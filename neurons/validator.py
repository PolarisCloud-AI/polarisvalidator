import asyncio
import uuid
import numpy as np
import bittensor as bt
from template.base.validator import BaseValidatorNeuron
from loguru import logger
from template.base.utils.weight_utils import normalize_max_weight, convert_weights_and_uids_for_emit, process_weights_for_netuid
from utils.api_utils import get_filtered_miners, get_miner_list_with_resources, update_container_payment_status, track_tokens,get_containers_for_miner,get_unverified_miners,update_miner_status
from utils.validator_utils import process_miners, verify_miners
from utils.state_utils import load_state, save_state
from utils.uptimedata import send_reward_log
import copy
import time
import os
import json

class PolarisNode(BaseValidatorNeuron):
    def __init__(self, config=None):
        super().__init__(config=config)
        self.max_allowed_weights = 500
        self.hotkeys = self.metagraph.hotkeys.copy()
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
        balance = self.subtensor.get_balance(self.wallet.hotkey.ss58_address)
        logger.info(f"Wallet balance: {balance}")
        self.instance_id = str(uuid.uuid4())[:8]
        logger.info(f"Initializing PolarisNode instance {self.instance_id}")
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        self.thread = None
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.weights_rate_limit = self.tempo
        self.last_weight_update_block = 0
        self._tasks_scheduled = False
        self.max_retries = 3
        self.retry_delay_base = 5
        self.step = 0

    def save_state(self):
        """Saves the current validator state to a file with defaults."""
        try:
            logger.info("Saving validator state.")
            state = {
                "step": self.step,
                "scores": self.scores.tolist() if hasattr(self, 'scores') else np.zeros(self.metagraph.n, dtype=np.float32).tolist(),
                "hotkeys": self.hotkeys if hasattr(self, 'hotkeys') else copy.deepcopy(self.metagraph.hotkeys),
                "last_weight_update_block": self.last_weight_update_block if hasattr(self, 'last_weight_update_block') else 0,
                "tempo": self.tempo if hasattr(self, 'tempo') else self.subtensor.tempo(self.config.netuid),
                "weights_rate_limit": self.weights_rate_limit if hasattr(self, 'weights_rate_limit') else self.tempo
            }
            os.makedirs(self.config.neuron.full_path, exist_ok=True)
            with open(os.path.join(self.config.neuron.full_path, "state.json"), "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def resync_metagraph(self):
        logger.info("Resyncing metagraph...")
        previous_metagraph = copy.deepcopy(self.metagraph)  # Changed from .copy() to copy.deepcopy()
        self.metagraph.sync(subtensor=self.subtensor)
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.weights_rate_limit = self.get_weights_rate_limit()
        if previous_metagraph.axons == self.metagraph.axons:
            return
        logger.info("Metagraph updated, re-syncing hotkeys and scores.")
        for uid, hotkey in enumerate(self.hotkeys):
            if hotkey != self.metagraph.hotkeys[uid]:
                self.scores[uid] = 0
        if len(self.hotkeys) < len(self.metagraph.hotkeys):
            new_scores = np.zeros(self.metagraph.n)
            min_len = min(len(self.hotkeys), len(self.scores))
            new_scores[:min_len] = self.scores[:min_len]
            self.scores = new_scores
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)  # Also update this line
        save_state(self)

    def get_registered_miners(self) -> list[int]:
        try:
            self.metagraph.sync()
            return [int(uid) for uid in self.metagraph.uids]
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    def get_weights_rate_limit(self):
        try:
            node = self.subtensor.substrate
            return node.query("SubtensorModule", "WeightsSetRateLimit", [self.config.netuid]).value
        except Exception as e:
            logger.error(f"Error fetching weights rate limit: {e}")
            return self.tempo

    def get_last_update(self):
        try:
            node = self.subtensor.substrate
            my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            last_update_blocks = self.subtensor.block - node.query("SubtensorModule", "LastUpdate", [self.config.netuid]).value[my_uid]
            logger.info(f"Last update was {last_update_blocks} blocks ago")
            return last_update_blocks
        except Exception as e:
            logger.error(f"Error fetching last update: {e}")
            return 1000

    def check_registered(self):
        try:
            if not self.subtensor.is_hotkey_registered(
                netuid=self.config.netuid,
                hotkey_ss58=self.wallet.hotkey.ss58_address,
            ):
                logger.error(f"Validator {self.wallet.hotkey.ss58_address} is not registered on netuid {self.config.netuid}.")
                return False
            logger.info("Validator is registered.")
            return True
        except Exception as e:
            logger.error(f"Error checking registration: {e}")
            return False

    def is_chain_synced(self):
        try:
            current_block = self.subtensor.block
            return current_block > 0
        except Exception as e:
            logger.error(f"Error checking chain sync: {e}")
            return False

    async def is_subnet_ready_for_weights(self) -> bool:
        try:
            current_block = self.subtensor.block
            self.tempo = self.subtensor.tempo(self.config.netuid)
            weights_rate_limit = self.get_weights_rate_limit()
            blocks_since_last_update = current_block - self.last_weight_update_block
            last_update_from_chain = self.get_last_update()

            effective_rate_limit = max(self.tempo, weights_rate_limit)
            
            if not self.is_chain_synced():
                logger.warning("Subtensor not synced with chain.")
                return False

            is_ready_internal = blocks_since_last_update >= effective_rate_limit
            is_ready_chain = last_update_from_chain >= effective_rate_limit

            if not is_ready_internal or (last_update_from_chain != 1000 and not is_ready_chain):
                logger.info(f"Not ready: {blocks_since_last_update}/{effective_rate_limit} blocks (internal), {last_update_from_chain}/{effective_rate_limit} (chain)")
                return False

            logger.info(f"Ready: {blocks_since_last_update}/{effective_rate_limit} blocks (internal), {last_update_from_chain}/{effective_rate_limit} (chain)")
            return True
        except Exception as e:
            logger.error(f"Error checking subnet readiness: {e}")
            return False

    async def update_validator_weights(self, results: dict[int, float], container_updates: dict[int, list[str]], uptime_rewards_dict: dict[int, dict]):
        logger.info("Starting update_validator_weights...")
        async with self.lock:
            try:
                if not results:
                    logger.warning("No results to process.")
                    return
                if not self.check_registered():
                    logger.error("Validator not registered. Skipping weight update.")
                    return
                if not await self.is_subnet_ready_for_weights():
                    logger.info("Subnet not ready for weights.")
                    return

                subnet_price = 0.0
                try:
                    async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                        subnet_info = await sub.subnet(self.config.netuid)
                        subnet_price = float(subnet_info.price) if subnet_info else 0.0
                except Exception as e:
                    logger.error(f"Error fetching subnet price: {e}")
                    return

                weighted_scores = {
                    int(uid): float(score) * subnet_price if subnet_price > 0 else float(score)
                    for uid, score in results.items()
                }
                if not weighted_scores:
                    logger.warning("No weighted scores calculated.")
                    return

                weights, uids = convert_weights_and_uids_for_emit(weighted_scores)
                weights = np.array(weights, dtype=np.float32)
                weights = normalize_max_weight(weights, limit=0.1)

                for attempt in range(self.max_retries):
                    success = process_weights_for_netuid(
                        weights=weights.tolist(),
                        uids=uids,
                        netuid=self.config.netuid,
                        subtensor=self.subtensor,
                        wallet=self.wallet
                    )

                    if success:
                        logger.info(f"Weights updated successfully on attempt {attempt + 1}.")
                        self.last_weight_update_block = self.subtensor.block
                        self.step += 1
                        save_state(self)
                        for uid in container_updates:
                            for container_id in container_updates[uid]:
                                update_container_payment_status(container_id)
                            if uid in uptime_rewards_dict and uptime_rewards_dict[uid]["reward_amount"] > 0:
                                send_reward_log(uptime_rewards_dict[uid])
                        for uid, weight in zip(uids, weights):
                            if weight > 0:
                                track_tokens(str(uid), weight, self.wallet.hotkey_str, "Bittensor")
                        break
                    else:
                        logger.warning(f"Weight update failed on attempt {attempt + 1}/{self.max_retries}")
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay_base * (2 ** attempt)
                            logger.info(f"Retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                else:
                    logger.error("All retry attempts failed. Skipping updates.")
            except Exception as e:
                logger.error(f"Exception in update_validator_weights: {e}")

    async def verify_miners_loop(self):
        while True:
            try:
                logger.info("Starting verify_miners_loop...")
                miners = self.get_registered_miners()
                bittensor_miners = get_filtered_miners(miners)
                await verify_miners(list(bittensor_miners.keys()), get_unverified_miners, update_miner_status)
                await asyncio.sleep(180)
            except Exception as e:
                logger.error(f"Error in verify_miners_loop: {e}")
                await asyncio.sleep(60)

    async def process_miners_loop(self):
        while True:
            try:
                logger.info("Starting process_miners_loop...")
                miners = self.get_registered_miners()
                bittensor_miners = get_filtered_miners(miners)
                miner_resources = get_miner_list_with_resources(bittensor_miners)
                results, container_updates, uptime_rewards_dict = await process_miners(miners, miner_resources, get_containers_for_miner)
                await self.update_validator_weights(results, container_updates, uptime_rewards_dict)
                current_block = self.subtensor.block
                blocks_since_last = current_block - self.last_weight_update_block
                effective_rate_limit = max(self.tempo, self.weights_rate_limit)
                blocks_remaining = effective_rate_limit - blocks_since_last
                sleep_time = min(3600, max(720, blocks_remaining * 12)) if blocks_remaining > 0 else 3600
                logger.info(f"Sleeping for {sleep_time} seconds until next weight update opportunity.")
                await asyncio.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Error in process_miners_loop: {e}")
                await asyncio.sleep(720)

    async def setup(self):
        load_state(self)
        if not self._tasks_scheduled:
            asyncio.create_task(self.verify_miners_loop())
            asyncio.create_task(self.process_miners_loop())
            self._tasks_scheduled = True
        logger.info("Setup completed")

    async def cleanup(self):
        pass

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def forward(self):
        try:
            await self.update_validator_weights({}, {}, {})
        except Exception as e:
            logger.error(f"Error in forward: {e}")

    def run(self):
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.success("Validator stopped by keyboard interrupt.")
        except Exception as e:
            logger.error(f"Error running validator: {e}")

if __name__ == "__main__":
    async def main():
        async with PolarisNode() as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await asyncio.sleep(300)
    asyncio.run(main())
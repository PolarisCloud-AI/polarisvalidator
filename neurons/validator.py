import asyncio
import uuid
import numpy as np
import bittensor as bt
import copy
import time
import os
import json
from loguru import logger
from template.base.validator import BaseValidatorNeuron
from template.base.utils.weight_utils import (
    normalize_max_weight,
    convert_weights_and_uids_for_emit,
    process_weights_for_netuid
)
from utils.api_utils import (
    get_filtered_miners,
    get_miner_list_with_resources,
    update_container_payment_status,
    track_tokens,
    get_containers_for_miner,
    get_unverified_miners,
    update_miner_status,filter_miners_by_id

)
from utils.validator_utils import process_miners, verify_miners
from utils.state_utils import load_state, save_state
from utils.uptimedata import send_reward_log

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
        
        # Score decay
        self.score_decay = 0.9
        
        # Subnet price fallback
        self.default_subnet_price = 1.0

    def save_state(self):
        """Saves the validator state by calling the external save_state function."""
        save_state(self)
        logger.info("Validator state saved via external state_utils.save_state")

    def load_state(self):
        """Loads the validator state by calling the external load_state function."""
        load_state(self)
        logger.info("Validator state loaded via external state_utils.load_state")

    def resync_metagraph(self):
        """Resyncs the metagraph and updates related state."""
        logger.info("Resyncing metagraph...")
        previous_metagraph = copy.deepcopy(self.metagraph)
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
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
        self.save_state()

    def get_registered_miners(self) -> list[int]:
        """Returns a list of registered miner UIDs."""
        try:
            self.metagraph.sync()
            return [int(uid) for uid in self.metagraph.uids]
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    def get_weights_rate_limit(self):
        """Fetches the weights rate limit from the blockchain."""
        try:
            node = self.subtensor.substrate
            return node.query("SubtensorModule", "WeightsSetRateLimit", [self.config.netuid]).value
        except Exception as e:
            logger.error(f"Error fetching weights rate limit: {e}")
            return self.tempo

    def get_last_update(self):
        """Fetches the number of blocks since the last weight update."""
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
        """Checks if the validator is registered on the subnet."""
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
        """Checks if the chain is synced."""
        try:
            current_block = self.subtensor.block
            return current_block > 0
        except Exception as e:
            logger.error(f"Error checking chain sync: {e}")
            return False

    async def is_subnet_ready_for_weights(self) -> bool:
        """Checks if the subnet is ready for weight updates."""
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
        """Updates validator weights based on miner scores."""
        logger.info("Starting update_validator_weights...")
        async with self.lock:
            try:
                if not results:
                    logger.warning("No results. Skipping weight update.")
                    return
                if not self.check_registered():
                    logger.error("Validator not registered. Skipping weight update.")
                    return
                if not await self.is_subnet_ready_for_weights():
                    logger.info("Subnet not ready for weights.")
                    return

                subnet_price = self.default_subnet_price
                try:
                    async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                        subnet_info = await sub.subnet(self.config.netuid)
                        subnet_price = float(subnet_info.price) if subnet_info and subnet_info.price > 0 else self.default_subnet_price
                    logger.info(f"Subnet price: {subnet_price}")
                except Exception as e:
                    logger.error(f"Error fetching subnet price, using default {self.default_subnet_price}: {e}")

                # Apply score decay
                self.scores *= self.score_decay
                logger.info(f"Applied score decay: {self.score_decay}, new scores sum: {self.scores.sum()}")

                # Update scores with new results
                for uid, score in results.items():
                    uid = int(uid)
                    if uid < len(self.scores):
                        self.scores[uid] = max(self.scores[uid], float(score) * subnet_price)
                logger.info(f"Updated scores, top 5: {sorted(zip(range(len(self.scores)), self.scores), key=lambda x: x[1], reverse=True)[:5]}")

                # Prepare weighted scores
                weighted_scores = {str(uid): float(score) for uid, score in enumerate(self.scores) if score > 0}

                weights, uids = convert_weights_and_uids_for_emit(weighted_scores)

                for attempt in range(self.max_retries):
                    success = process_weights_for_netuid(
                        weights=weights,
                        uids=uids,
                        netuid=self.config.netuid,
                        subtensor=self.subtensor,
                        wallet=self.wallet
                    )

                    if success:
                        logger.info(f"Weights updated successfully on attempt {attempt + 1}.")
                        self.last_weight_update_block = self.subtensor.block
                        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
                        self.step += 1
                        self.save_state()
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
        """Periodically verifies miners."""
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
        """Periodically processes miners and updates weights."""
        while True:
            try:
                logger.info("Starting process_miners_loop...")
                miners = self.get_registered_miners()
                white_list = get_filtered_miners(miners)
                bittensor_miners = filter_miners_by_id(white_list)
                miner_resources = get_miner_list_with_resources(bittensor_miners)
                results, container_updates, uptime_rewards_dict = await process_miners( miners, miner_resources, get_containers_for_miner, self.tempo, max_score=self.max_allowed_weights)
                await self.update_validator_weights(results, container_updates, uptime_rewards_dict)
                current_block = self.subtensor.block
                blocks_since_last = current_block - self.last_weight_update_block
                effective_rate_limit = max(self.tempo, self.weights_rate_limit)
                blocks_remaining = effective_rate_limit - blocks_since_last
                sleep_time = max(60, blocks_remaining * 12)
                logger.info(f"Sleeping for {sleep_time} seconds until next weight update opportunity.")
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in process_miners_loop: {e}")
                logger.info("Sleeping for 60 seconds after error.")
                await asyncio.sleep(60)

    async def setup(self):
        """Sets up the validator."""
        self.load_state()
        if not self._tasks_scheduled:
            asyncio.create_task(self.verify_miners_loop())
            asyncio.create_task(self.process_miners_loop())
            self._tasks_scheduled = True
        logger.info("Setup completed")

    async def cleanup(self):
        """Cleans up resources."""
        pass

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def forward(self):
        """Handles forward pass (placeholder)."""
        try:
            await self.update_validator_weights({}, {}, {})
        except Exception as e:
            logger.error(f"Error in forward: {e}")

    def run(self):
        """Runs the validator loop."""
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
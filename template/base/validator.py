import copy
import numpy as np
import asyncio
import argparse
import threading
import bittensor as bt
from loguru import logger
import sys
from typing import List, Union
from traceback import print_exception
from template.base.neuron import BaseNeuron
from template.base.utils.weight_utils import (
    process_weights_for_netuid,
    convert_weights_and_uids_for_emit,
)
from template.mock import MockDendrite
from template.utils.config import add_validator_args
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
    colorize=True,
)
class BaseValidatorNeuron(BaseNeuron):
    neuron_type: str = "ValidatorNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        add_validator_args(cls, parser)

    def __init__(self, config=None):
        super().__init__(config=config)
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
        self.dendrite = MockDendrite(wallet=self.wallet) if self.config.mock else bt.dendrite(wallet=self.wallet)
        bt.logging.info(f"Dendrite: {self.dendrite}")
        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
        self.miner_score_queue = asyncio.Queue()
        self.sync()
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        self.thread = None
        self.lock = asyncio.Lock()
    
    def serve_axon(self):
        bt.logging.info("Serving axon to chain...")
        try:
            self.axon = bt.axon(wallet=self.wallet, config=self.config)
            self.subtensor.serve_axon(netuid=self.config.netuid, axon=self.axon)
            bt.logging.info(f"Validator running on {self.config.subtensor.chain_endpoint} with netuid {self.config.netuid}")
        except Exception as e:
            bt.logging.error(f"Failed to serve Axon: {e}")
    
    async def get_subnet_prices(self):
        try:
            async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                # Use the 'sub' object to fetch subnet prices
                subnet_prices = {int(netuid): float((await sub.subnet(netuid)).price) for netuid in self.metagraph.uids}
                return subnet_prices
        except Exception as e:
            bt.logging.error(f"Error in get_subnet_prices: {e}")
            return {}  # Or return None, depending on how you want to handle the error

    
    async def update_validator_weights(self):
        logger.info("Updating validator weights...")
        try:
            subnet_prices = await asyncio.wait_for(self.get_subnet_prices(), timeout=30)
            logger.info(f"Subnet prices: {subnet_prices}")
            total_weight = sum(subnet_prices.values())
            logger.info(f"Total weight: {total_weight}")
            normalized_prices = {uid: price / total_weight for uid, price in subnet_prices.items() if total_weight > 0}
            logger.info(f"Normalized prices: {normalized_prices}")
            while not self.miner_score_queue.empty():
                logger.info("Processing miner scores...")
                try:
                    uid, score = await self.miner_score_queue.get()
                    logger.info(f"UID: {uid}, Score: {score}")
                    uid = int(uid)  # Ensure UID is integer
                    self.scores[uid] = float(score) * normalized_prices.get(uid, 0)
                except Exception as e:
                    bt.logging.error(f"Error processing score: {e}")
                    continue
            logger.info("Converting weights and uids...")
            weights, uids = convert_weights_and_uids_for_emit(self.scores) # Remove scores=
            weights = [float(w) for w in weights]  # Convert weights to Python floats
            process_weights_for_netuid(weights, uids, self.config.netuid, self.subtensor)
            logger.info("Weights updated successfully.")
        except Exception as e:
            logger.error(f"Exception in update_validator_weights: {e}")

    
    async def check_validator_state(self):
        while True:
            bt.logging.info(f"Current miner data in queue: {self.miner_score_queue.qsize()}")
            await asyncio.sleep(60)
    
    async def forward(self):
        try:
            self.sync()
            await self.update_validator_weights()
        except Exception as e:
            bt.logging.error(f"Error in forward loop: {e}")
    
    def run(self):
        self.sync()
        try:
            self.loop.create_task(self.check_validator_state())
            while not self.should_exit:
                self.loop.run_until_complete(self.forward())
                asyncio.sleep(300)
        except KeyboardInterrupt:
            self.axon.stop()
            bt.logging.success("Validator killed by keyboard interrupt.")
            exit()
        except Exception as e:
            bt.logging.error(f"Error during validation: {e}")
            bt.logging.debug(str(print_exception(type(e), e, e.__traceback__)))
    
    def run_in_background_thread(self):
        if not self.is_running:
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
    
    def stop_run_thread(self):
        if self.is_running:
            self.should_exit = True
            self.thread.join(5)
            self.is_running = False

if __name__ == "__main__":
    async def main():
        async with BaseValidatorNeuron() as validator:
            while True:
                await validator.forward()
                await asyncio.sleep(300)
    asyncio.run(main())
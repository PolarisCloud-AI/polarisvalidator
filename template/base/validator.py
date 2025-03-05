import copy
import numpy as np
import asyncio
import argparse
import threading
import bittensor as bt
from typing import List, Union
from traceback import print_exception
from template.base.neuron import BaseNeuron
from template.base.utils.weight_utils import (
    process_weights_for_netuid,
    convert_weights_and_uids_for_emit,
)
from template.mock import MockDendrite
from template.utils.config import add_validator_args

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
        async with bt.subtensor.async_get(self.config.subtensor.network) as sub:
            return {netuid: (await sub.subnet(netuid)).price for netuid in self.metagraph.uids}
    
    async def update_validator_weights(self):
        subnet_prices = await self.get_subnet_prices()
        while not self.miner_score_queue.empty():
            uid, score = await self.miner_score_queue.get()
            self.scores[uid] = score
        
        norm = np.linalg.norm(self.scores, ord=1) or 1.0
        raw_weights = self.scores / norm
        processed_uids, processed_weights = process_weights_for_netuid(
            self.metagraph.uids, raw_weights, self.config.netuid, self.subtensor, self.metagraph
        )
        uint_uids, uint_weights = convert_weights_and_uids_for_emit(processed_uids, processed_weights)
        result, msg = await self.subtensor.set_weights(
            wallet=self.wallet, netuid=self.config.netuid, uids=uint_uids, weights=uint_weights, wait_for_finalization=False
        )
        if result:
            bt.logging.info("Successfully set weights on chain.")
        else:
            bt.logging.error(f"Failed to set weights: {msg}")
    
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
import copy
import numpy as np
import asyncio
import argparse
import bittensor as bt
from template.base.neuron import BaseNeuron
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
        try:
            async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                # Use the 'sub' object to fetch subnet prices
                subnet_prices = {int(netuid): float((await sub.subnet(netuid)).price) for netuid in self.metagraph.uids}
                return subnet_prices
        except Exception as e:
            bt.logging.error(f"Error in get_subnet_prices: {e}")
            return {}  # Or return None, depending on how you want to handle the error
    
    async def check_validator_state(self):
        while True:
            bt.logging.info(f"Current miner data in queue: {self.miner_score_queue.qsize()}")
            await asyncio.sleep(60)

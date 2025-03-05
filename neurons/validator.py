import time
import json
import requests
import torch
import bittensor as bt
from template.base.validator import BaseValidatorNeuron
import asyncio
import os
import copy
from loguru import logger
from typing import List, Dict
import numpy as np
from utils.pogs import fetch_compute_specs, compare_compute_resources, compute_resource_score

class PolarisNode(BaseValidatorNeuron):
    def __init__(self, config=None):
        super().__init__(config=config)
        self.max_allowed_weights = 500
    
    def save_state(self):
        """Saves the current state of the validator to a file."""
        bt.logging.info("Saving validator state.")
        state = {
            "step": self.step,
            "scores": self.scores.tolist(),
            "hotkeys": self.hotkeys
        }
        with open(self.config.neuron.full_path + "/state.json", "w") as f:
            json.dump(state, f)

    def load_state(self):
        """Loads the saved state of the validator from a file."""
        try:
            bt.logging.info("Loading validator state.")
            with open(self.config.neuron.full_path + "/state.json", "r") as f:
                state = json.load(f)
                self.step = state["step"]
                self.scores = np.array(state["scores"], dtype=np.float32)
                self.hotkeys = state["hotkeys"]
        except FileNotFoundError:
            bt.logging.warning("No previous state found. Starting fresh.")

    def resync_metagraph(self):
        """Resyncs the metagraph and updates the hotkeys and moving averages."""
        bt.logging.info("Resyncing metagraph...")

        previous_metagraph = copy.deepcopy(self.metagraph)

        # Sync metagraph from subtensor
        self.metagraph.sync(subtensor=self.subtensor)

        # Check if the metagraph has changed
        if previous_metagraph.axons == self.metagraph.axons:
            return

        bt.logging.info("Metagraph updated, re-syncing hotkeys and moving averages.")
        
        # Zero out hotkeys that have been replaced
        for uid, hotkey in enumerate(self.hotkeys):
            if hotkey != self.metagraph.hotkeys[uid]:
                self.scores[uid] = 0  # Reset scores for replaced hotkeys

        # Expand score array if the metagraph grew
        if len(self.hotkeys) < len(self.metagraph.hotkeys):
            new_scores = np.zeros((self.metagraph.n))
            min_len = min(len(self.hotkeys), len(self.scores))
            new_scores[:min_len] = self.scores[:min_len]
            self.scores = new_scores

        # Update hotkeys
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
    def get_registered_miners(self) -> List[int]:
        try:
            self.metagraph.sync()
            return self.metagraph.uids.tolist()
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    async def verify_miners_loop(self):
        """Continuously verify miners in a separate async loop."""
        while True:
            miners = self.get_registered_miners()
            commune_miners = self.get_filtered_miners(miners)
            await self.verify_miners(list(commune_miners.keys()))
            await asyncio.sleep(180)  # Run every 30 minutes
    
    async def process_miners_loop(self):
        """Process miners separately from verification, running every 3 hours."""
        while True:
            miners = self.get_registered_miners()
            logger.info(f"Processing miners: {miners}")
            commune_miners = self.get_filtered_miners(miners)
            miner_resources = self.get_miner_list_with_resources(commune_miners)
            results = await self.process_miners(miners, miner_resources)
            if results:
                for miner_uid, final_score in results.items():
                    await self.miner_score_queue.put((miner_uid, final_score))
                logger.info("Miner score processing complete.")
            await asyncio.sleep(10800)  # Run every 3 hours
    
    def get_filtered_miners(self, allowed_uids: List[int]) -> Dict[str, str]:
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/commune/miners")
            if response.status_code == 200:
                miners_data = response.json()
                return {
                    miner["miner_id"]: miner["network_info"]["bittensor_uid"]
                    for miner in miners_data if int(miner["network_info"]["bittensor_uid"]) in allowed_uids
                }
        except Exception as e:
            logger.error(f"Error fetching filtered miners: {e}")
        return {}
    def get_miner_list_with_resources(self, miner_commune_map: Dict[str, str]) -> Dict:
            """Fetch verified miners with their compute resources."""
            try:
                response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
                if response.status_code == 200:
                    miners_data = response.json()
                    return {
                        miner["id"]: {
                            "compute_resources": miner["compute_resources"],
                            "bittensor_uid": miner_commune_map.get(miner["id"])
                        }
                        for miner in miners_data
                        if miner["status"] == "verified" and miner["id"] in miner_commune_map
                    }
                else:
                    logger.error(f"Failed to fetch miners. Status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching miner list with resources: {e}")
            return {}
    def get_unverified_miners(self) -> Dict:
        """
        Fetch verified miners from the network along with their compute resources.
        Returns a dictionary containing miner IDs and their compute resources.
        """
        unverified_miners={}
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
            if response.status_code == 200:
                miners_data = response.json()
                unverified_miners = {
                    miner["id"]: miner["compute_resources"]
                    for miner in miners_data
                    if miner["status"] == "pending_verification"
                }
                return unverified_miners
            else:
                print(f"Failed to fetch miners. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error fetching miner list: {e}")
        return {}

    
    def update_miner_status(self,miner_id):
        """
        Updates the status of a miner to 'verified' using a PATCH request.

        Args:
            miner_id (str): The ID of the miner to update.

        Returns:
            Response object: The response from the PATCH request.
        """
        url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/status"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "status": "verified"
        }

        try:
            response = requests.patch(url, json=payload, headers=headers)
            response.raise_for_status()  
            json_response = response.json()  
            logger.info(f"Miner {miner_id} is verifed")
            return json_response.get("status", "unknown")
        except requests.exceptions.RequestException as e:
            print(f"Error updating miner status: {e}")
            return None

    async def process_miners(self, miners: List[int], miner_resources: Dict) -> Dict[int, float]:
        results = {}
        active_miners = [int(value["bittensor_uid"]) for value in miner_resources.values()]
        for miner in miners:
            compute_score = 0
            total_termination_time = 0
            total_score = 0.0
            rewarded_containers = 0
            if miner not in active_miners:
                logger.debug(f"Miner {miner} is not active. Skipping...")
                continue
            for key, value in miner_resources.items():
                if value["bittensor_uid"] == str(miner):
                    compute_score = compute_resource_score(value["compute_resources"])
                    containers = self.get_containers_for_miner(key)
                    for container in containers:
                        if container['status'] == 'terminated' and container['payment_status'] == 'pending':
                            scheduled_termination = container['subnet_details'].get('scheduled_termination', 0)
                            total_termination_time += scheduled_termination
                            rewarded_containers += 1
                            total_score = total_termination_time
                            self.update_container_payment_status(container['container_id'])
                        if rewarded_containers > 0:
                            average_score = total_score / rewarded_containers
                            final_score = (average_score + total_termination_time) * compute_score[0]
                            results[miner] = final_score
        return results
    

    def extract_ssh_and_password(self,miner_resources):
        
        if not miner_resources:
            return {"error": "No compute resources available for the miner."}

        # Extract the first compute resource (assuming SSH and password are in the network field)
        compute_resource = miner_resources[0]
        network_info = compute_resource.get("network", {})

        ssh_string = network_info.get("ssh", "").replace("ssh://", "ssh ").replace(":", " -p ")
        password = network_info.get("password", "")

        if not ssh_string or not password:
            return {"error": "SSH or password information is missing."}

        return {
            "ssh_string": ssh_string,
            "password": password
        }


    async def verify_miners(self, miners):
        for miner in miners:
            compute_resources = self.get_unverified_miners()
            if miner not in compute_resources:
                logger.debug(f"Miner {miner} is not in pending verification. Skipping...")
                continue
            miner_resources = compute_resources[miner]
            ssh_info = self.extract_ssh_and_password(miner_resources)
            if "error" not in ssh_info:
                ssh_string = ssh_info["ssh_string"]
                password = ssh_info["password"]
                result = fetch_compute_specs(ssh_string, password)
                pog_score = compare_compute_resources(result, miner_resources[0])
                if pog_score["score"] >= 10:
                    self.update_miner_status(miner)
            else:
                logger.info(f"Miner {miner} is unverified")
    
    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def setup(self):
        self.load_state()
        asyncio.create_task(self.verify_miners_loop())
        asyncio.create_task(self.process_miners_loop())
    
    async def cleanup(self):
        pass

if __name__ == "__main__":
    async def main():
        async with PolarisNode() as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await asyncio.sleep(300)
    asyncio.run(main())

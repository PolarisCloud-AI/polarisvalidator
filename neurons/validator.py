import time
import json
import requests
import torch
import bittensor as bt
from template.base.validator import BaseValidatorNeuron
import asyncio
import os
from loguru import logger
from typing import List, Dict
from utils.pogs import fetch_compute_specs,compare_compute_resources,compute_resource_score


class PolarisNode(BaseValidatorNeuron):
    def __init__(self,config=None):
        super().__init__(config=config)
        self.max_allowed_weights = 500
    
        

    def get_registered_miners(self) -> List[int]:
        """
        Fetch the list of registered miners (UIDs) on the Bittensor network.
        """
        try:
            self.metagraph.sync()
            return self.metagraph.uids.tolist()
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    def track_miner_containers(self):
        """Fetch and update active containers for each miner."""
        miners = self.get_registered_miners()
        logger.info(f"Registered miners: {miners}")

        commune_miners = self.get_filtered_miners(miners)
        self.verify_miners(list(commune_miners.keys()))

        miner_resources = self.get_miner_list_with_resources(commune_miners)
        logger.info("Processing miners and their containers...")

        results = self.process_miners(miners, miner_resources)
        if results:
            for miner_uid, final_score in results.items():
                self.miner_data[miner_uid] = final_score
            logger.info("Miner score processing complete.")
            logger.debug(f"Updated miner_data: {self.miner_data}")

            # Set weights using Bittensor
            self.set_weights(self.miner_data)
        else:
            logger.info("No miners to process.")
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

    def get_filtered_miners(self, allowed_uids: List[int]) -> Dict[str, str]:
        """Fetch verified miners and return only those in the allowed_uids list."""
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/commune/miners")
            if response.status_code == 200:
                miners_data = response.json()
                return {
                    miner["miner_id"]: miner["network_info"]["bittensor_uid"]
                    for miner in miners_data
                    if int(miner["network_info"]["bittensor_uid"]) in allowed_uids and miner.get("miner_id")
                }
            logger.warning("No verified miners yet on the network.")
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

    def process_miners(self, miners: List[int], miner_resources: Dict) -> Dict[int, float]:
        results = []
        active_miners=[int(value["bittensor_uid"]) for value in miner_resources.values()]
        print(f"active miners f{active_miners}")
        for miner in miners:
            compute_score=0
            total_termination_time = 0
            total_score = 0.0
            rewarded_containers = 0
            if miner not in [m for m in active_miners]:
                logger.debug(f"Miner {miner} is not active. Skipping...")
                continue
            # Getting miners scores depending on the specs
            for key, value in miner_resources.items():
                if value["bittensor_uid"] == str(miner):
                    compute_score=compute_resource_score(value["compute_resources"])
                    # Fetch containers for the miner
                    containers = self.get_containers_for_miner(key)
                    for container in containers:
                    # Process only active containers with pending payment
                        if container['status'] == 'terminated' and container['payment_status'] == 'pending':
                            scheduled_termination = container['subnet_details'].get('scheduled_termination', 0)
                            total_termination_time += scheduled_termination
                            rewarded_containers += 1
                            total_score=total_termination_time 
                            self.update_container_payment_status(container['container_id']) 
                        
                         
                        # If containers are processed, calculate the final score
                        if rewarded_containers > 0:
                            average_score = total_score / rewarded_containers
                            final_score = average_score + total_termination_time + compute_score[0]
                            results.append({
                                'miner_uid': miner,
                                'final_score': final_score
                            }) 
            return results
        
    def verify_miners(self,miners):
        compute_resources = self.get_unverified_miners()
        active_miners=list(compute_resources.keys())
        if active_miners:
            for miner in miners:
                pog_scores=0
                if miner not in [m for m in active_miners]:
                    logger.debug(f"Miner {miner} is not active. Skipping...")
                    continue
                #test for proof of resources
                miner_resources=compute_resources.get(miner, None)
                ssh_and_password=self.extract_ssh_and_password(miner_resources)
                if "error" not in ssh_and_password:
                    ssh_string = ssh_and_password["ssh_string"]
                    password = ssh_and_password["password"]
                    # ssh_string="ssh tobius@5.tcp.eu.ngrok.io -p 19747"
                    # password="masaka1995t"
                    # Use the extracted SSH and password in fetch_compute_specs
                    result = fetch_compute_specs(ssh_string, password)
                    pog_scores =compare_compute_resources(result,miner_resources[0])
                    logger.info(f"Miner {miner}'s results from pog {pog_scores}")
                    pog_scores=int(pog_scores["score"])
                    if pog_scores>=10:
                        self.update_miner_status(miner)
                    else:
                        logger.info(f"Miner {miner} is unverified")
                else:
                    logger.info(f"Miner {miner} is unverified")
            return logger.info(f"Pending miner verification has been executed")
        else:
            return logger.info(f"Currently no pending miners to verify")

    def set_weights(self, miner_scores: Dict[int, float]):
        """
        Normalize and set weights for miners in the Bittensor blockchain.
        """
        if not miner_scores:
            logger.info("No miner scores to set weights.")
            return

        # Normalize scores
        uids = list(miner_scores.keys())
        scores = torch.tensor(list(miner_scores.values()), dtype=torch.float32)
        scores[scores < 0] = 0  # Remove negative scores

        weights = torch.nn.functional.normalize(scores, p=1.0, dim=0)
        logger.info(f"Normalized weights: {weights.tolist()}")

        # Set weights on the blockchain
        try:
            self.subtensor.set_weights(
                netuid=self.netuid,
                wallet=self.wallet,
                uids=uids,
                weights=weights,
                wait_for_inclusion=False
            )
            logger.success("Successfully set weights on the blockchain.")
        except Exception as e:
            logger.error(f"Failed to set weights: {e}")
    async def forward(self):
        """Main execution method."""
        try:
            logger.info("Fetching commits...")
            self.track_miner_containers()
        except Exception as e:
            logger.error(f"Error in forward: {str(e)}")
    
    async def __aenter__(self):
        await self.setup()  # Assuming you have a setup method
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()  # Assuming you have a cleanup method

    async def setup(self):
        # Initialization logic here
        pass

    async def cleanup(self):
        # Cleanup logic here
        pass


# Main execution
if __name__ == "__main__":
    async def main():
        async with PolarisNode() as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await validator.forward()
                await asyncio.sleep(300) 

    asyncio.run(main())

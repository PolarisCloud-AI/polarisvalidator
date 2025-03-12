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
import sys
from template.base.utils.weight_utils import (
    process_weights_for_netuid,
    convert_weights_and_uids_for_emit,
)
from utils.pogs import fetch_compute_specs, compare_compute_resources, compute_resource_score,time_calculation,has_expired
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
    colorize=True,
)
class PolarisNode(BaseValidatorNeuron):
    def __init__(self, config=None):
        super().__init__(config=config)
        self.max_allowed_weights = 500
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        self.thread = None

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
            logger.warning("No previous state found. Starting fresh.")

    def resync_metagraph(self):
        """Resyncs the metagraph and updates the hotkeys and moving averages."""
        logger.info("Resyncing metagraph...")

        previous_metagraph = copy.deepcopy(self.metagraph)

        # Sync metagraph from subtensor
        self.metagraph.sync(subtensor=self.subtensor)

        # Check if the metagraph has changed
        if previous_metagraph.axons == self.metagraph.axons:
            return

        logger.info("Metagraph updated, re-syncing hotkeys and moving averages.")
        
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
            return [int(uid) for uid in self.metagraph.uids]
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    async def verify_miners_loop(self):
        """Continuously verify miners in a separate async loop."""
        while True:
            logger.info("Starting verify_miners_loop...")
            miners = self.get_registered_miners()
            logger.info(f"Registered miners retrieved")
            bittensor_miners = self.get_filtered_miners(miners)
            await self.verify_miners(list(bittensor_miners.keys()))

            await asyncio.sleep(180)  # Run every 3 minutes
    
    async def process_miners_loop(self):
        """Process miners separately from verification, running every 30 seconds."""
        while True:
            try:
                logger.info("Starting process_miners_loop...")

                # Step 1: Get registered miners
                miners = self.get_registered_miners()

                # Step 2: Filter miners
                bittensor_miners = self.get_filtered_miners(miners)

                # Step 3: Get miner resources
                miner_resources = self.get_miner_list_with_resources(bittensor_miners)

                # Step 4: Process miners
                results = await self.process_miners(miners, miner_resources)
                logger.info(f"Validation results: {results}")

                # Step 5: Directly update validator weights with results
                if results:
                    logger.info("Calling update_validator_weights() with results...")
                    await self.update_validator_weights(results)  # Pass results directly
                    logger.info("Finished calling update_validator_weights()")
                else:
                    logger.warning("No results to process. Skipping update_validator_weights.")

                # Step 6: Sleep before next iteration
                logger.info("Sleeping for 30 seconds...")
                await asyncio.sleep(180)

            except Exception as e:
                logger.error(f"Error in process_miners_loop: {e}")

    
    def get_filtered_miners(self, allowed_uids: List[int]) -> Dict[str, str]:
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
            if response.status_code == 200:
                miners_data = response.json()
                return {
                    miner["miner_id"]: miner["network_info"]["subnet_uid"]
                    for miner in miners_data if int(miner["network_info"]["subnet_uid"]) in allowed_uids
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
                            "subnet_uid": miner_commune_map.get(miner["id"])
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
            logger.error(f"Error updating miner status: {e}")
            return None
        
    def get_containers_for_miner(self, miner_uid: str) -> List[str]:
            """Fetch container IDs associated with a miner."""
            try:
                response = requests.get(f"https://orchestrator-gekh.onrender.com/api/v1/containers/miner/direct/{miner_uid}")
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"No containers yet for {miner_uid}")
            except Exception as e:
                logger.error(f"Error fetching containers for miner {miner_uid}: {e}")
            return []
    
    async def process_miners(self, miners: List[int], miner_resources: Dict) -> Dict[int, float]:
        """
        Process miners and calculate their scores based on container performance and compute resources.
        Also updates payment status for rewarded containers.
        
        Args:
            miners: List of miner UIDs to process
            miner_resources: Dictionary mapping miner IDs to their resource information
            
        Returns:
            Dictionary mapping miner UIDs to their calculated scores
        """
        results = {}
        # Create a mapping of subnet_uid to miner_id for easier lookup
        subnet_to_miner_map = {}
        
        # Build a map of subnet_uid to miner_id for quick reference
        for miner_id, info in miner_resources.items():
            subnet_uid = int(info["subnet_uid"])
            subnet_to_miner_map[subnet_uid] = miner_id
        
        # Get the list of active miners (those with resources)
        active_miners = [int(info["subnet_uid"]) for info in miner_resources.values()]
        
        # Process each miner in the list
        for miner_uid in miners:
            # Skip miners that aren't active
            if miner_uid not in active_miners:
                logger.debug(f"Miner {miner_uid} is not active. Skipping...")
                continue
            
            # Get the associated miner_id from the subnet_uid
            miner_id = subnet_to_miner_map.get(miner_uid)
            if not miner_id:
                logger.warning(f"No miner_id found for subnet_uid {miner_uid}")
                continue
                
            # Get miner's compute resource info
            miner_info = miner_resources.get(miner_id)
            if not miner_info:
                logger.warning(f"No resource info found for miner_id {miner_id}")
                continue
                
            # Calculate compute score based on resources
            try:
                compute_score = compute_resource_score(miner_info["compute_resources"][0])
                logger.info(f"Compute score for miner {miner_uid}: {compute_score}")
            except (KeyError, IndexError, Exception) as e:
                logger.error(f"Error calculating compute score for miner {miner_uid}: {e}")
                continue
            
            # Get all containers for this miner
            try:
                containers = self.get_containers_for_miner(miner_id)
                logger.info(f"Found {len(containers)} containers for miner {miner_id}")
            except Exception as e:
                logger.error(f"Error fetching containers for miner {miner_id}: {e}")
                continue
            
            # Process container data
            total_termination_time = 0
            rewarded_containers = 0
            container_payment_updates = []
            
            # Process each container
            for container in containers:
                container_id = container.get("id", "unknown")
                logger.info(f"Processing container: {container_id}")
                
                # Skip containers with missing required fields
                required_fields = ["created_at", "scheduled_termination", "status", "payment_status"]
                if not all(field in container for field in required_fields):
                    missing_fields = [field for field in required_fields if field not in container]
                    logger.warning(f"Container {container_id} missing required fields: {missing_fields}. Skipping.")
                    continue
                    
                # Skip if created_at or scheduled_termination is None
                if container["created_at"] is None or container["scheduled_termination"] is None:
                    logger.warning(f"Container {container_id} has null timestamp values. Skipping.")
                    continue
                
                # Check if container has expired
            # Calculate actual run time
                try:
                    actual_run_time = time_calculation(str(container["created_at"]),str(container["scheduled_termination"]))
                    logger.info(f"Actual run time for container {container_id}: {actual_run_time}")
                except Exception as e:
                    logger.error(f"Error calculating run time for container {container_id}: {e}")
                    continue
                        
            # Check if container is eligible for rewards
                if (container['status'] == 'terminated' and  container['payment_status'] == 'pending'):
                    total_termination_time += actual_run_time
                    rewarded_containers += 1
                    container_payment_updates.append(container_id)
                    logger.info(f"Container {container_id} eligible for reward. Total rewarded containers: {rewarded_containers}")    
            
            # Calculate final score after processing all containers for this miner
            logger.info(f"Completed container processing for miner {miner_uid}. Rewarded containers: {rewarded_containers}")
            
            if rewarded_containers > 0:
                try:
                    # Calculate average time across all rewarded containers
                    average_time = total_termination_time / rewarded_containers
                    
                    # Calculate final score using formula: (avg_time + total_time) * compute_score
                    final_score = (average_time + total_termination_time) * compute_score
                    
                    logger.info(f"Final score calculation for miner {miner_uid}:")
                    logger.info(f"  - Average time: {average_time}")
                    logger.info(f"  - Total time: {total_termination_time}")
                    logger.info(f"  - Compute score: {compute_score}")
                    logger.info(f"  - Final score: {final_score}")
                    
                    # Store the result
                    results[miner_uid] = final_score
                    
                    # Update payment status for all rewarded containers
                    update_results = []
                    for container_id in container_payment_updates:
                        logger.info(f"Updating payment status for container {container_id}...")
                        success = self.update_container_payment_status(container_id)
                        update_results.append((container_id, success))
                    
                    # Log the results of the updates
                    successful_updates = [container_id for container_id, success in update_results if success]
                    failed_updates = [container_id for container_id, success in update_results if not success]
                    
                    if successful_updates:
                        logger.info(f"Successfully updated payment status for containers: {successful_updates}")
                    if failed_updates:
                        logger.warning(f"Failed to update payment status for containers: {failed_updates}")
                    
                except Exception as e:
                    logger.error(f"Error calculating final score for miner {miner_uid}: {e}")
            else:
                logger.info(f"No rewarded containers for miner {miner_uid}, skipping score calculation")
        
        # Log final results before returning
        logger.info(f"Final results for all miners: {results}")
        return results


        
    
    def update_container_payment_status(self, container_id: str) -> bool:
        """
        Update the payment status of a container using the PATCH method with the direct multi-field endpoint.
        
        Args:
            container_id (str): The ID of the container to update.
            
        Returns:
            bool: True if the update is successful, False otherwise.
        """
        api_endpoint = f"https://orchestrator-gekh.onrender.com/api/v1/containers/direct/{container_id}/multi"
        
        try:
            # Prepare the request payload according to the expected format
            payload = {
                "fields": {
                    "payment_status": "completed"
                }
            }
            
            # Set the headers for the request
            headers = {
                "Content-Type": "application/json"
            }
            
            # Send the PATCH request
            response = requests.patch(api_endpoint, json=payload, headers=headers)
            
            # Check for successful update
            if response.status_code == 200:
                logger.info(f"Successfully updated payment status for container {container_id}.")
                return True
            else:
                logger.error(f"Failed to update payment status for container {container_id}. "
                            f"Status code: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error while updating payment status for container {container_id}: {e}")
            return False

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
            #logger.info(f"{miner} resources {miner_resources} ")
            ssh_info = self.extract_ssh_and_password(miner_resources)
            if "error" not in ssh_info:
                ssh_string = ssh_info["ssh_string"]
                password = ssh_info["password"]
                result = fetch_compute_specs(ssh_string, password)
                pog_score = compare_compute_resources(result, miner_resources[0])
                if pog_score["score"] >= 15:
                    logger.info(f"{miner} current resources  {result} ")
                    logger.info(f"{miner} scores {pog_score} ")
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

    async def update_validator_weights(self, results):
        """
        Updates validator weights using DTAO mechanics, ensuring proper normalization.
        
        Args:
            results (Dict[int, float]): A dictionary mapping miner UIDs to scores.
        """
        logger.info("Starting update_validator_weights...")
        try:
            if not results:
                logger.warning("No results to process. Skipping weight update.")
                return
            
            # Fetch subnet prices for DTAO weighting
            subnet_prices = {}
            try:
                async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                    for netuid in self.metagraph.uids:
                        try:
                            # Convert NumPy int64 to Python int explicitly
                            python_netuid = int(netuid)
                            # Now fetch the subnet with the Python int
                            subnet_info = await sub.subnet(python_netuid)
                            subnet_prices[python_netuid] = float(subnet_info.price)
                        except Exception as e:
                            logger.warning(f"Error fetching price for subnet {netuid}: {e}")
                            continue
            except Exception as e:
                logger.error(f"Error initializing AsyncSubtensor: {e}")
                return
            
            if not subnet_prices:
                logger.error("Failed to fetch any subnet prices. Cannot update weights.")
                return
            
            # Normalize subnet prices
            total_weight = sum(subnet_prices.values())
            if total_weight == 0:
                logger.error("Total subnet price weight is zero. Cannot normalize.")
                return
            normalized_prices = {uid: price / total_weight for uid, price in subnet_prices.items()}
            
            # Compute final scores by weighting results with subnet prices
            weighted_scores = {}
            for uid in results:
                python_uid = int(uid)  # Convert to Python int if it's a NumPy type
                normalized_price = normalized_prices.get(python_uid, 0)
                score = results.get(python_uid, 0)
                weighted_scores[python_uid] = score * normalized_price
            
            if not weighted_scores:
                logger.warning("No weighted scores calculated. Skipping weight update.")
                return
            logger.info(f"Weighted scores: {weighted_scores}")
            weights, uids = convert_weights_and_uids_for_emit(weighted_scores)
            
            # Convert to NumPy arrays for processing
        
            # Normalize weights to sum to 1
            norm = np.linalg.norm(weights, ord=1)
            if norm > 0:
                weights /= norm
            else:
                logger.warning("Weights sum to zero, using uniform distribution instead.")
                weights = np.ones_like(weights) / len(weights) if len(weights) > 0 else weights
            
            logger.info(f"Final processed weights: {weights}")
            logger.info(f"Final processed UIDs: {uids}")
            
            # Set weights using DTAO mechanism
            success = process_weights_for_netuid(
                weights=weights.tolist(),
                uids=uids, 
                netuid=self.config.netuid, 
                subtensor=self.subtensor,
                wallet=self.wallet
            )
            
            if success:
                logger.info("Validator weights updated successfully.")
            else:
                logger.error("Failed to update validator weights.")
        except Exception as e:
            logger.error(f"Exception in update_validator_weights: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def forward(self):
        try:
            await self.update_validator_weights()
        except Exception as e:
            bt.logging.error(f"Error in forward loop: {e}")
    def run(self):
        try:
            while not self.should_exit:
                self.loop.run_until_complete(self.forward())
                asyncio.sleep(300)
        except KeyboardInterrupt:
            bt.logging.success("Validator killed by keyboard interrupt.")
        except Exception as e:
            bt.logging.error(f"Error during validation: {e}")

if __name__ == "__main__":
    async def main():
        async with PolarisNode() as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await asyncio.sleep(300)
    asyncio.run(main())

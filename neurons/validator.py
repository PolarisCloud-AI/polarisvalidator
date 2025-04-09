import time
import json
import requests
import torch
import bittensor as bt
from template.base.validator import BaseValidatorNeuron
import asyncio
import uuid
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
from utils.pogs import execute_ssh_tasks, compare_compute_resources, compute_resource_score,time_calculation
from utils.uptimedata import calculate_miner_rewards,send_reward_log

if not logger._core.handlers:  # Prevent duplicate sinks
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
        balance = self.subtensor.get_balance(self.wallet.hotkey.ss58_address)
        logger.info(f"Wallet balance: {balance}")
        self.instance_id = str(uuid.uuid4())[:8]  # Unique ID for this instance
        logger.info(f"Initializing PolarisNode instance {self.instance_id}")
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        self.thread = None

    def load_state(self):
        """Loads the saved state of the validator from a file."""
        try:
            logger.info("Loading validator state.")
            with open(self.config.neuron.full_path + "/state.json", "r") as f:
                state = json.load(f)
                self.step = state["step"]
                self.scores = np.array(state["scores"], dtype=np.float32)
                self.hotkeys = state["hotkeys"]
        except FileNotFoundError:
            logger.warning("No previous state found. Starting fresh.")
    
    def save_state(self):
        """Saves the current state of the validator to a file."""
        try:
            logger.info("Saving validator state.")
            state = {
                "step": getattr(self, "step", 0),
                "scores": self.scores.tolist(),
                "hotkeys": self.hotkeys
            }
            os.makedirs(self.config.neuron.full_path, exist_ok=True)
            with open(self.config.neuron.full_path + "/state.json", "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

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
            # Check if UID 234 is valid
            
            return [int(uid) for uid in self.metagraph.uids]
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    async def verify_miners_loop(self):
        """Continuously verify miners in a separate async loop."""
        while True:
            logger.info("Starting verify_miners_loop...")
            miners = self.get_registered_miners()

            logger.info(f"Registered miners retrieved {len(miners)}")
            bittensor_miners = self.get_filtered_miners(miners)
            logger.info(f"Bittensor miners retrieved {len(bittensor_miners)}")
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
                results, container_updates, uptime_rewards_dict = await self.process_miners(miners, miner_resources)
                logger.info(f"Validation results: {results}")

                # Step 5: Directly update validator weights with results
                if results:
                    logger.info("Calling update_validator_weights() with results...")
                    await self.update_validator_weights(results, container_updates, uptime_rewards_dict)                    
                    logger.info("Finished calling update_validator_weights()")
                else:
                    logger.warning("No results to process. Skipping update_validator_weights.")
                # Step 6: Sleep before next iteration
                logger.info("Sleeping for 1 hour ...")
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in process_miners_loop: {e}")

    
    def get_filtered_miners(self, allowed_uids: List[int]) -> Dict[str, str]:
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
            if response.status_code == 200:
                miners_data = response.json()
                return {
                    miner["miner_id"]: miner["miner_uid"]
                    for miner in miners_data 
                    if miner["miner_uid"] is not None and int(miner["miner_uid"]) in allowed_uids
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
                            "miner_uid": miner_commune_map.get(miner["id"])
                        }
                        for miner in miners_data
                        if miner["status"] == "verified" and miner["id"] in miner_commune_map
                    }
                else:
                    logger.error(f"Failed to fetch miners. Status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching miner list with resources: {e}")
            return {}
    def get_unverified_miners(self) -> Dict[str, Dict]:
        """
        Fetch unverified miners from the orchestrator API.
        Returns a dictionary where keys are miner IDs and values are their compute resources.
        Only includes miners with status 'pending_verification'.
        """
        try:
            response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
            if response.status_code == 200:
                miners_data = response.json()
                return {
                    miner["id"]: miner.get("compute_resources", {})
                    for miner in miners_data
                    if miner.get("status") == "pending_verification"
                }
            else:
                print(f"[ERROR] Failed to fetch miners. Status code: {response.status_code}")
        except Exception as e:
            print(f"[EXCEPTION] Error fetching miner list: {e}")
        
        return {}
    
    def update_miner_status(self,miner_id,status,percentage):
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
            "status": status
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
    
    async def process_miners(self, miners: List[int], miner_resources: Dict) -> tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
        """
        Process miners and calculate their scores. Collect container updates and uptime rewards without applying them yet.
        
        Args:
            miners: List of miner UIDs to process
            miner_resources: Dictionary mapping miner IDs to their resource information
            
        Returns:
            Tuple of (results: Dict[int, float], container_updates: Dict[int, List[str]], uptime_rewards_dict: Dict[int, Dict])
            - results: Miner UIDs to their calculated scores
            - container_updates: Miner UIDs to lists of container IDs eligible for payment updates
            - uptime_rewards_dict: Miner UIDs to their uptime reward data
        """
        results = {}
        container_updates = {}
        uptime_rewards_dict = {}
        subnet_to_miner_map = {int(info["miner_uid"]): miner_id for miner_id, info in miner_resources.items()}
        active_miners = list(subnet_to_miner_map.keys())
        
        for miner_uid in miners:
            if miner_uid not in active_miners:
                logger.debug(f"Miner {miner_uid} is not active. Skipping...")
                continue
            miner_id = subnet_to_miner_map.get(miner_uid)
            if not miner_id:
                logger.warning(f"No miner_id found for miner_uid {miner_uid}")
                continue
            miner_info = miner_resources.get(miner_id)
            if not miner_info:
                logger.warning(f"No resource info found for miner_id {miner_id}")
                continue
            try:
                compute_score = compute_resource_score(miner_info["compute_resources"][0])
                logger.info(f"Compute score for miner {miner_uid}: {compute_score}")
            except (KeyError, IndexError, Exception) as e:
                logger.error(f"Error calculating compute score for miner {miner_uid}: {e}")
                continue
            try:
                uptime_rewards = calculate_miner_rewards(miner_id, compute_score)
                logger.info(f"Miner {miner_id} uptime reward: {uptime_rewards['reward_amount']}")
                uptime_rewards_dict[miner_uid] = uptime_rewards
            except (KeyError, IndexError, Exception) as e:
                logger.error(f"Error calculating uptime rewards for miner {miner_uid}: {e}")
                continue
            try:
                containers = self.get_containers_for_miner(miner_id)
                logger.info(f"Found {len(containers)} containers for miner {miner_id}")
            except Exception as e:
                logger.error(f"Error fetching containers for miner {miner_id}: {e}")
                continue
            
            total_termination_time = 0
            rewarded_containers = 0
            container_payment_updates = []
            
            for container in containers:
                container_id = container.get("id", "unknown")
                logger.info(f"Processing container: {container_id}")
                required_fields = ["created_at", "scheduled_termination", "status", "payment_status"]
                if not all(field in container for field in required_fields):
                    missing_fields = [field for field in required_fields if field not in container]
                    logger.warning(f"Container {container_id} missing required fields: {missing_fields}. Skipping.")
                    continue
                if container["created_at"] is None or container["scheduled_termination"] is None:
                    logger.warning(f"Container {container_id} has null timestamp values. Skipping.")
                    continue
                try:
                    actual_run_time = time_calculation(str(container["created_at"]), str(container["scheduled_termination"]))
                    logger.info(f"Actual run time for container {container_id}: {actual_run_time}")
                except Exception as e:
                    logger.error(f"Error calculating run time for container {container_id}: {e}")
                    continue
                if container['status'] == 'terminated' and container['payment_status'] == 'pending':
                    total_termination_time += actual_run_time
                    rewarded_containers += 1
                    container_payment_updates.append(container_id)
                    logger.info(f"Container {container_id} eligible for reward. Total rewarded: {rewarded_containers}")
            
            logger.info(f"Completed container processing for miner {miner_uid}. Rewarded containers: {rewarded_containers}")
            
            if rewarded_containers > 0:
                try:
                    average_time = total_termination_time / rewarded_containers
                    final_score = ((average_time + total_termination_time) * compute_score) + uptime_rewards["reward_amount"]
                    logger.info(f"Final score for miner {miner_uid}: {final_score}")
                    results[miner_uid] = final_score
                    container_updates[miner_uid] = container_payment_updates
                except Exception as e:
                    logger.error(f"Error calculating final score for miner {miner_uid}: {e}")
            else:
                if uptime_rewards["reward_amount"] > 0:
                    results[miner_uid] = uptime_rewards["reward_amount"]
                    container_updates[miner_uid] = []  # No containers to update, but include in dict
        
        logger.info(f"Final results: {results}")
        logger.info(f"Container updates collected: {container_updates}")
        logger.info(f"Uptime rewards collected: {uptime_rewards_dict}")
        return results, container_updates, uptime_rewards_dict

    
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

    async def verify_miners(self, miners):
        logger.info(f"Verifying miners........")
        
        # Fetch unverified miners once before the loop
        all_unverified_miners = self.get_unverified_miners()
        logger.info(f"Fetched all unverified miners' compute resources.")

        for miner in miners:
            logger.info(f"Processing miner {miner}")
            try:
                # Get compute resources for this specific miner
                miner_resources = all_unverified_miners.get(miner)

                if miner_resources is None:
                    logger.debug(f"Miner {miner} is not in pending verification. Skipping...")
                    continue

                logger.info(f"Found resources for miner {miner}: {miner_resources}")
                
                if not miner_resources:
                    logger.warning(f"No resources found for miner {miner}. Skipping...")
                    continue

                # Execute SSH tasks to verify the miner
                result = execute_ssh_tasks(miner)
                logger.info(f"{result}")
                
                if result and "task_results" in result:
                    specs = result["task_results"]
                    logger.info(f"SSH task results for miner {miner}: {specs}")
                    
                    # Compare claimed vs. actual resources
                    pog_score = compare_compute_resources(specs, miner_resources[0])
                    logger.info(f"Miner {miner} pog_score: {pog_score}")
                    
                    if pog_score["percentage"] >= 30:
                        logger.info(f"Miner {miner} is verified with score {pog_score['percentage']}%")
                        self.update_miner_status(miner, "verified", pog_score["percentage"])
                    else:
                        logger.info(f"Miner {miner} failed verification with score {pog_score['percentage']}%")
                        self.update_miner_status(miner, "rejected", pog_score["percentage"])
                else:
                    logger.warning(f"Failed to execute SSH tasks for miner {miner}")
                    self.update_miner_status(miner, "rejected", 0.0)
            except Exception as e:
                logger.error(f"Error processing miner {miner}: {e}")
                try:
                    self.update_miner_status(miner, "rejected", 0.0)
                except Exception as update_error:
                    logger.error(f"Failed to update status for miner {miner}: {update_error}")


    
    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def setup(self):
        self.load_state()
        if not hasattr(self, '_tasks_scheduled'):
            asyncio.create_task(self.verify_miners_loop())
            asyncio.create_task(self.process_miners_loop())
            self._tasks_scheduled = True
        logger.info("Setup completed")
    
    async def cleanup(self):
        pass
    
    def track_tokens(self,miner_uid: str, tokens: float, validator: str, platform: str):
        """
        Sends a POST request to the scores/add API to track tokens rewarded to miners.

        Args:
            miner_uid (str): The UID of the miner being rewarded.
            tokens (float): The number of tokens rewarded.
            validator (str): The validator issuing the reward.
            platform (str): The platform associated with the reward.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        url = "https://orchestrator-gekh.onrender.com/api/v1/scores/add"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "id": str(uuid.uuid4()),  # Generate a unique ID
            "miner_uid": miner_uid,
            "tokens": float(tokens),
            "date_received": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),  # Current UTC time
            "validator": validator,
            "platform": platform,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())  # Current UTC time
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Successfully tracked tokens for miner {miner_uid}.")
                return True
            else:
                logger.error(f"Failed to track tokens for miner {miner_uid}. "
                            f"Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error while tracking tokens for miner {miner_uid}: {e}")
            return False

    async def update_validator_weights(self, results: Dict[int, float], container_updates: Dict[int, List[str]], uptime_rewards_dict: Dict[int, Dict]):
        """Update validator weights and apply container updates only if weights are set successfully."""
        logger.info("Starting update_validator_weights...")
        try:
            if not results:
                logger.warning("No results to process. Skipping weight update.")
                return
            subnet_price = 0.0
            try:
                async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                    subnet_info = await sub.subnet(self.config.netuid)
                    subnet_price = float(subnet_info.price) if subnet_info else 0.0
            except Exception as e:
                logger.error(f"Error fetching price for netuid {self.config.netuid}: {e}")
                return
            if subnet_price <= 0:
                logger.warning(f"Subnet price for netuid {self.config.netuid} is zero or invalid.")
                weighted_scores = {int(uid): float(score) for uid, score in results.items()}
            else:
                weighted_scores = {int(uid): float(score) * subnet_price for uid, score in results.items()}
            if not weighted_scores:
                logger.warning("No weighted scores calculated. Skipping weight update.")
                return
            logger.info(f"Weighted scores: {weighted_scores}")
            weights, uids = convert_weights_and_uids_for_emit(weighted_scores)
            weights = np.array(weights, dtype=np.float32)
            norm = np.linalg.norm(weights, ord=1)
            if norm > 0:
                weights /= norm
            else:
                logger.warning("Weights sum to zero, using uniform distribution.")
                weights = np.ones_like(weights) / len(weights) if len(weights) > 0 else weights
            logger.info(f"Final processed weights: {weights}")
            logger.info(f"Final processed UIDs: {uids}")
            
            success = process_weights_for_netuid(
                weights=weights.tolist(),
                uids=uids,
                netuid=self.config.netuid,
                subtensor=self.subtensor,
                wallet=self.wallet
            )
            
            if success:
                logger.info("Validator weights updated successfully.")
                self.save_state()
                # Update container payment statuses
                for uid in container_updates:
                    container_ids = container_updates[uid]
                    for container_id in container_ids:
                        if not self.update_container_payment_status(container_id):
                            logger.warning(f"Failed to update payment status for container {container_id}")
                    # Send reward log if there are uptime rewards
                    if uid in uptime_rewards_dict and uptime_rewards_dict[uid]["reward_amount"] > 0:
                        send_reward_log(uptime_rewards_dict[uid])
                        logger.info(f"Sent reward log for miner {uid}")
                # Track tokens
                for uid, weight in zip(uids, weights):
                    if weight > 0:
                        track_success = self.track_tokens(str(uid), weight, self.wallet.hotkey_str, "Bittensor")
                        if not track_success:
                            logger.warning(f"Failed to track tokens for miner {uid}.")
            else:
                logger.warning("Failed to update validator weights. Skipping container updates and reward logs.")
        except Exception as e:
            logger.error(f"Exception in update_validator_weights: {e}")

    async def forward(self):
        try:
            await self.update_validator_weights({}, {}, {})
        except Exception as e:
            logger.error(f"Error in forward loop: {e}")
    

    def run(self):
        try:
            self.loop.run_forever()  # Just run the event loop for tasks scheduled in setup
        except KeyboardInterrupt:
            logger.success("Validator killed by keyboard interrupt.")
        except Exception as e:
            logger.error(f"Error during validation: {e}")
    

if __name__ == "__main__":
    async def main():
        async with PolarisNode() as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await asyncio.sleep(300)
    asyncio.run(main())

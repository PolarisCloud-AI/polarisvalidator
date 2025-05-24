# Fixed Polaris Validator Implementation
# Addresses all critical issues identified in the analysis

import asyncio
import uuid
import numpy as np
import bittensor as bt
import copy
import time
import os
import json
from loguru import logger
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from template.base.validator import BaseValidatorNeuron
from template.base.utils.weight_utils import (
    convert_weights_and_uids_for_emit,
    process_weights_for_netuid
)
from utils.api_utils import (
    get_filtered_miners,
    get_miner_list_with_resources,
    get_containers_for_miner,
    get_unverified_miners,
    get_filtered_miners_val,
    update_miner_status,
    filter_miners_by_id
)
from utils.validator_utils import process_miners, verify_miners
from utils.state_utils import load_state, save_state
from gpu_proof_of_work import GPUProofOfWork, ValidationResult


class PolarisNode(BaseValidatorNeuron):
    """Fixed Polaris Validator with corrected scoring logic and GPU validation"""
    
    def __init__(self, config=None):
        super().__init__(config=config)
        self.max_allowed_weights = 500
        self.hotkeys = self.metagraph.hotkeys.copy()
        self.dendrite = bt.dendrite(wallet=self.wallet)
        
        # Initialize scoring system with proper defaults
        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
        self.score_history = {}  # Track historical performance
        self.score_decay = 0.95  # Increased decay for better stability
        self.min_score_threshold = 0.01  # Minimum score to maintain
        
        # GPU validation system
        self.gpu_validator = GPUProofOfWork()
        self.validation_cache = {}  # Cache validation results
        self.validation_frequency = 100  # Blocks between validations
        self.last_validation_block = {}  # Track last validation for each miner
        
        # Performance tracking
        self.miner_performance = {}  # Track detailed miner performance
        self.performance_window = 24 * 60 * 60  # 24 hour window
        
        # Configuration
        balance = self.subtensor.get_balance(self.wallet.hotkey.ss58_address)
        logger.info(f"Wallet balance: {balance}")
        
        self.instance_id = str(uuid.uuid4())[:8]
        logger.info(f"Initializing PolarisNode instance {self.instance_id}")
        
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        
        # Blockchain parameters
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.weights_rate_limit = self.tempo
        self.last_weight_update_block = 0
        self._tasks_scheduled = False
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay_base = 5
        self.step = 0
        
        # Subnet configuration
        self.default_subnet_price = 1.0
        
        # Initialize cluster configuration
        self._init_cluster_config()
        
        logger.info(f"PolarisNode initialized with improved scoring and GPU validation")
        
    def _init_cluster_config(self):
        """Initialize cluster configuration with proper validation"""
        try:
            # Handle miner_cluster_id configuration properly
            miner_cluster_id = None
            
            # Check direct config attribute
            if hasattr(self.config, 'miner_cluster_id'):
                miner_cluster_id = self.config.miner_cluster_id
            # Check neuron config attribute
            elif hasattr(self.config, 'neuron') and hasattr(self.config.neuron, 'miner_cluster_id'):
                miner_cluster_id = self.config.neuron.miner_cluster_id
            
            # Validate and convert to int
            if miner_cluster_id is not None:
                try:
                    miner_cluster_id = int(miner_cluster_id)
                    if miner_cluster_id not in range(4):
                        logger.warning(f"Invalid cluster ID {miner_cluster_id}, using default 0")
                        miner_cluster_id = 0
                except (ValueError, TypeError):
                    logger.warning(f"Invalid cluster ID format, using default 0")
                    miner_cluster_id = 0
            else:
                miner_cluster_id = 0
            
            # Set cluster ranges
            cluster_ranges = {
                0: (0, 63),
                1: (64, 127),
                2: (128, 191),
                3: (192, 255)
            }
            
            self.config.uid_start, self.config.uid_end = cluster_ranges[miner_cluster_id]
            logger.info(f"Using cluster {miner_cluster_id}: UIDs {self.config.uid_start}-{self.config.uid_end}")
            
        except Exception as e:
            logger.error(f"Error initializing cluster config: {e}")
            # Fallback to full range
            self.config.uid_start, self.config.uid_end = 0, 255

    def calculate_cpu_score(self, cpu_info: Dict) -> float:
        """Calculate CPU score based on actual logical threads (FIXED)"""
        try:
            # Extract CPU information
            cores = cpu_info.get('cores', 1)
            threads_per_core = cpu_info.get('threads_per_core', 1)
            clock_speed = cpu_info.get('clock_speed_ghz', 2.0)
            
            # FIXED: Calculate logical threads correctly
            # Do NOT multiply by sockets - that's already included in core count
            logical_threads = cores * threads_per_core
            
            # Score based on threads and clock speed
            # This gives a more reasonable range
            base_score = logical_threads * clock_speed
            
            # Apply logarithmic scaling to prevent extreme advantages
            # log1p is log(1 + x) to handle zero gracefully
            scaled_score = np.log1p(base_score) * 10
            
            # Cap at 100 to normalize scores
            final_score = min(scaled_score, 100)
            
            logger.debug(f"CPU Score: {cores} cores × {threads_per_core} threads × {clock_speed} GHz = "
                        f"{logical_threads} threads, base_score={base_score:.2f}, "
                        f"scaled={scaled_score:.2f}, final={final_score:.2f}")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating CPU score: {e}")
            return 1.0  # Minimum score on error

    def save_state(self):
        """Saves the validator state"""
        try:
            state_data = {
                'scores': self.scores.tolist(),
                'score_history': self.score_history,
                'last_weight_update_block': self.last_weight_update_block,
                'step': self.step,
                'miner_performance': self.miner_performance,
                'validation_cache': self.validation_cache,
                'last_validation_block': self.last_validation_block
            }
            save_state(self, state_data)
            logger.info("Validator state saved successfully")
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def load_state(self):
        """Loads the validator state"""
        try:
            state_data = load_state(self)
            if state_data:
                self.scores = np.array(state_data.get('scores', []))
                if len(self.scores) != self.metagraph.n:
                    self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
                
                self.score_history = state_data.get('score_history', {})
                self.last_weight_update_block = state_data.get('last_weight_update_block', 0)
                self.step = state_data.get('step', 0)
                self.miner_performance = state_data.get('miner_performance', {})
                self.validation_cache = state_data.get('validation_cache', {})
                self.last_validation_block = state_data.get('last_validation_block', {})
                
            logger.info("Validator state loaded successfully")
        except Exception as e:
            logger.error(f"Error loading state: {e}")

    def resync_metagraph(self):
        """Resyncs the metagraph and updates related state"""
        logger.info("Resyncing metagraph...")
        previous_metagraph = copy.deepcopy(self.metagraph)
        self.metagraph.sync(subtensor=self.subtensor)
        
        # Update blockchain parameters
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.weights_rate_limit = self.get_weights_rate_limit()
        
        # Check if metagraph actually changed
        if previous_metagraph.axons == self.metagraph.axons:
            return
            
        logger.info("Metagraph updated, re-syncing hotkeys and scores")
        
        # Update scores array size if needed
        if len(self.scores) != self.metagraph.n:
            new_scores = np.zeros(self.metagraph.n, dtype=np.float32)
            # Copy existing scores
            min_len = min(len(self.scores), self.metagraph.n)
            new_scores[:min_len] = self.scores[:min_len]
            self.scores = new_scores
        
        # Reset scores for changed hotkeys
        for uid, hotkey in enumerate(self.metagraph.hotkeys):
            if uid < len(self.hotkeys) and hotkey != self.hotkeys[uid]:
                self.scores[uid] = 0
                # Clear history for changed miners
                if str(uid) in self.score_history:
                    del self.score_history[str(uid)]
        
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
        self.save_state()

    def get_registered_miners(self) -> List[int]:
        """Returns a list of registered miner UIDs"""
        try:
            self.metagraph.sync()
            return [int(uid) for uid in self.metagraph.uids]
        except Exception as e:
            logger.error(f"Error fetching registered miners: {e}")
            return []

    def get_weights_rate_limit(self):
        """Fetches the weights rate limit from the blockchain"""
        try:
            node = self.subtensor.substrate
            result = node.query("SubtensorModule", "WeightsSetRateLimit", [self.config.netuid])
            return result.value
        except Exception as e:
            logger.error(f"Error fetching weights rate limit: {e}")
            return self.tempo

    def get_last_update(self):
        """Fetches the number of blocks since the last weight update"""
        try:
            node = self.subtensor.substrate
            my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            last_update = node.query("SubtensorModule", "LastUpdate", [self.config.netuid]).value
            
            if last_update and my_uid < len(last_update):
                blocks_since = self.subtensor.block - last_update[my_uid]
                logger.info(f"Last update was {blocks_since} blocks ago")
                return blocks_since
            
            return 1000  # Default to allow update
        except Exception as e:
            logger.error(f"Error fetching last update: {e}")
            return 1000

    def check_registered(self):
        """Checks if the validator is registered on the subnet"""
        try:
            is_registered = self.subtensor.is_hotkey_registered(
                netuid=self.config.netuid,
                hotkey_ss58=self.wallet.hotkey.ss58_address,
            )
            if not is_registered:
                logger.error(f"Validator {self.wallet.hotkey.ss58_address} is not registered on netuid {self.config.netuid}")
            else:
                logger.info("Validator is registered")
            return is_registered
        except Exception as e:
            logger.error(f"Error checking registration: {e}")
            return False

    def is_chain_synced(self):
        """Checks if the chain is synced"""
        try:
            current_block = self.subtensor.block
            return current_block > 0
        except Exception as e:
            logger.error(f"Error checking chain sync: {e}")
            return False

    async def is_subnet_ready_for_weights(self) -> bool:
        """Checks if the subnet is ready for weight updates"""
        try:
            current_block = self.subtensor.block
            self.tempo = self.subtensor.tempo(self.config.netuid)
            weights_rate_limit = self.get_weights_rate_limit()
            
            # Calculate blocks since last update
            blocks_since_last_update = current_block - self.last_weight_update_block
            last_update_from_chain = self.get_last_update()
            
            # Use the larger of tempo and weights rate limit
            effective_rate_limit = max(self.tempo, weights_rate_limit)
            
            # Check chain sync
            if not self.is_chain_synced():
                logger.warning("Subtensor not synced with chain")
                return False
            
            # Check both internal and chain readiness
            is_ready_internal = blocks_since_last_update >= effective_rate_limit
            is_ready_chain = last_update_from_chain >= effective_rate_limit
            
            # Need both to be ready (unless chain returns default 1000)
            if not is_ready_internal or (last_update_from_chain != 1000 and not is_ready_chain):
                logger.info(f"Not ready for weights - Internal: {blocks_since_last_update}/{effective_rate_limit}, "
                           f"Chain: {last_update_from_chain}/{effective_rate_limit}")
                return False
            
            logger.info(f"Ready for weights - Internal: {blocks_since_last_update}/{effective_rate_limit}, "
                       f"Chain: {last_update_from_chain}/{effective_rate_limit}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking subnet readiness: {e}")
            return False

    async def update_validator_weights(self, results: Dict[int, float], 
                                     container_updates: Dict[int, List[str]], 
                                     uptime_rewards_dict: Dict[int, Dict]):
        """FIXED: Updates validator weights with proper scoring logic"""
        logger.info("Starting update_validator_weights...")
        
        async with self.lock:
            try:
                # Validation checks
                if not results:
                    logger.warning("No results to process")
                    return
                
                if not self.check_registered():
                    logger.error("Validator not registered")
                    return
                
                if not await self.is_subnet_ready_for_weights():
                    logger.info("Subnet not ready for weight update")
                    return
                
                # Get subnet price
                subnet_price = await self._get_subnet_price()
                logger.info(f"Using subnet price: {subnet_price}")
                
                # FIXED: Apply decay to ALL scores first
                self.scores *= self.score_decay
                logger.info(f"Applied decay {self.score_decay}, sum before: {self.scores.sum():.4f}")
                
                # Remove scores below threshold
                below_threshold = self.scores < self.min_score_threshold
                self.scores[below_threshold] = 0
                logger.info(f"Removed {below_threshold.sum()} scores below threshold {self.min_score_threshold}")
                
                # FIXED: Update scores with new results (no max() function!)
                updated_count = 0
                for uid, score in results.items():
                    uid = int(uid)
                    if 0 <= uid < len(self.scores):
                        new_score = float(score) * subnet_price
                        
                        # Use weighted average with history for smoothing
                        uid_str = str(uid)
                        if uid_str in self.score_history and len(self.score_history[uid_str]) > 0:
                            # Weighted average: 30% historical, 70% new
                            historical_avg = np.mean(self.score_history[uid_str])
                            self.scores[uid] = 0.3 * historical_avg + 0.7 * new_score
                        else:
                            # No history, use new score directly
                            self.scores[uid] = new_score
                        
                        # Update history
                        if uid_str not in self.score_history:
                            self.score_history[uid_str] = []
                        
                        self.score_history[uid_str].append(self.scores[uid])
                        
                        # Keep only recent history (last 10 updates)
                        if len(self.score_history[uid_str]) > 10:
                            self.score_history[uid_str].pop(0)
                        
                        updated_count += 1
                
                logger.info(f"Updated {updated_count} miner scores")
                
                # Log score distribution
                non_zero_scores = self.scores[self.scores > 0]
                if len(non_zero_scores) > 0:
                    logger.info(f"Score distribution - Count: {len(non_zero_scores)}, "
                              f"Mean: {np.mean(non_zero_scores):.4f}, "
                              f"Std: {np.std(non_zero_scores):.4f}, "
                              f"Min: {np.min(non_zero_scores):.4f}, "
                              f"Max: {np.max(non_zero_scores):.4f}")
                    
                    # Log top 5 miners
                    top_indices = np.argsort(self.scores)[-5:][::-1]
                    top_scores = [(idx, self.scores[idx]) for idx in top_indices if self.scores[idx] > 0]
                    logger.info(f"Top 5 miners: {top_scores}")
                
                # Prepare weights for emission
                weighted_scores = {
                    str(uid): float(score) 
                    for uid, score in enumerate(self.scores) 
                    if score > self.min_score_threshold
                }
                
                if not weighted_scores:
                    logger.warning("No miners meet minimum score threshold")
                    return
                
                logger.info(f"Preparing to set weights for {len(weighted_scores)} miners")
                
                # Convert weights for emission
                weights, uids = convert_weights_and_uids_for_emit(weighted_scores)
                
                # Attempt weight update with retries
                success = await self._update_weights_with_retry(weights, uids)
                
                if success:
                    logger.success(f"✓ Weights updated successfully at block {self.subtensor.block}")
                    self.last_weight_update_block = self.subtensor.block
                    self.step += 1
                    # FIXED: Do NOT reset scores! Let decay handle the history
                    self.save_state()
                else:
                    logger.error("Failed to update weights after all retries")
                    
            except Exception as e:
                logger.error(f"Exception in update_validator_weights: {e}", exc_info=True)

    async def _get_subnet_price(self) -> float:
        """Get subnet price with proper error handling"""
        try:
            async with bt.AsyncSubtensor(network=self.config.subtensor.network) as sub:
                subnet_info = await sub.subnet(self.config.netuid)
                if subnet_info and hasattr(subnet_info, 'price') and subnet_info.price > 0:
                    return float(subnet_info.price)
        except Exception as e:
            logger.error(f"Error fetching subnet price: {e}")
        
        return self.default_subnet_price

    async def _update_weights_with_retry(self, weights: np.ndarray, uids: np.ndarray) -> bool:
        """Update weights with retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting weight update (attempt {attempt + 1}/{self.max_retries})")
                
                success = process_weights_for_netuid(
                    weights=weights,
                    uids=uids,
                    netuid=self.config.netuid,
                    subtensor=self.subtensor,
                    wallet=self.wallet
                )
                
                if success:
                    return True
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_base * (2 ** attempt)
                    logger.warning(f"Weight update failed, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Exception during weight update attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay_base)
        
        return False

    async def verify_miners_loop(self):
        """Periodically verifies miners"""
        allowed_uids = set(range(self.config.uid_start, self.config.uid_end + 1))
        
        while True:
            try:
                logger.info("Starting miner verification cycle")
                
                # Get registered miners in our range
                all_miners = self.get_registered_miners()
                eligible_miners = [m for m in all_miners if m in allowed_uids]
                
                if not eligible_miners:
                    logger.warning(f"No eligible miners in range {self.config.uid_start}-{self.config.uid_end}")
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"Verifying {len(eligible_miners)} miners")
                
                # Get miners to verify
                bittensor_miners, miners_to_reject = get_filtered_miners(eligible_miners)
                
                if bittensor_miners:
                    logger.info(f"Verifying {len(bittensor_miners)} Bittensor miners")
                    await verify_miners(
                        list(bittensor_miners.keys()), 
                        get_unverified_miners, 
                        update_miner_status
                    )
                
                # Sleep before next verification cycle
                await asyncio.sleep(400)
                
            except Exception as e:
                logger.error(f"Error in verify_miners_loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def process_miners_loop(self):
        """FIXED: Periodically processes miners with GPU validation"""
        allowed_uids = set(range(self.config.uid_start, self.config.uid_end + 1))
        logger.info(f"Processing miners in UID range: {self.config.uid_start}-{self.config.uid_end}")
        
        while True:
            try:
                cycle_start = time.time()
                logger.info("=" * 60)
                logger.info("Starting miner processing cycle")
                
                # Get registered miners
                all_miners = self.get_registered_miners()
                eligible_miners = [m for m in all_miners if m in allowed_uids]
                
                if not eligible_miners:
                    logger.warning("No eligible miners found")
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"Found {len(eligible_miners)} eligible miners")
                
                # Get miner information
                white_list = get_filtered_miners_val(eligible_miners)
                bittensor_miners = filter_miners_by_id(white_list)
                miner_resources = get_miner_list_with_resources(bittensor_miners)
                
                logger.info(f"Got resources for {len(miner_resources)} miners")
                
                # Perform GPU validation for miners
                if self.gpu_validator.enabled:
                    logger.info("Performing GPU validation...")
                    validation_results = await self._validate_miners_gpu(eligible_miners)
                    logger.info(f"GPU validation completed for {len(validation_results)} miners")
                else:
                    validation_results = {}
                
                # Process miners and calculate base scores
                results, container_updates, uptime_rewards = await process_miners(
                    miners=eligible_miners,
                    miner_resources=miner_resources,
                    get_containers_func=get_containers_for_miner,
                    update_status_func=update_miner_status,
                    tempo=self.tempo,
                    max_score=self.max_allowed_weights
                )
                
                # Apply GPU validation adjustments
                if validation_results:
                    for uid, validation in validation_results.items():
                        if uid in results and validation.score > 0:
                            # Multiply base score by GPU validation score
                            original_score = results[uid]
                            results[uid] *= validation.score
                            logger.debug(f"Miner {uid}: base_score={original_score:.4f}, "
                                       f"gpu_score={validation.score:.4f}, "
                                       f"final={results[uid]:.4f}")
                
                # Update weights
                await self.update_validator_weights(results, container_updates, uptime_rewards)
                
                # Calculate sleep time
                sleep_time = self._calculate_sleep_time()
                cycle_duration = time.time() - cycle_start
                
                logger.info(f"Cycle completed in {cycle_duration:.1f}s, sleeping for {sleep_time}s")
                logger.info("=" * 60)
                
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in process_miners_loop: {e}", exc_info=True)
                logger.info("Sleeping for 60s after error")
                await asyncio.sleep(60)

    async def _validate_miners_gpu(self, miners: List[int]) -> Dict[int, ValidationResult]:
        """Validate miners' GPU hardware"""
        results = {}
        current_block = self.subtensor.block
        
        for miner_uid in miners:
            try:
                # Convert to string for cache keys
                uid_str = str(miner_uid)
                
                # Check if validation is needed
                last_validation = self.last_validation_block.get(uid_str, 0)
                blocks_since_validation = current_block - last_validation
                
                if blocks_since_validation < self.validation_frequency:
                    # Use cached result if available and recent
                    if uid_str in self.validation_cache:
                        results[miner_uid] = self.validation_cache[uid_str]
                        logger.debug(f"Using cached GPU validation for miner {miner_uid}")
                    continue
                
                logger.info(f"Performing GPU validation for miner {miner_uid}")
                
                # Perform GPU validation
                validation_result = await self.gpu_validator.validate_miner(
                    miner_uid=miner_uid,
                    dendrite=self.dendrite,
                    metagraph=self.metagraph
                )
                
                # Cache result
                self.validation_cache[uid_str] = validation_result
                self.last_validation_block[uid_str] = current_block
                results[miner_uid] = validation_result
                
                # Log validation result
                logger.info(f"GPU validation for miner {miner_uid}: "
                           f"score={validation_result.score:.4f}, "
                           f"type={validation_result.validation_type}")
                
            except Exception as e:
                logger.error(f"Error validating miner {miner_uid}: {e}")
                # Create failed validation result
                results[miner_uid] = ValidationResult(
                    uid=miner_uid,
                    score=0.0,
                    hardware_info={},
                    timestamp=datetime.now(),
                    validation_type='error'
                )
        
        return results

    def _calculate_sleep_time(self) -> int:
        """Calculate appropriate sleep time until next weight update"""
        try:
            current_block = self.subtensor.block
            blocks_since_last = current_block - self.last_weight_update_block
            effective_rate_limit = max(self.tempo, self.weights_rate_limit)
            
            # Calculate blocks until next allowed update
            blocks_remaining = max(0, effective_rate_limit - blocks_since_last)
            
            # Estimate time: ~12 seconds per block on Bittensor
            # Add buffer to avoid hitting rate limit exactly
            sleep_seconds = (blocks_remaining + 5) * 12
            
            # Minimum 60 seconds, maximum 10 minutes
            return max(60, min(sleep_seconds, 600))
            
        except Exception as e:
            logger.error(f"Error calculating sleep time: {e}")
            return 300  # Default 5 minutes

    async def setup(self):
        """Sets up the validator"""
        logger.info("Setting up validator...")
        
        # Load saved state
        self.load_state()
        
        # Schedule background tasks
        if not self._tasks_scheduled:
            asyncio.create_task(self.verify_miners_loop())
            asyncio.create_task(self.process_miners_loop())
            self._tasks_scheduled = True
            
        logger.info("Setup completed")

    async def cleanup(self):
        """Cleans up resources"""
        logger.info("Cleaning up validator...")
        self.save_state()
        self.should_exit = True

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def forward(self):
        """Handles forward pass (required by base class)"""
        # This is called by the base validator
        # We handle everything in our own loops
        pass

    def run(self):
        """Runs the validator loop"""
        try:
            logger.info(f"Starting Polaris validator on netuid {self.config.netuid}")
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.success("Validator stopped by keyboard interrupt")
        except Exception as e:
            logger.error(f"Error running validator: {e}", exc_info=True)
        finally:
            self.save_state()


if __name__ == "__main__":
    # Run the validator
    async def main():
        async with PolarisNode() as validator:
            logger.info("Polaris validator started successfully")
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await asyncio.sleep(300)
    
    asyncio.run(main())
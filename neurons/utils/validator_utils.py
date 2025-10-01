import asyncio
from typing import List, Callable, Dict, Any,Tuple
from loguru import logger
import numpy as np
import requests
import os
import tenacity
import time
from utils.api_utils import _get_cached_miners_data,sub_verification,reward_mechanism,aggregate_rewards
from utils.alpha_overselling_detector import AlphaOverSellingDetector
import asyncio
import bittensor as bt
import logging
logging.getLogger("websockets.client").setLevel(logging.WARNING)

async def process_miners(
    miners: List[int],
    tempo: int,
    max_score: float = 500.0,
    netuid: int = 49,
    network: str = "finney",
) -> Tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
    """
    Process miners and compute their rewards with robust error handling.

    Args:
        miners: List of miner IDs to process
        tempo: Tempo value for reward calculation
        max_score: Maximum score for reward calculation (default: 500.0)
        netuid: Network unique identifier (default: 49)
        network: Network name (default: "finney")

    Returns:
        Tuple containing total rewards, compute rewards, and uptime rewards

    Raises:
        ValueError: If input parameters are invalid
        RuntimeError: If critical operations fail
    """
    # Input validation (use original miners list for validation)
    if not isinstance(miners, list) or not all(isinstance(m, int) for m in miners):
        logger.error("Invalid miners list: must be a list of integers")
        raise ValueError("Miners must be a list of integers")
    
    if not isinstance(tempo, int) or tempo <= 0:
        logger.error(f"Invalid tempo value: {tempo}. Must be a positive integer")
        raise ValueError("Tempo must be a positive integer")
    
    if not isinstance(max_score, (int, float)) or max_score <= 0:
        logger.error(f"Invalid max_score: {max_score}. Must be a positive number")
        raise ValueError("max_score must be a positive number")
    
    if not isinstance(netuid, int):
        logger.error(f"Invalid netuid: {netuid}. Must be an integer")
        raise ValueError("netuid must be an integer")
    
    if not isinstance(network, str):
        logger.error(f"Invalid network: {network}. Must be a string")
        raise ValueError("network must be a string")

    # Initialize default return values in case of failure (use original miners only)
    default_rewards: Dict[int, float] = {miner: 0.0 for miner in miners}
    default_details: Dict[int, List[str]] = {miner: [] for miner in miners}
    default_metadata: Dict[int, Dict] = {miner: {} for miner in miners}
    default_return = (default_rewards, default_details, default_metadata)
    
    logger.info(f"Processing {len(miners)} miners for rewards")

    try:
        # Refresh cached miners data
        try:
            logger.info("🚀 VALIDATOR: Starting miner processing cycle - refreshing cache...")
            _get_cached_miners_data(force_refresh=True)
            logger.info("✅ VALIDATOR: Successfully refreshed cached miners data")
        except Exception as e:
            logger.warning(f"⚠️ VALIDATOR: Failed to refresh cached miners data: {e}")
            # Continue execution as cache refresh is not critical

        # Initialize subtensor connection
        current_block = 0
        try:
            subtensor = bt.subtensor(network=network)
            current_block = subtensor.get_current_block()
            logger.info(f"Current block number: {current_block}")
        except Exception as e:
            logger.error(f"Failed to initialize subtensor or fetch block: {e}")
            # Continue with default block number (0)

        # Calculate rewards
        try:
            compute_rewards, uptime_rewards = await reward_mechanism(
                allowed_uids=miners,  # Use original miners only
                netuid=netuid,
                network=network,
                tempo=tempo,
                max_score=max_score,
                current_block=current_block
            )
        except Exception as e:
            logger.error(f"Error in reward_mechanism: {e}")
            return default_return

        # Aggregate rewards
        try:
            total_rewards, cpu_gpu_breakdown = aggregate_rewards(compute_rewards, uptime_rewards)
            logger.info(f"Successfully processed miners rewards: {total_rewards}")
            logger.info(f"CPU/GPU breakdown available for {len(cpu_gpu_breakdown)} miners")
            
            # Apply alpha over-selling penalties with moving average
            try:
                # Initialize over-selling detector if not already done
                if not hasattr(process_miners, '_overselling_detector'):
                    process_miners._overselling_detector = AlphaOverSellingDetector(
                        netuid=netuid,
                        network=network
                    )
                    logger.info("Initialized AlphaOverSellingDetector with moving average")
                
                detector = process_miners._overselling_detector
                
                # Get metagraph for penalty detection
                try:
                    subtensor = bt.subtensor(network=network)
                    metagraph = bt.metagraph(netuid=netuid, subtensor=subtensor)
                    metagraph.sync(subtensor=subtensor)
                    
                    # Check for expired penalties
                    expired_uids = detector.check_penalty_expiration(current_block)
                    if expired_uids:
                        logger.info(f"⏰ ALPHA PENALTIES EXPIRED for UIDs: {expired_uids}")
                        logger.info(f"📋 EXPIRED PENALTY UIDs: {expired_uids}")
                    else:
                        logger.debug("No alpha penalties expired in this cycle")
                    
                    # Detect over-selling violations with moving average
                    violations = detector.detect_overselling_violations(metagraph)
                    if violations:
                        logger.warning(f"🚨 ALPHA OVER-SELLING DETECTED: {len(violations)} violations found")
                        
                        # Log all detected violations with moving average data
                        violation_uids = []
                        for violation in violations:
                            violation_uids.append(violation['uid'])
                            logger.warning(f"   UID {violation['uid']}: {violation['penalty_level']} violation "
                                         f"(stake decrease: {violation['stake_change_percent']:.1f}%, "
                                         f"moving avg deviation: {violation['moving_avg_change_percent']:.1f}%)")
                        
                        logger.warning(f"📋 VIOLATION UIDs: {violation_uids}")
                        
                        # Apply penalties
                        penalties = detector.apply_penalties(violations, current_block)
                        if penalties:
                            logger.warning(f"⚖️ ALPHA PENALTIES APPLIED: {len(penalties)} miners penalized")
                            
                            # Log detailed penalty information
                            penalized_uids = []
                            for uid, penalty_info in penalties.items():
                                penalized_uids.append(uid)
                                logger.warning(f"   UID {uid}: {penalty_info['penalty_level']} penalty "
                                             f"for {penalty_info['duration_hours']:.1f} hours "
                                             f"(score reduction: {penalty_info['score_reduction']*100:.0f}%)")
                            
                            logger.warning(f"📋 PENALIZED UIDs: {penalized_uids}")
                        else:
                            logger.info("⚠️ No penalties applied despite violations detected")
                    else:
                        logger.info("✅ No alpha over-selling violations detected")
                    
                    # Apply penalties to rewards and collect penalty losses
                    # Then implement CPU/GPU split logic
                    if total_rewards:
                        penalized_rewards, penalty_loss_for_uid_44 = detector.apply_penalties_to_scores(total_rewards, current_block)
                        
                        # Calculate 40% bonus from rewarded UIDs only (exclude penalized UIDs)
                        # We'll calculate this after processing the CPU/GPU split logic
                        
                        # Now implement the complex logic for CPU/GPU and penalties
                        final_rewards = {}
                        uid_44_cpu_collection = 0.0
                        uid_44_penalty_collection = penalty_loss_for_uid_44
                        
                        logger.info("\n" + "=" * 80)
                        logger.info("🎯 APPLYING CPU/GPU SPLIT AND PENALTY LOGIC")
                        logger.info("=" * 80)
                        
                        for uid_str, total_score in penalized_rewards.items():
                            try:
                                uid_int = int(uid_str)
                            except (ValueError, TypeError):
                                continue
                            
                            # Get CPU/GPU breakdown for this miner
                            breakdown = cpu_gpu_breakdown.get(uid_str, {})
                            has_cpu = breakdown.get("has_cpu_resources", False)
                            cpu_score = breakdown.get("cpu_score", 0.0)
                            gpu_score = breakdown.get("gpu_score", 0.0)
                            
                            # Check if miner has active penalty
                            has_penalty = uid_int in detector.active_penalties
                            if has_penalty:
                                penalty_info = detector.active_penalties[uid_int]
                                is_penalty_active = current_block < penalty_info['end_block']
                            else:
                                is_penalty_active = False
                            
                            # Apply logic based on penalty status and CPU resources
                            if is_penalty_active and has_cpu:
                                # CASE 1: Penalized + Has CPUs = Everything goes to UID 44
                                logger.warning(f"🚨 UID {uid_int}: PENALTY + CPU resources → ALL to UID 44")
                                logger.warning(f"   Total: {total_score:.3f} → UID 44")
                                uid_44_cpu_collection += total_score
                                final_rewards[uid_str] = 0.0  # Miner gets nothing
                                
                            elif is_penalty_active and not has_cpu:
                                # CASE 2: Penalized but NO CPUs = Normal penalty applies
                                logger.info(f"⚖️  UID {uid_int}: PENALTY only (no CPUs) → keeps penalized score")
                                logger.info(f"   Score: {total_score:.3f} (penalized)")
                                final_rewards[uid_str] = total_score
                                
                            elif not is_penalty_active and has_cpu:
                                # CASE 3: No penalty but has CPUs = CPU to UID 44, GPU stays
                                logger.info(f"💻 UID {uid_int}: NO PENALTY + CPU resources → split")
                                logger.info(f"   CPU: {cpu_score:.3f} → UID 44")
                                logger.info(f"   GPU: {gpu_score:.3f} → miner keeps")
                                uid_44_cpu_collection += cpu_score
                                final_rewards[uid_str] = gpu_score
                                
                            else:
                                # CASE 4: No penalty, no CPUs (pure GPU or no resources)
                                logger.info(f"✅ UID {uid_int}: NO PENALTY, NO CPUs → normal scoring")
                                logger.info(f"   Score: {total_score:.3f}")
                                final_rewards[uid_str] = total_score
                        
                        # Calculate 40% bonus from rewarded UIDs only (exclude penalized UIDs)
                        total_rewarded_scores = sum(final_rewards.values())
                        uid_44_40_percent_bonus = total_rewarded_scores * 0.40
                        logger.info(f"💰 UID 44 BONUS CALCULATION:")
                        logger.info(f"   Sum of rewarded UID scores: {total_rewarded_scores:.3f}")
                        logger.info(f"   40% bonus for UID 44: {uid_44_40_percent_bonus:.3f}")
                        
                        # Calculate total for UID 44 (penalty losses + CPU scores + 40% bonus)
                        uid_44_total = uid_44_penalty_collection + uid_44_cpu_collection + uid_44_40_percent_bonus
                        
                        logger.info("\n" + "=" * 80)
                        logger.info("🎁 UID 44 REWARD SUMMARY")
                        logger.info("=" * 80)
                        logger.info(f"  Total rewarded UID scores: {total_rewarded_scores:.3f}")
                        logger.info(f"  40% bonus (from rewarded UIDs): {uid_44_40_percent_bonus:.3f}")
                        logger.info(f"  Penalty losses collected: {uid_44_penalty_collection:.3f}")
                        logger.info(f"  CPU scores collected: {uid_44_cpu_collection:.3f}")
                        logger.info(f"  TOTAL for UID 44: {uid_44_total:.3f}")
                        logger.info("=" * 80)
                        
                        # Add UID 44's total to final rewards
                        if uid_44_total > 0:
                            final_rewards['44'] = uid_44_total
                            logger.warning(f"🎉 UID 44 receives {uid_44_total:.3f} points total")
                        
                        # Update total_rewards with final rewards
                        total_rewards = final_rewards
                    
                    # Log detector status
                    detector_summary = detector.get_penalty_summary()
                    logger.info(f"Alpha over-selling detector: {detector_summary['active_penalties']} active penalties, "
                               f"{detector_summary['total_violations']} total violations")
                    
                    # Clean up metagraph
                    subtensor.close()
                    
                except Exception as e:
                    logger.error(f"Error applying alpha penalties: {e}")
                    # Continue with original rewards if penalty system fails
                
            except Exception as e:
                logger.error(f"Error in alpha over-selling detector: {e}")
                # Continue with original rewards if penalty system fails
            
            return total_rewards
            
        except Exception as e:
            logger.info(f"No resources to be rewarded")
            return {}

    except Exception as e:
        logger.error(f"Unexpected error in process_miners: {e}")
        return default_return
    finally:
        # Clean up subtensor connection if established
        if subtensor is not None:
            try:
                subtensor.close()
                logger.debug("Subtensor connection closed")
            except Exception as e:
                logger.warning(f"Error closing subtensor connection: {e}")

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)


async def verify_miners(
    allowed_uids: List[str],
) -> None:
    try:
        _get_cached_miners_data(force_refresh=True)
        # Input validation
        verification_results =await sub_verification(allowed_uids)
        if verification_results:
            logger.info(f"Verifiction complete .........")
        else:
            logger.info(f"Verification failed ...... ")
    except ConnectionError as e:
        logger.info(f"verificatio fialed ")
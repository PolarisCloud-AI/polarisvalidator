import asyncio
from typing import List, Callable, Dict, Any,Tuple
from loguru import logger
import numpy as np
import requests
import os
import tenacity
from utils.pogs import execute_ssh_tasks, compare_compute_resources
from utils.compute_score import calculate_compute_score
from utils.uptimedata import calculate_miner_rewards
from utils.api_utils import get_miner_details, get_miner_uid_by_hotkey,check_miner_unique,update_miner_status
from neurons.utils.pow import  perform_ssh_tasks
from neurons.utils.gpu_specs import get_gpu_weight

async def process_miners(
    miners: List[int],
    miner_resources: Dict,
    get_containers_func,
    update_status_func: Callable[[str, str, float, str], None],
    tempo: int,
    max_score: float = 500.0,
) -> Tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
    """
    Processes miners to compute scores based on active containers and compute resources, with incentives for scalability,
    fair compute score weighting, and diminishing returns on container count. Normalizes scores to max_score.
    Miners with no SSH task results or missing task_results are excluded from scoring.

    Args:
        miners: List of miner UIDs.
        miner_resources: Dictionary of miner resource information.
        get_containers_func: Function to retrieve containers for a miner.
        update_status_func: Function to update miner status with ID, status, and percentage.
        tempo: Subnet tempo to scale rewards.
        max_score: Maximum score per miner (default: 500.0).

    Returns:
        Tuple of (results, container_updates, uptime_rewards_dict):
        - results: Dict mapping miner UID to normalized score (≤ max_score).
        - container_updates: Dict mapping miner UID to list of container IDs to update.
        - uptime_rewards_dict: Dict mapping miner UID to uptime reward details.
    """
    raw_results = {}  # Store raw scores before normalization
    container_updates = {}
    uptime_rewards_dict = {}
    subnet_to_miner_map = {int(info["miner_uid"]): miner_id for miner_id, info in miner_resources.items()}
    active_miners = list(subnet_to_miner_map.keys())

    for miner_uid in miners:
        if miner_uid not in active_miners:
            continue
        miner_id = subnet_to_miner_map.get(miner_uid)
        if not miner_id:
            logger.warning(f"No miner_id for miner_uid {miner_uid}")
            continue

        miner_info = miner_resources.get(miner_id)
        if not miner_info:
            logger.warning(f"No resource info for miner_id {miner_id}")
            continue

        try:
            # Execute SSH tasks and check for valid results
            resource_type =miner_info["compute_resources"][0]["resource_type"]
            wrk =miner_info["compute_resources"][0]["network"]["ssh"]
            result = await perform_ssh_tasks(wrk) 
            if not result or "task_results" not in result:
                await _reject_miner(miner_id, "SSH tasks failed or returned no results", update_status_func)
                continue

            specs = result.get("task_results", {})
            pog_score = calculate_compute_score(resource_type,specs)
            if pog_score <50:
                logger.info(f"Miner {miner_id} below threshould with {pog_score} percent")
                reason= f"Your compute score is low with {pog_score}%"
                update_status_func(miner_id, "pending_verification", pog_score,reason)

            scaled_compute_score = np.log1p(pog_score) * 10 

            if resource_type =="GPU":
                gpu_name = specs.get("gpu_name", "")
                gpu_weight = get_gpu_weight(gpu_name)
                if gpu_weight == 0.0:
                    logger.warning(f"No weight found for GPU: {gpu_name}")
                    return 0.0
                pog_score= pog_score * gpu_weight
            logger.info(f"Compute score for miner {miner_uid}: raw={pog_score}, scaled={scaled_compute_score:.2f}")
        except Exception as e:
            logger.error(f"Error calculating compute score for miner {miner_uid}: {e}")
            continue

        try:
            uptime_rewards = calculate_miner_rewards(miner_id, pog_score)
            uptime_rewards_dict[miner_uid] = uptime_rewards
            logger.info(f"Miner {miner_id} uptime reward: {uptime_rewards['reward_amount']}")
        except Exception as e:
            logger.error(f"Error calculating uptime rewards for miner {miner_uid}: {e}")
            continue

        containers = get_containers_func(miner_id)
        active_container_count = 0
        container_payment_updates = []

        for container in containers:
            container_id = container.get("id", "unknown")
            required_fields = ["status"]
            if not all(field in container for field in required_fields):
                logger.warning(f"Container {container_id} missing status field. Skipping.")
                continue
            if container["status"] != "running":
                logger.debug(f"Container {container_id} is not active (status: {container['status']}). Skipping.")
                continue
            try:
                active_container_count += 1
                container_payment_updates.append(container_id)
            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")
                continue

        try:
            # Diminishing returns on container count
            effective_container_count = min(active_container_count, 10) + np.log1p(max(0, active_container_count - 10))
            # Scalability bonus
            container_bonus = np.sqrt(active_container_count) * 2  # Scales to ~9 for 10 containers
            # Balanced weighting: 0.5 containers, 0.5 compute
            base_score = 0.6 * effective_container_count + 0.4 * scaled_compute_score
            
            # Apply tempo and bonus
            raw_score = (base_score * tempo + container_bonus) + uptime_rewards["reward_amount"]
            
            if raw_score > 0:
                raw_results[miner_uid] = raw_score
                container_updates[miner_uid] = container_payment_updates
                logger.info(f"Miner {miner_uid}: {active_container_count} active containers, "
                           f"effective_count={effective_container_count:.2f}, "
                           f"container_bonus={container_bonus:.2f}, "
                           f"scaled_compute={scaled_compute_score:.2f}, "
                           f"tempo={tempo}, "
                           f"uptime_reward={uptime_rewards['reward_amount']}, "
                           f"raw_score={(base_score * tempo):.2f} + {container_bonus:.2f} + "
                           f"{uptime_rewards['reward_amount']} = {raw_score:.2f}")
            else:
                logger.debug(f"Miner {miner_uid} has no score contribution (active_containers={active_container_count}, "
                            f"uptime_rewards={uptime_rewards['reward_amount']})")
        except Exception as e:
            logger.error(f"Error calculating raw score for miner {miner_uid}: {e}")

    # Normalize scores to max_score
    results = {}
    if raw_results:
        raw_scores = list(raw_results.values())
        if raw_scores:
            # Use 90th percentile to reduce outlier impact
            percentile_90 = np.percentile(raw_scores, 90) if len(raw_scores) >= 5 else max(raw_scores)
            if percentile_90 > 0:
                normalization_factor = max_score / percentile_90
                for miner_uid, raw_score in raw_results.items():
                    normalized_score = raw_score * normalization_factor
                    results[miner_uid] = min(max_score, normalized_score)
                    logger.info(f"Miner {miner_uid}: raw_score={raw_score:.2f}, " f"normalized_score={normalized_score:.2f} (factor={normalization_factor:.4f})")
            else:

                logger.warning("All raw scores are zero. Skipping normalization.")
        else:
            logger.info("No valid scores to normalize.")
    else:
        logger.info("No valid scores to normalize.")

    logger.info(f"Processed miners: {results}")
    return results, container_updates, uptime_rewards_dict

async def _reject_miner(
    miner: str,
    reason: str,
    update_status_func: Callable[[str, str, float, str], None]
) -> None:
    """Helper function to reject a miner with a reason and update status."""
    logger.error(f"Rejecting miner {miner}: {reason}")
    update_status_func(miner, "rejected", 0.0, reason)

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
def _check_miner_unique_with_retry(miner: str) -> bool:
    """Wrapper for check_miner_unique with retry logic."""
    return check_miner_unique(miner)

async def verify_miners(
    miners: List[str],
    get_unverified_func: Callable[[], Dict[str, Dict[str, Any]]],
    update_status_func: Callable[[str, str, float, str], None]
) -> None:
    """
    Verifies only unverified miners by checking their hotkey-based UID, uniqueness, and compute resources.
    
    Args:
        miners: List of miner IDs to consider.
        get_unverified_func: Function returning a dict of unverified miners.
        update_status_func: Function to update miner status with ID, status, and percentage.
    """
    logger.info(f"Received {len(miners)} miner IDs for verification")
    unverified_miners = get_unverified_func()
    if not unverified_miners:
        logger.info("No unverified miners found, skipping verification")
        return

    # Filter miners to only those that are unverified
    miners_to_verify = [miner for miner in miners if miner in unverified_miners]
    logger.info(f"Verifying {len(miners_to_verify)} unverified miners")

    for miner in miners_to_verify:
        # Validate resources (expecting a dict from get_unverified_miners)
        miner_resources = unverified_miners.get(miner)
        if not isinstance(miner_resources, list) or not miner_resources:
            await _reject_miner(miner, "Invalid or missing resources", update_status_func)
            continue

        # Get miner details
        miner_spec = get_miner_details(miner)
        if not miner_spec:
            await _reject_miner(miner, "No details returned", update_status_func)
            continue

        # Validate subnet_uid
        subnet_uid = miner_spec.get("subnet_uid")
        if subnet_uid != 49:
            await _reject_miner(miner, f"Invalid subnet_uid {subnet_uid}, expected 49", update_status_func)
            continue

        # Extract and validate hotkey and miner_uid
        hotkey = miner_spec.get("hotkey")
        miner_uid = miner_spec.get("miner_uid")
        if not hotkey or miner_uid is None:
            await _reject_miner(miner, "Missing hotkey or miner_uid", update_status_func)
            continue

        # Verify UID using hotkey on subnet 49
        network_uid = get_miner_uid_by_hotkey(hotkey, netuid=49, network="finney")
        logger.info(f"Network UID for miner {miner}: {network_uid}")
        if network_uid is None or network_uid != miner_uid:
            await _reject_miner(
                miner,
                f"UID mismatch: metagraph UID {network_uid}, reported UID {miner_uid}",
                update_status_func
            )
            continue

        # Verify miner uniqueness with retries
        try:
            is_unique = _check_miner_unique_with_retry(miner)
            if not is_unique:
                await _reject_miner(miner, "Not unique (check_miner_unique returned False)", update_status_func)
                continue
        except requests.RequestException as e:
            await _reject_miner(miner, f"Uniqueness check failed: {str(e)}", update_status_func)
            continue

        # Perform SSH-based resource verification
        try:
            resource_type =miner_resources[0]["resource_type"]
            wrk =miner_resources[0]["network"]["ssh"]
            result = await perform_ssh_tasks(wrk) 
            if not result or "task_results" not in result:
                await _reject_miner(miner, "SSH tasks failed or returned no results", update_status_func)
                continue

            specs = result.get("task_results", {})
            pog_score = calculate_compute_score(resource_type,specs)
            status = "verified" if pog_score >=50 else "rejected"
            logger.info(f"Miner {miner} verification complete: status={status}, percentage={pog_score}")
            reason= f"Failed verification with {pog_score} %"
            update_status_func(miner, status, pog_score,reason)

        except ConnectionError as e:
            await _reject_miner(miner, f"SSH connection error: {str(e)}", update_status_func)
        except TimeoutError as e:
            await _reject_miner(miner, f"SSH task timeout: {str(e)}", update_status_func)
        except Exception as e:
            await _reject_miner(miner, f"Unexpected error during SSH verification: {str(e)}", update_status_func)
            
import asyncio
from typing import List, Dict, Tuple
from loguru import logger
import numpy as np
from utils.pogs import execute_ssh_tasks, compare_compute_resources, compute_resource_score
from utils.uptimedata import calculate_miner_rewards

async def process_miners(
    miners: List[int],
    miner_resources: Dict,
    get_containers_func,
    tempo: int,
    max_score: float = 500.0
) -> Tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
    """
    Processes miners to compute scores based on active containers and compute resources, with incentives for scalability,
    fair compute score weighting, and diminishing returns on container count. Normalizes scores to max_score.

    Args:
        miners: List of miner UIDs.
        miner_resources: Dictionary of miner resource information.
        get_containers_func: Function to retrieve containers for a miner.
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
            logger.debug(f"Miner {miner_uid} is not active. Skipping...")
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
            compute_score = compute_resource_score(miner_info["compute_resources"][0])
            # Logarithmic scaling for fair compute score
            scaled_compute_score = np.log1p(compute_score) * 5  # Scales to ~35 for compute_score=1000
            logger.info(f"Compute score for miner {miner_uid}: raw={compute_score}, scaled={scaled_compute_score:.2f}")
        except Exception as e:
            logger.error(f"Error calculating compute score for miner {miner_uid}: {e}")
            continue

        try:
            uptime_rewards = calculate_miner_rewards(miner_id, compute_score)
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
            if container["status"] != "active":
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
            container_bonus = np.sqrt(active_container_count) * 3  # Scales to ~9 for 10 containers
            # Balanced weighting: 0.5 containers, 0.5 compute
            base_score = 0.5 * effective_container_count + 0.5 * scaled_compute_score
            # Scale base_score to keep within reasonable bounds
            base_score = base_score / 10
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
        max_raw_score = max(raw_results.values())
        if max_raw_score > 0:
            normalization_factor = max_score / max_raw_score
            for miner_uid, raw_score in raw_results.items():
                normalized_score = raw_score * normalization_factor
                results[miner_uid] = normalized_score
                logger.info(f"Miner {miner_uid}: raw_score={raw_score:.2f}, "
                           f"normalized_score={normalized_score:.2f} (factor={normalization_factor:.4f})")
        else:
            logger.warning("All raw scores are zero. Skipping normalization.")
    else:
        logger.info("No valid scores to normalize.")

    logger.info(f"Processed miners: {results}")
    return results, container_updates, uptime_rewards_dict

async def verify_miners(miners: List[str], get_unverified_func, update_status_func):
    logger.info("Verifying miners...")
    unverified_miners = get_unverified_func()
    for miner in miners:
        if miner not in unverified_miners:
            logger.debug(f"Miner {miner} not pending verification. Skipping...")
            continue
        miner_resources = unverified_miners.get(miner)
        if not miner_resources:
            logger.warning(f"No resources for miner {miner}. Skipping...")
            continue
        try:
            result = execute_ssh_tasks(miner)
            if result and "task_results" in result:
                specs = result["task_results"]
                pog_score = compare_compute_resources(specs, miner_resources[0])
                percentage = pog_score["percentage"]
                status = "verified" if percentage >= 30 else "rejected"
                update_status_func(miner, status, percentage)
            else:
                logger.warning(f"SSH tasks failed for miner {miner}")
                update_status_func(miner, "rejected", 0.0)
        except Exception as e:
            logger.error(f"Error verifying miner {miner}: {e}")
            update_status_func(miner, "rejected", 0.0)
import asyncio
from typing import List, Dict, Tuple
from loguru import logger
from utils.pogs import execute_ssh_tasks, compare_compute_resources, compute_resource_score, time_calculation
from utils.uptimedata import calculate_miner_rewards

async def process_miners(miners: List[int], miner_resources: Dict, get_containers_func) -> Tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
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
            logger.warning(f"No miner_id for miner_uid {miner_uid}")
            continue
        miner_info = miner_resources.get(miner_id)
        if not miner_info:
            logger.warning(f"No resource info for miner_id {miner_id}")
            continue

        try:
            compute_score = compute_resource_score(miner_info["compute_resources"][0])
            logger.info(f"Compute score for miner {miner_uid}: {compute_score}")
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
        total_termination_time = 0
        rewarded_containers = 0
        container_payment_updates = []

        for container in containers:
            container_id = container.get("id", "unknown")
            required_fields = ["created_at", "scheduled_termination", "status", "payment_status"]
            if not all(field in container for field in required_fields):
                logger.warning(f"Container {container_id} missing fields. Skipping.")
                continue
            if container["created_at"] is None or container["scheduled_termination"] is None:
                logger.warning(f"Container {container_id} has null timestamps. Skipping.")
                continue
            try:
                actual_run_time = time_calculation(str(container["created_at"]), str(container["scheduled_termination"]))
                if container["status"] == "terminated" and container["payment_status"] == "pending":
                    total_termination_time += actual_run_time
                    rewarded_containers += 1
                    container_payment_updates.append(container_id)
            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")
                continue

        if rewarded_containers > 0:
            try:
                average_time = total_termination_time / rewarded_containers
                final_score = ((average_time + total_termination_time) * compute_score) + uptime_rewards["reward_amount"]
                results[miner_uid] = final_score
                container_updates[miner_uid] = container_payment_updates
            except Exception as e:
                logger.error(f"Error calculating final score for miner {miner_uid}: {e}")
        elif uptime_rewards["reward_amount"] > 0:
            results[miner_uid] = uptime_rewards["reward_amount"]
            container_updates[miner_uid] = []

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
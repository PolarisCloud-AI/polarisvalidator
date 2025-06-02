import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List, Dict, Optional, Tuple, TypedDict
from datetime import datetime, timedelta
import asyncio
from neurons.utils.proof_of_work import perform_ssh_tasks
from neurons.utils.uptimedata import calculate_miner_rewards, log_uptime
import asyncio
import re
import numpy as np
import os
import logging
logging.getLogger("websockets.client").setLevel(logging.WARNING)

class MinerProcessingError(Exception):
    pass

class MinerResult(TypedDict):
    miner_id: str
    miner_uid: str
    hotkey: str
    total_score: float

class UptimeReward(TypedDict):
    reward_amount: float
    blocks_active: int
    uptime: int
    additional_details: Dict

SCORE_THRESHOLD = 0.005
MAX_CONTAINERS = 10
SCORE_WEIGHT = 0.33
CONTAINER_BONUS_MULTIPLIER = 2
SUPPORTED_NETWORKS = ["finney", "mainnet", "test"]


# Cache for hotkey-to-UID mapping
_hotkey_to_uid_cache: Dict[str, int] = {}
_last_metagraph_sync: float = 0
_metagraph_sync_interval: float = 300  # 5 minutes in seconds
_metagraph = None

# Cache for miners data from the common API endpoint
_miners_data_cache: Dict = {}
_miners_data_last_fetch: float = 0
_miners_data_cache_interval: float = 600  # 1 hour in seconds

def _sync_miners_data() -> None:
    """Fetches and caches miners data from the common API endpoint."""
    global _miners_data_cache, _miners_data_last_fetch
    try:
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }
        url = "https://polaris-interface.onrender.com/api/v1/services/miner/miners"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        _miners_data_cache = response.json().get("data", {}).get("miners", [])
        _miners_data_last_fetch = time.time()
        logger.info(f"Cached miners data, total miners: {len(_miners_data_cache)}")
    except Exception as e:
        logger.error(f"Error caching miners data: {e}")
        _miners_data_cache = []
        _miners_data_last_fetch = time.time()

def _get_cached_miners_data(force_refresh: bool = False) -> List[dict]:
    """Returns cached miners data, refreshing if necessary or forced."""
    global _miners_data_last_fetch
    if force_refresh or time.time() - _miners_data_last_fetch > _miners_data_cache_interval or not _miners_data_cache:
        _sync_miners_data()
    return _miners_data_cache

def _sync_metagraph(netuid: int, network: str = "finney") -> None:
    """Syncs the metagraph and updates the hotkey-to-UID cache."""
    global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
    try:
        if time.time() - _last_metagraph_sync > _metagraph_sync_interval or _metagraph is None:
            subtensor = bt.subtensor(network=network)
            _metagraph = subtensor.metagraph(netuid=netuid)
            _hotkey_to_uid_cache = {hotkey: uid for uid, hotkey in enumerate(_metagraph.hotkeys)}
            _last_metagraph_sync = time.time()
            logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(_metagraph.hotkeys)}")
    except Exception as e:
        logger.error(f"Error syncing metagraph for netuid {netuid}: {e}")
        _hotkey_to_uid_cache = {}
        _metagraph = None

def aggregate_rewards(results, uptime_rewards_dict):
    import logging
    logger.debug(f"Aggregating rewards for scored miners.................")

    aggregated_rewards = {}

    # Map miner_id to miner_uid from results
    miner_id_to_uid = {}
    for miner_id, info in results.items():
        miner_uid = info.get("miner_uid")
        miner_id_to_uid[miner_id] = miner_uid

        reward = info.get("total_score", 0)
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
            aggregated_rewards[miner_uid] += reward

    # Now aggregate from uptime_rewards_dict
    for miner_id, uptime_data in uptime_rewards_dict.items():
        uptime_reward = uptime_data.get("reward_amount", 0)

        miner_uid = miner_id_to_uid.get(miner_id)
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
            aggregated_rewards[miner_uid] += uptime_reward
        else:
            logging.warning(f"Miner ID {miner_id} not found in results. Skipping.")

    return aggregated_rewards

async def reward_mechanism(
    allowed_uids: List[int],
    netuid: int = 100,
    network: str = "test",
    tempo: int = 4320,
    max_score: float = 100.0,
    current_block: int = 0
) -> Tuple[Dict[str, MinerResult], Dict[str, UptimeReward]]:
    """
    Fetches and processes miner data, aggregating scores and rewards for verified compute resources.

    Args:
        allowed_uids: List of allowed miner UIDs to filter.
        netuid: Subnet ID for hotkey verification (default: 49).
        network: Bittensor network name (default: "finney").
        tempo: Tempo interval in seconds (default: 4320 seconds = 72 minutes).
        max_score: Maximum normalized score (default: 100.0).
        current_block: Current block number for uptime logging (default: 0).

    Returns:
        Tuple of two dictionaries:
        - Dict mapping miner_id to {miner_id, miner_uid, hotkey, total_score}.
        - Dict mapping miner_id to {reward_amount, blocks_active, uptime, additional_details}.

    Raises:
        ValueError: If input parameters are invalid.
        MinerProcessingError: If processing fails critically.
    """
    # Input validation
    if not allowed_uids:
        logger.warning("Empty allowed_uids list provided")
        return {}, {}
    if tempo <= 0:
        raise ValueError("Tempo must be positive")
    if max_score <= 0:
        raise ValueError("max_score must be positive")
    if current_block < 0:
        raise ValueError("current_block cannot be negative")
    if network not in SUPPORTED_NETWORKS:
        raise ValueError(f"Network must be one of {SUPPORTED_NETWORKS}")

    try:
        # Get cached miners data
        miners = _get_cached_miners_data()
        if not miners:
            logger.warning("No miners data available")
            return {}, {}
        logger.info(f"Fetched {len(miners)} miners")

        # Initialize result dictionaries
        results: Dict[str, MinerResult] = {}
        raw_results: Dict[str, dict] = {}
        uptime_rewards_dict: Dict[str, UptimeReward] = {}
        hotkey_cache: Dict[str, int] = {}
        uptime_logs = []

        # Iterate through miners
        for miner in miners:
            if (
                not miner.get("bittensor_registration")
                or miner["bittensor_registration"].get("miner_uid") is None
                or int(miner["bittensor_registration"]["miner_uid"]) not in allowed_uids
            ):
                continue

            hotkey = miner["bittensor_registration"].get("hotkey")
            miner_uid = int(miner["bittensor_registration"]["miner_uid"])
            miner_id = miner.get("id", "unknown")
            logger.info(f"Processing miner {miner_id} (UID: {miner_uid})")

            # # Verify hotkey
            # if hotkey not in hotkey_cache:
            #     logger.info(f"Verifying hotkey {hotkey} on subnet {netuid}")
            #     hotkey_cache[hotkey] = get_miner_uid_by_hotkey(hotkey, netuid, network)
            # verified_uid = hotkey_cache[hotkey]
            # if verified_uid is None or verified_uid != miner_uid:
            #     logger.warning(f"Hotkey verification failed for miner {miner_id}")
            #     continue

            # Initialize accumulators
            if miner_id not in uptime_rewards_dict:
                raw_results[miner_id] = {
                    "miner_id": miner_id,
                    "miner_uid": miner_uid,
                    "total_raw_score": 0.0
                }
                uptime_rewards_dict[miner_id] = {
                    "reward_amount": 0.0,
                    "blocks_active": 0,
                    "uptime": 0,
                    "additional_details": {"resources": {}}
                }
                results[miner_id] = {
                    "miner_id": miner_id,
                    "miner_uid": str(miner_uid),
                    "hotkey": hotkey,
                    "total_score": 0.0
                }

            # Process compute resources concurrently
            compute_details = miner.get("compute_resources_details", [])
            logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

            async def process_resource(resource, idx):
                resource_id = resource.get("id", "unknown")
                validation_status = resource.get("validation_status")
                if validation_status != "verified":
                    logger.info(f"Skipping resource {resource_id} (ID: {idx}): validation_status={validation_status}")
                    return None
                logger.info(f"Processing resource {idx} (ID: {resource_id})")
                ssh_value = resource.get("network", {}).get("ssh", "No SSH value available")
                try:
                    ssh_result = await perform_ssh_tasks(ssh_value)
                    pog_score = ssh_result["task_results"]["total_score"]
                    logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")
                    return resource_id, pog_score
                except (OSError, asyncio.TimeoutError) as e:
                    logger.error(f"Error performing SSH tasks for resource {resource_id}: {e}")
                    return None

            tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
            resource_results = [r for r in await asyncio.gather(*tasks, return_exceptions=True) if r is not None]

            for resource_id, pog_score in resource_results:
                if pog_score < SCORE_THRESHOLD:
                    logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold")
                    update_result = update_miner_compute_resource(
                        miner_id=miner_id,
                        resource_id=resource_id,
                        status="rejected",
                        reason=f"Low compute score: {pog_score:.4f}"
                    )
                    if not update_result:
                        logger.warning(f"Failed to update status for resource {resource_id}")
                    continue

                # Scale compute score
                scaled_compute_score = np.log1p(pog_score) * 10
                logger.info(f"Resource {resource_id}: scaled_compute_score={scaled_compute_score:.2f}")

                # Calculate uptime and rewards
                status = "active" if pog_score >= SCORE_THRESHOLD else "inactive"
                safe_resource_id = re.sub(r'[^a-zA-Z0-9_-]', '_', resource_id)
                log_file = os.path.join("logs/uptime", f"resource_{safe_resource_id}_uptime.json")
                is_new_resource = not os.path.exists(log_file)
                uptime_percent = 100.0 if status == "active" else 0.0

                uptime_logs.append({
                    "miner_uid": resource_id,
                    "status": status,
                    "compute_score": pog_score,
                    "uptime_reward": 0.0,
                    "block_number": current_block,
                    "reason": "Initial uptime log"
                })

                uptime_rewards = calculate_miner_rewards(resource_id, pog_score, current_block, tempo)
                if is_new_resource:
                    uptime_rewards["reward_amount"] = (tempo / 3600) * 0.2 * (pog_score / 100)
                    uptime_rewards["blocks_active"] = 1
                    uptime_rewards["uptime"] = tempo if status == "active" else 0
                    uptime_rewards["additional_details"] = {
                        "first_time_calculation": True,
                        "blocks_since_last": current_block
                    }

                uptime_rewards_dict[miner_id]["reward_amount"] += uptime_rewards["reward_amount"]
                uptime_rewards_dict[miner_id]["blocks_active"] += uptime_rewards.get("blocks_active", 0)
                uptime_rewards_dict[miner_id]["uptime"] += uptime_rewards.get("uptime", 0)
                uptime_rewards_dict[miner_id]["additional_details"]["resources"][resource_id] = {
                    "reward_amount": uptime_rewards["reward_amount"],
                    "blocks_active": uptime_rewards.get("blocks_active", 0),
                    "uptime": uptime_rewards.get("uptime", 0),
                    "details": uptime_rewards.get("additional_details", {})
                }
                logger.info(f"Resource {resource_id}: reward={uptime_rewards['reward_amount']:.6f}")

                uptime_logs.append({
                    "miner_uid": resource_id,
                    "status": status,
                    "compute_score": pog_score,
                    "uptime_reward": uptime_rewards["reward_amount"],
                    "block_number": current_block,
                    "reason": "Reward updated"
                })

                containers = get_containers_for_resource(resource_id)
                active_container_count = int(containers["running_count"])
                if active_container_count == 0 and containers.get("total_count", 0) > 0:
                    logger.warning(f"No running containers for resource {resource_id}, but {containers['total_count']} found")
                logger.info(f"Resource {resource_id}: running_containers={active_container_count}")

                # Calculate resource score
                effective_container_count = min(active_container_count, MAX_CONTAINERS) + np.log1p(max(0, active_container_count - MAX_CONTAINERS))
                container_bonus = np.sqrt(active_container_count) * CONTAINER_BONUS_MULTIPLIER
                base_score = (uptime_percent / 100) * 100 + SCORE_WEIGHT * effective_container_count + SCORE_WEIGHT * scaled_compute_score
                resource_score = (base_score * (tempo / 3600)) + container_bonus + uptime_rewards["reward_amount"]
                raw_results[miner_id]["total_raw_score"] += resource_score
                logger.info(
                    f"Resource {resource_id}: containers={active_container_count}, score={resource_score:.2f}"
                )

        # Normalize scores
        if raw_results:
            raw_scores = [entry["total_raw_score"] for entry in raw_results.values()]
            if raw_scores:
                percentile_90 = np.percentile(raw_scores, 90) if len(raw_scores) >= 5 else max(raw_scores)
                if percentile_90 > 0:
                    normalization_factor = max_score / percentile_90
                    for miner_id, entry in raw_results.items():
                        normalized_score = min(max_score, entry["total_raw_score"] * normalization_factor)
                        results[miner_id]["total_score"] = normalized_score
                        logger.info(
                            f"Miner ID {miner_id}: raw_score={entry['total_raw_score']:.2f}, normalized_score={normalized_score:.2f}"
                        )
                else:
                    logger.warning("All raw scores are zero. Skipping normalization.")
            else:
                logger.info("No valid scores to normalize.")
        else:
            logger.info("No valid resources to process.")

        # Write uptime logs
        for log_entry in uptime_logs:
            log_uptime(**log_entry)

        logger.info(f"Processed {len(results)} unique miner IDs")
        return results, uptime_rewards_dict

    except Exception as e:
        logger.critical(f"Fatal error processing miners: {e}")
        raise MinerProcessingError(f"Failed to process miners: {e}")



def update_miner_status(miner_id: str, status: str, percentage: float, reason: str) -> Optional[str]:
    """
    Updates a miner's full status using the new PUT endpoint.

    Args:
        miner_id: The ID of the miner to update.
        status: New status string (e.g. 'active', 'inactive').
        percentage: Completion or activity percentage.
        reason: Reason for the status change.

    Returns:
        The updated status from the server or None if failed.
    """
    headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }
    updated_at = datetime.utcnow()
    url = f"https://polaris-interface.onrender.com/api/v1/services/miner/miners/{miner_id}"
    payload = {
        "status": status,
        "percentage": percentage,
        "reason": reason,
        "updated_at": updated_at.isoformat() + "Z"
    }

    try:
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Miner {miner_id} successfully updated to {status} ({percentage}%) - Reason: {reason}")
        return response.json().get("status", "unknown")
    except Exception as e:
        logger.error(f"Failed to update miner {miner_id}: {e}")
        return None


def get_containers_for_miner(miner_id: str) -> List[str]:
    try:
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }

        url = f"https://polaris-interface.onrender.com/api/v1/services/container/container/containers/miner/{miner_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("containers", [])
        

    except Exception as e:
        logger.error(f"Error fetching containers for miner {miner_id}: {e}")
        return []
    


def update_container_payment_status(container_id: str) -> bool:
    """
    Updates the payment status of a container to 'completed' via PUT request.

    Args:
        container_id (str): The ID of the container to update.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    headers = {
        "Connection": "keep-alive",
        "x-api-key": "dev-services-key",
        "x-use-encryption": "true",
        "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
        "service-name": "miner_service",
        "Content-Type": "application/json"
    }

    url = f"https://polaris-interface.onrender.com/api/v1/services/container/container/containers/{container_id}"
    payload = {
        "fields": {
            "payment_status": "paid"
        }
    }

    try:
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"[{response.status_code}] Payment status updated for container {container_id}")
        return True

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error while updating container {container_id}: {http_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error while updating container {container_id}: {req_err}")
    except Exception as e:
        logger.error(f"Unexpected error while updating container {container_id}: {e}", exc_info=True)

    return False

def check_resource_unique(resource_id: str, miner_id: str) -> bool:
    """
    Checks if a resource's IP and port combination is unique across all resources of all miners.

    Args:
        resource_id (str): The ID of the resource to check.
        miner_id (str): The ID of the miner owning the resource.

    Returns:
        bool: True if the resource's IP and port combination is unique, False otherwise.
    """
    try:
        # Fetch cached miners data
        miners = _get_cached_miners_data()
        if not miners:
            logger.error(f"No miner data in cache for uniqueness check of resource {resource_id}")
            return False

        # Extract target resource's IP and port
        target_ip_port = None
        for miner in miners:
            if miner.get("id") == miner_id:
                compute_details = miner.get("compute_resources_details", [])
                for resource in compute_details:
                    if resource.get("id") == resource_id:
                        ssh = resource.get("network", {}).get("ssh")
                        if not ssh or not ssh.startswith("ssh://"):
                            logger.error(f"Resource {resource_id} has invalid or missing SSH format: {ssh}")
                            return False
                        try:
                            address = ssh.split("://")[1].split("@")[1]
                            ip, port = address.split(":")
                            target_ip_port = (ip, port)
                        except (IndexError, ValueError) as e:
                            logger.error(f"Error parsing SSH for resource {resource_id}: {ssh}, error: {e}")
                            return False
                        break
                break
        else:
            logger.error(f"Resource {resource_id} not found for miner {miner_id}")
            return False

        # Check uniqueness across all resources
        for miner in miners:
            compute_details = miner.get("compute_resources_details", [])
            for resource in compute_details:
                if resource.get("id") == resource_id and miner.get("id") == miner_id:
                    continue  # Skip the target resource itself

                ssh = resource.get("network", {}).get("ssh")
                if not ssh or not ssh.startswith("ssh://"):
                    continue

                try:
                    address = ssh.split("://")[1].split("@")[1]
                    ip, port = address.split(":")
                    if (ip, port) == target_ip_port:
                        logger.info(
                            f"Resource {resource_id} of miner {miner_id} shares IP {ip} and port {port} "
                            f"with resource {resource.get('id')} of miner {miner.get('id')}"
                        )
                        return False
                except (IndexError, ValueError):
                    continue

        logger.info(f"Resource {resource_id} of miner {miner_id} is unique with IP and port: {target_ip_port}")
        return True

    except Exception as e:
        logger.error(f"Error checking uniqueness for resource {resource_id} of miner {miner_id}: {e}")
        return False

def get_miners_compute_resources() -> dict[str, dict]:
    """
    Retrieves compute resources for all miners.
    
    Returns:
        dict: A dictionary mapping miner IDs to their compute resources.
    """
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct dictionary of miner IDs to compute resources
        return {
            miner.get("id"): miner.get('compute_resources_details', [])
            for miner in miners
            if miner.get("id")
        }

    except Exception as e:
        logger.error(f"Error fetching miners compute resources: {e}")
        return {}

def get_miner_details(miner_id: str) -> dict:
    """
    Retrieve miner details from _miners_data_cache by miner_id.

    Args:
        miner_id (str): The ID of the miner to look up.

    Returns:
        dict: The miner details if found in _miners_data_cache, otherwise an empty dict.
    """
    logger.info(f"Looking up miner {miner_id} in _miners_data_cache")
    
    # Get cached miners data
    miners_data = _get_cached_miners_data()
    
    # Search for the miner by ID
    for miner in miners_data:
        if miner.get("id") == miner_id:
            logger.info(f"Found miner {miner_id} in _miners_data_cache")
            return miner
    
    logger.warning(f"Miner {miner_id} not found in _miners_data_cache")
    return {}

def get_miner_uid_by_hotkey(hotkey: str, netuid: int, network: str = "finney", force_refresh: bool = False) -> int | None:
    """
    Retrieves the miner UID for a given hotkey on a specific Bittensor subnet using cached metagraph data.

    Args:
        hotkey: The SS58 address of the miner's hotkey.
        netuid: The subnet ID (e.g., 49).
        network: The Bittensor network to query (default: "finney" for mainnet).
        force_refresh: If True, forces a refresh of the metagraph cache (default: False).

    Returns:
        int | None: The miner's UID if found, None otherwise.
    """
    global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph

    try:
        # Validate input
        if not hotkey or not isinstance(hotkey, str):
            logger.error(f"Invalid hotkey provided: {hotkey}")
            return None

        # Check if cache refresh is needed or forced
        if force_refresh or not _hotkey_to_uid_cache or time.time() - _last_metagraph_sync > _metagraph_sync_interval or _metagraph is None:
            logger.info(f"Refreshing metagraph cache for netuid {netuid} (force_refresh={force_refresh})")
            subtensor = bt.subtensor(network=network)
            logger.info(f"Connected to Bittensor network: {network}, querying subnet: {netuid}")
            _metagraph = subtensor.metagraph(netuid=netuid)
            _hotkey_to_uid_cache = {hotkey: uid for uid, hotkey in enumerate(_metagraph.hotkeys)}
            _last_metagraph_sync = time.time()
            logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(_metagraph.hotkeys)}")

        # Look up hotkey in cache
        uid = _hotkey_to_uid_cache.get(hotkey)
        if uid is not None:
            logger.info(f"Found hotkey {hotkey} with UID {uid} in cache for subnet {netuid}")
            return uid

        logger.warning(f"Hotkey {hotkey} not found in cache for subnet {netuid}")
        return None

    except Exception as e:
        logger.error(f"Error retrieving miner UID for hotkey {hotkey} on subnet {netuid}: {e}")
        return None
    

def get_containers_for_resource(resource_id: str) -> Dict[str, any]:
    """
    Fetches containers for a specific resource ID from the Polaris API and counts those in 'running' status.

    Args:
        resource_id (str): The ID of the compute resource to filter containers (e.g., 'c6469c-4b1c-4bca-98e6-b9bf45b88260').

    Returns:
        Dict[str, any]: A dictionary containing:
            - 'running_count': Number of containers in 'running' status for the resource.
            - 'containers': List of containers matching the resource_id (optional, for further use).
    """
    try:
        # Validate input
        if not resource_id or not isinstance(resource_id, str):
            logger.error(f"Invalid resource_id provided: {resource_id}")
            return {"running_count": 0, "containers": []}

        # Set up headers
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }

        # API endpoint
        url = "https://polaris-interface.onrender.com/api/v1/services/container/container/containers"
        logger.info(f"Fetching containers for resource_id: {resource_id} from {url}")

        # Send GET request
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an exception for 4xx/5xx status codes

        # Parse response
        container_list = response.json().get("containers", [])
        logger.info(f"Retrieved {len(container_list)} containers for resource_id: {resource_id}")

        # Filter containers by resource_id and count running ones
        matching_containers = [container for container in container_list if container.get("resource_id") == resource_id]
        running_count = sum(1 for container in matching_containers if container.get("status") == "running")

        logger.info(f"Found {len(matching_containers)} containers for resource_id {resource_id}, "
                    f"{running_count} in 'running' status")

        return {
            "running_count": running_count
        }

    except requests.RequestException as e:
        logger.error(f"Network error fetching containers for resource {resource_id}: {e}")
        return {"running_count": 0, "containers": []}
    except Exception as e:
        logger.error(f"Unexpected error fetching containers for resource {resource_id}: {e}")
        return {"running_count": 0, "containers": []}




def extract_miner_ids(data: List[dict]) -> List[str]:
    """
    Extract miner IDs from the 'unique_miners_ips' list in the data.
    
    Args:
        data: List of dictionaries from get_miners_compute_resources().
    
    Returns:
        List of miner IDs (strings).
    """
    miner_ids = []
    
    try:
        # Validate input
        if not isinstance(data, list) or not data:
            logger.error("Data is not a non-empty list")
            return miner_ids
        
        # Access unique_miners_ips from the first dict
        multiple_miners_ips = data[0].get("unique_miners_ips", [])
        if not isinstance(multiple_miners_ips, list):
            logger.error("unique_miners_ips is not a list")
            return miner_ids
        
        # Extract keys from each dict in unique_miners_ips
        for item in multiple_miners_ips:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict item: {item}")
                continue
            if len(item) != 1:
                logger.warning(f"Skipping dict with unexpected key count: {item}")
                continue
            miner_id = next(iter(item))  # Get the single key
            if isinstance(miner_id, str) and miner_id:
                miner_ids.append(miner_id)
            else:
                logger.warning(f"Skipping invalid miner ID: {miner_id}")
        
        logger.info(f"Extracted {len(miner_ids)} miner IDs")
        return miner_ids
    
    except Exception as e:
        logger.error(f"Error extracting miner IDs: {e}")
        return miner_ids

def filter_miners_by_id(
    bittensor_miners: Dict[str, int],
    netuid: int = 100,
    network: str = "test",
    hotkey_to_uid: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep and whose hotkey-derived UID matches the provided UID.

    Args:
        bittensor_miners: Dictionary mapping miner IDs to UIDs from get_filtered_miners.
        netuid: The subnet ID (default: 49).
        network: The Bittensor network to query (default: "finney").
        hotkey_to_uid: Optional cached mapping of hotkeys to UIDs (e.g., from PolarisNode).

    Returns:
        Dictionary mapping retained miner IDs to their UIDs.
    """
    try:
        # Validate inputs
        if not isinstance(bittensor_miners, dict):
            logger.error("bittensor_miners is not a dictionary")
            return {}

        ids_to_keep = list(bittensor_miners.keys())
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Use provided hotkey_to_uid cache or sync metagraph
        uid_cache = hotkey_to_uid if hotkey_to_uid is not None else _hotkey_to_uid_cache
        if not uid_cache or hotkey_to_uid is None:
            _sync_metagraph(netuid, network)
            uid_cache = _hotkey_to_uid_cache

        # Filter miners and verify hotkey-UID match
        for miner_id, uid in bittensor_miners.items():
            if miner_id not in ids_to_keep_set:
                logger.debug(f"Miner {miner_id} not in ids_to_keep, skipping")
                continue

            # Get miner details
            miner_details = get_miner_details(miner_id)
            hotkey = miner_details.get("bittensor_registration", {}).get("hotkey")
            if not hotkey or hotkey == "default":
                logger.warning(f"Invalid or missing hotkey for miner {miner_id}, skipping")
                continue

            subnet_uid = get_miner_uid_by_hotkey(hotkey, netuid, network)
            if subnet_uid is None:
                logger.warning(f"Hotkey {hotkey} for miner {miner_id} not found on subnet {netuid}, skipping")
                continue

            # Ensure type consistency
            try:
                uid = int(uid)  # Convert uid to int
                subnet_uid = int(subnet_uid)  # Ensure subnet_uid is int
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid UID types for miner {miner_id}: uid={uid} (type={type(uid)}), subnet_uid={subnet_uid} (type={type(subnet_uid)}), error={e}")
                continue

            # Debug logging for UID comparison
            logger.debug(f"Comparing UIDs for miner {miner_id}: uid={uid} (type={type(uid)}), subnet_uid={subnet_uid} (type={type(subnet_uid)})")

            if subnet_uid == uid:
                filtered_miners[miner_id] = uid
                logger.info(f"Miner {miner_id} validated: UID {uid} matches subnet UID {subnet_uid}")
            else:
                logger.warning(f"Miner {miner_id} UID {uid} does not match subnet UID {subnet_uid}, skipping")

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
    

def update_miner_compute_resource(
    miner_id: str,
    resource_id: str,
    status:str,
    reason:str,
) -> Optional[dict]:
    
    try:
    
        # Construct the full URL
        url = f"https://polaris-interface.onrender.com/api/v1/services/miner/miners/{miner_id}"

        # Prepare headers
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }
    
        # Prepare payload
        payload = {
            "compute_resource_updates": [
                {
                    "id": resource_id,
                    "validation_status":status,
                    "reason":reason
                }
            ]
        }

        # Send PUT request
        logger.info(f"Sending PUT request with payload: {payload}")
        response = requests.put(url, headers=headers, json=payload)

        # Check response status
        if response.status_code == 200:
            logger.info(f"Successfully updated compute resource {resource_id} for miner {miner_id}")
            return response.json()
        else:
            logger.error(f"Failed to update compute resource {resource_id} for miner {miner_id}. "
                        f"Status code: {response.status_code}, Response: {response.text}")
            return None

    except requests.RequestException as e:
        logger.error(f"Network error while updating compute resource {resource_id} for miner {miner_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while updating compute resource {resource_id} for miner {miner_id}: {e}")
        return None


async def sub_verification(allowed_uids: List[int]) -> Tuple[Dict[str, int], Dict]:
    """
    Verifies miner compute resources for a given list of allowed UIDs.
    
    Args:
        allowed_uids: List of allowed miner UIDs to process
        
    Returns:
        Tuple containing:
        - hotkey_cache: Dictionary mapping miner hotkeys to UIDs
        - verification_results: Dictionary containing verification outcomes
    """
    # Initialize result dictionaries
    hotkey_cache: Dict[str, int] = {}
    verification_results: Dict = {}

    # Validate input
    if not allowed_uids:
        logger.warning("Received empty allowed_uids list")
        return hotkey_cache, verification_results

    try:
        # Fetch miner data with proper error handling
        try:
            miners =  _get_cached_miners_data()
        except Exception as e:
            logger.error(f"Failed to fetch miners data: {str(e)}", exc_info=True)
            return hotkey_cache, verification_results

        if not miners:
            logger.warning("No miners data available in cache")
            return hotkey_cache, verification_results

        logger.info(f"Processing {len(miners)} miners for verification")

        async def process_miner(miner: Dict) -> None:
            """Process individual miner and their compute resources."""
            try:
                # Validate miner data
                if not (bittensor_reg := miner.get("bittensor_registration")):
                    logger.warning(f"Skipping miner {miner.get('id', 'unknown')}: No bittensor registration")
                    return

                miner_uid = bittensor_reg.get("miner_uid")
                if miner_uid is None or int(miner_uid) not in allowed_uids:
                    logger.debug(f"Skipping miner {miner.get('id', 'unknown')}: UID {miner_uid} not in allowed list")
                    return

                miner_uid = int(miner_uid)
                miner_id = miner.get("id", "unknown")
                hotkey_cache[miner_id] = miner_uid
                logger.info(f"Processing miner {miner_id} (UID: {miner_uid})")

                # Process compute resources
                compute_details = miner.get("compute_resources_details", [])
                if not compute_details:
                    logger.info(f"Miner {miner_id} has no compute resources")
                    return
                logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

                async def process_resource(resource: Dict, idx: int) -> Tuple[str, float] | None:
                    """Process individual compute resource."""
                    try:
                        resource_id = resource.get("id", f"unknown_{idx}")
                        validation_status = resource.get("validation_status")

                        if validation_status == "verified":
                            logger.debug(f"Resource {resource_id} already verified, skipping")
                            return None
                        
                        # Check resource uniqueness
                        if not check_resource_unique(resource_id, miner_id):
                            logger.warning(f"Resource {resource_id} of miner {miner_id} is not unique. Skipping.")
                            return None

                        logger.info(f"Processing resource {idx} (ID: {resource_id})")
                        ssh_value = resource.get("network", {}).get("ssh", None)
                        
                        if not ssh_value:
                            logger.warning(f"Resource {resource_id} has no SSH value")
                            return None

                        ssh_result = await perform_ssh_tasks(ssh_value)
                        pog_score = ssh_result["task_results"]["total_score"]
                        logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")
                        return resource_id, pog_score

                    except (OSError, asyncio.TimeoutError) as e:
                        logger.error(f"Error processing resource {resource_id}: {str(e)}", exc_info=True)
                        return None
                    except Exception as e:
                        logger.error(f"Unexpected error processing resource {resource_id}: {str(e)}", exc_info=True)
                        return None

                # Process resources concurrently
                tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
                resource_results = [r for r in await asyncio.gather(*tasks, return_exceptions=True) 
                                 if r is not None and not isinstance(r, Exception)]

                # Update verification results
                for resource_id, pog_score in resource_results:
                    try:
                        status = "verified" if pog_score >= SCORE_THRESHOLD else "rejected"
                        reason = (f"Verified with score: {pog_score:.4f}" if status == "verified" 
                                else f"Low compute score: {pog_score:.4f}")
                        
                        update_result = await update_miner_compute_resource(
                            miner_id=miner_id,
                            resource_id=resource_id,
                            status=status,
                            reason=reason
                        )
                        
                        if not update_result:
                            logger.warning(f"Failed to update status for resource {resource_id}")
                        
                        verification_results[f"{miner_id}_{resource_id}"] = {
                            "status": status,
                            "score": pog_score,
                            "reason": reason
                        }
                        
                    except Exception as e:
                        logger.error(f"Error updating resource {resource_id} for miner {miner_id}: {str(e)}", 
                                   exc_info=True)

            except Exception as e:
                logger.error(f"Error processing miner {miner.get('id', 'unknown')}: {str(e)}", exc_info=True)

        # Process miners concurrently
        await asyncio.gather(*[process_miner(miner) for miner in miners], return_exceptions=True)
        
        return verification_results

    except Exception as e:
        logger.error(f"Unexpected error in sub_verification: {str(e)}", exc_info=True)
        return verification_results
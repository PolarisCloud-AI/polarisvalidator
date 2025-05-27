import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# Cache for hotkey-to-UID mapping
_hotkey_to_uid_cache: Dict[str, int] = {}
_last_metagraph_sync: float = 0
_metagraph_sync_interval: float = 300  # 5 minutes in seconds
_metagraph = None
_miner_details_cache: Dict[str, dict] = {}

# Cache for miners data from the common API endpoint
_miners_data_cache: Dict = {}
_miners_data_last_fetch: float = 0
_miners_data_cache_interval: float = 3600  # 1 hour in seconds

def _sync_miners_data() -> None:
    """Fetches and caches miners data from the common API endpoint."""
    global _miners_data_cache, _miners_data_last_fetch
    try:
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "53c8f1eba578f46cd3361d243a62c2c46e2852f80acaf5ccc35eaf16304bc60b",
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

def _get_cached_miners_data() -> List[dict]:
    """Returns cached miners data, refreshing if necessary."""
    global _miners_data_last_fetch
    if time.time() - _miners_data_last_fetch > _miners_data_cache_interval or not _miners_data_cache:
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

def get_filtered_miners(allowed_uids: List[int]) -> Tuple[Dict[str, str], List[str]]:
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Initialize outputs
        filtered_miners = {}
        miners_to_reject = []

        for miner in miners:
            miner_id = miner.get("id")
            bittensor_reg = miner.get("bittensor_registration")

            if not miner_id:
                continue 

            if bittensor_reg is not None:
                miner_uid = bittensor_reg.get("miner_uid")
                if miner_uid is None:
                    miners_to_reject.append(miner_id)
                elif int(miner_uid) in allowed_uids:
                    filtered_miners[miner_id] = str(miner_uid)
            else:
                miners_to_reject.append(miner_id)

        return filtered_miners, miners_to_reject

    except Exception as e:
        logger.error(f"Error fetching filtered miners: {e}")
        return {}, []

def get_filtered_miners_val(allowed_uids: List[int]) -> Dict[str, str]:
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Filter and return valid miners
        return {
            miner.get("id"): str(miner.get("bittensor_registration", {}).get("miner_uid"))
            for miner in miners
            if miner.get("bittensor_registration") and
               miner["bittensor_registration"].get("miner_uid") is not None and
               int(miner["bittensor_registration"]["miner_uid"]) in allowed_uids
        }

    except Exception as e:
        logger.error(f"Error fetching filtered miners: {e}")
        return {}

def reject_miners(miners_to_reject: List[str], reason: str = "miner_uid is None") -> None:
    """
    Rejects the specified miners by updating their status to 'rejected' with a given reason.
    
    Args:
        miners_to_reject (List[str]): List of miner IDs to reject.
        reason (str, optional): Reason for rejection. Defaults to "miner_uid is None".
    """
    if not miners_to_reject:
        logger.info("No miners to reject.")
        return
    for miner_id in miners_to_reject:
        logger.info(f"Rejecting miner {miner_id} with reason: {reason}")
        new_status = update_miner_status(
            miner_id=miner_id,
            status="rejected",
            percentage=0.0,
            reason=reason
        )
        if new_status:
            logger.info(f"Successfully rejected miner {miner_id} with status: {new_status}")
        else:
            logger.error(f"Failed to reject miner {miner_id}")

def get_miner_list_with_resources(miner_commune_map: Dict[str, str]) -> Dict[str, dict]:
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct and return the desired output
        return {
            miner.get("id"): {
                "compute_resource_details": miner.get("compute_resources_details", {}),
                "miner_uid": miner_commune_map.get(miner.get("id"))
            }
            for miner in miners
            if miner.get("status") == "verified" and miner.get("id") in miner_commune_map
        }

    except Exception as e:
        logger.error(f"Error fetching miner list with resources: {e}")
        return {}

def get_unverified_miners() -> Dict[str, dict]:
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Return only unverified miners
        return {
            miner.get("id"): miner.get("compute_resources", {})
            for miner in miners
            if miner.get("status") == "pending_verification"
        }

    except Exception as e:
        logger.error(f"Error fetching unverified miners: {e}")
        return {}

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
            "service-key": "53c8f1eba578f46cd3361d243a62c2c46e2852f80acaf5ccc35eaf16304bc60b",
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
            "service-key": "53c8f1eba578f46cd3361d243a62c2c46e2852f80acaf5ccc35eaf16304bc60b",
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
        "service-key": "53c8f1eba578f46cd3361d243a62c2c46e2852f80acaf5ccc35eaf16304bc60b",
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

def check_miner_unique(miner_id: str) -> bool:
    try:
        miners = _get_cached_miners_data()
        if not miners:
            logger.error(f"No miner data in cache for uniqueness check of miner {miner_id}")
            return False

        target_ip_port = None
        for miner in miners:
            if miner.get("id") == miner_id:
                compute_details = miner.get('compute_resources_details', [])
                if not compute_details:
                    logger.error(f"Miner {miner_id} has no compute_resources_details.")
                    return False

                ssh = compute_details[0].get('network', {}).get('ssh')
                if not ssh or not ssh.startswith("ssh://"):
                    logger.error(f"Miner {miner_id} has invalid or missing SSH format: {ssh}")
                    return False

                try:
                    address = ssh.split("://")[1].split("@")[1]
                    ip, port = address.split(":")
                    target_ip_port = (ip, port)
                except (IndexError, ValueError) as e:
                    logger.error(f"Error parsing SSH for miner {miner_id}: {ssh}, error: {e}")
                    return False
                break
        else:
            logger.error(f"Miner {miner_id} not found in cached data")
            return False

        for miner in miners:
            if miner.get("id") == miner_id:
                continue
            compute_details = miner.get('compute_resources_details', [])
            if not compute_details:
                continue

            ssh = compute_details[0].get('network', {}).get('ssh')
            if not ssh or not ssh.startswith("ssh://"):
                continue

            try:
                address = ssh.split("://")[1].split("@")[1]
                ip, port = address.split(":")
                if (ip, port) == target_ip_port:
                    logger.info(f"Miner {miner_id} shares IP {ip} and port {port} with miner {miner.get('id')}")
                    return False
            except (IndexError, ValueError):
                continue

        logger.info(f"Miner {miner_id} is unique with IP and port: {target_ip_port}")
        return True

    except Exception as e:
        logger.error(f"Error checking uniqueness for miner {miner_id}: {e}")
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

def get_miner_uid_by_hotkey(hotkey: str, netuid: int, network: str = "finney") -> int | None:
    """
    Retrieves the miner UID for a given hotkey on a specific Bittensor subnet.
    
    Args:
        hotkey: The SS58 address of the miner's hotkey.
        netuid: The subnet ID (e.g., 49).
        network: The Bittensor network to query (default: "finney" for mainnet).
    
    Returns:
        int | None: The miner's UID if found, None otherwise.
    """
    try:
        # Initialize subtensor connection
        subtensor = bt.subtensor(network=network)
        logger.info(f"Connected to Bittensor network: {network}, querying subnet: {netuid}")

        # Sync metagraph for the specified subnet
        metagraph = subtensor.metagraph(netuid=netuid)
        logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(metagraph.hotkeys)}")

        # Search for the hotkey in the metagraph
        for uid, registered_hotkey in enumerate(metagraph.hotkeys):
            if registered_hotkey == hotkey:
                logger.info(f"Found hotkey {hotkey} with UID {uid} on subnet {netuid}")
                return uid

        logger.warning(f"Hotkey {hotkey} not found in subnet {netuid}")
        return None

    except Exception as e:
        logger.error(f"Error retrieving miner UID for hotkey {hotkey} on subnet {netuid}: {e}")
        return None

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
    netuid: int = 49,
    network: str = "finney",
    hotkey_to_uid: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep, removing all others.
    
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
        # ids_to_keep = get_miners_compute_resources()
        
        ids_to_keep = list(bittensor_miners.keys())
        # Convert ids_to_keep to a set for O(1) lookup
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Use provided hotkey_to_uid cache or sync metagraph
        uid_cache = hotkey_to_uid if hotkey_to_uid is not None else _hotkey_to_uid_cache
        if hotkey_to_uid is None:
            _sync_metagraph(netuid, network)

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

            # Verify UID using cached mapping
            subnet_uid = uid_cache.get(hotkey)
            if subnet_uid is None:
                _sync_metagraph(netuid, network)
                subnet_uid = _hotkey_to_uid_cache.get(hotkey)
                if subnet_uid is None:
                    logger.warning(f"Hotkey {hotkey} still not found after sync, skipping")
                    continue

            filtered_miners[miner_id] = uid

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
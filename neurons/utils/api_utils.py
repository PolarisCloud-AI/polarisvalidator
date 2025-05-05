import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List,Dict
from datetime import datetime, timedelta

def get_filtered_miners(allowed_uids: List[int]) -> tuple[Dict[str, str], List[str]]:
    try:
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
        response.raise_for_status()
        miners_data = response.json()
        
        # Initialize outputs
        filtered_miners = {}
        miners_to_reject = []
        
        # Process each miner
        for miner in miners_data:
            miner_id = miner.get("miner_id")
            miner_uid = miner.get("miner_uid")
            if miner_uid is None:
                miners_to_reject.append(miner_id)
            elif int(miner_uid) in allowed_uids:
                # Include miners with valid miner_uid in allowed_uids
                filtered_miners[miner_id] = str(miner_uid)
        # filtered_miners_={'RplPqqDYqdPNptJ1jDTx':'173', 'SCJ2kuYzFhzQtEiTzAJ8':'0', 'WQRo8rJxvlM9LDlTS5Is':'239','Wbjht0arLPqeQ8ktEX0L':'173','WvOcrfWgVhJpAJiyrlHj':'96','YrPUTbjNrIwXacIcT4oB':'127','b7q1mnJYeAkMm0eeyIEa':'53','gTOo7rTfzpIkxLeXfU94':'0'}
        return filtered_miners, miners_to_reject
    
    except Exception as e:
        logger.error(f"Error fetching filtered miners: {e}")
        return {}, []
    
def get_filtered_miners_val(allowed_uids: list[int]) -> dict[str, str]:
    try:
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
        response.raise_for_status()
        miners_data = response.json()
        return {
            miner["miner_id"]: miner["miner_uid"]
            for miner in miners_data
            if miner["miner_uid"] is not None and int(miner["miner_uid"]) in allowed_uids
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
def get_miner_list_with_resources(miner_commune_map: dict[str, str]) -> dict:
    try:
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
        response.raise_for_status()
        miners_data = response.json()
        return {
            miner["id"]: {
                "compute_resources": miner["compute_resources"],
                "miner_uid": miner_commune_map.get(miner["id"])
            }
            for miner in miners_data
            if miner["status"] == "verified" and miner["id"] in miner_commune_map
        }
    except Exception as e:
        logger.error(f"Error fetching miner list with resources: {e}")
        return {}

def get_unverified_miners() -> dict[str, dict]:
    try:
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
        response.raise_for_status()
        miners_data = response.json()
        return {
            miner["id"]: miner.get("compute_resources", {})
            for miner in miners_data
            if miner.get("status") == "pending_verification"
        }
    except Exception as e:
        logger.error(f"Error fetching unverified miners: {e}")
        return {}

def update_miner_status(miner_id: str, status: str, percentage: float, reason: str) -> str:
    updated_at =datetime.utcnow()
    url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/status"
    headers = {"Content-Type": "application/json"}
    payload = {"status": status,"Reason":reason, "updated_at":updated_at.isoformat() + "Z"}
    try:
        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Miner {miner_id} status updated to {status} with {percentage}%")
        return response.json().get("status", "unknown")
    except Exception as e:
        logger.error(f"Error updating miner {miner_id} status: {e}")
        return None

def get_containers_for_miner(miner_uid: str) -> list[str]:
    try:
        response = requests.get(f"https://orchestrator-gekh.onrender.com/api/v1/containers/miner/direct/{miner_uid}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching containers for miner {miner_uid}: {e}")
        return []

def update_container_payment_status(container_id: str) -> bool:
    url = f"https://orchestrator-gekh.onrender.com/api/v1/containers/direct/{container_id}/multi"
    headers = {"Content-Type": "application/json"}
    payload = {"fields": {"payment_status": "completed"}}
    try:
        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Updated payment status for container {container_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating container {container_id} payment status: {e}")
        return False

def track_tokens(miner_uid: str, tokens: float, validator: str, platform: str) -> bool:
    url = "https://orchestrator-gekh.onrender.com/api/v1/scores/add"
    headers = {"Content-Type": "application/json"}
    payload = {
        "id": str(uuid.uuid4()),
        "miner_uid": miner_uid,
        "tokens": float(tokens),
        "date_received": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "validator": validator,
        "platform": platform,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Tracked tokens for miner {miner_uid}")
        return True
    except Exception as e:
        logger.error(f"Error tracking tokens for miner {miner_uid}: {e}")
        return False
    

def check_miner_unique(miner_id: str) -> bool:
    """
    Checks if a miner with the given miner_id is unique in the system.
    
    Args:
        miner_id: The ID of the miner to check.
    
    Returns:
        bool: True if the miner is unique, False otherwise.
    """
    url = f"https://orchestrator-gekh.onrender.com/api/v1/bittensor/miner/{miner_id}/unique-check"
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        is_unique = result.get("is_unique", False)
        logger.info(f"Miner {miner_id} uniqueness check: {'unique' if is_unique else 'not unique'}")
        return is_unique
    except Exception as e:
        logger.error(f"Error checking uniqueness for miner {miner_id}: {e}")
        return False

def get_miners_compute_resources() -> dict[str, dict]:
    """
    Retrieves compute resources for all miners.
    
    Returns:
        dict: A dictionary mapping miner IDs to their compute resources.
    """
    url = "https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners/compute-resources"
    try:
        response = requests.get(url)
        response.raise_for_status()
        miners_data = response.json()
        return extract_miner_ids(miners_data)
    except Exception as e:
        logger.error(f"Error fetching miners compute resources: {e}")
        return {}

def get_miner_details(miner_id: str) -> dict:
    """
    Retrieves details for a specific miner by miner_id.
    
    Args:
        miner_id: The ID of the miner to retrieve details for.
    
    Returns:
        dict: A dictionary containing the miner's details, or an empty dict if the request fails.
    """
    url = f"https://orchestrator-gekh.onrender.com/api/v1/bittensor/miner/{miner_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        miner_data = response.json()
        logger.info(f"Retrieved details for miner {miner_id}")
        return miner_data
    except Exception as e:
        logger.error(f"Error fetching details for miner {miner_id}: {e}")
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
    Extract miner IDs from the 'multiple_miners_ips' list in the data.
    
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
        
        # Access multiple_miners_ips from the first dict
        multiple_miners_ips = data[0].get("unique_miners_ips", [])
        if not isinstance(multiple_miners_ips, list):
            logger.error("multiple_miners_ips is not a list")
            return miner_ids
        
        # Extract keys from each dict in multiple_miners_ips
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
    

def filter_miners_by_id(bittensor_miners: Dict[str, int],netuid: int = 49, network: str = "finney") -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep, removing all others.
    
    Args:
        bittensor_miners: Dictionary mapping miner IDs to UIDs from get_filtered_miners.
        ids_to_keep: List of miner IDs to retain (e.g., from get_miners_compute_resources).
    
    Returns:
        Dictionary mapping retained miner IDs to their UIDs.
    """
    try:
        # Validate inputs
        if not isinstance(bittensor_miners, dict):
            logger.error("bittensor_miners is not a dictionary")
            return {}
        ids_to_keep = get_miners_compute_resources()
        if not isinstance(ids_to_keep, list):
            logger.error("ids_to_keep is not a list")
            return {}  # Return empty dict if invalid list

        # Convert ids_to_keep to a set for O(1) lookup
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Filter miners and verify hotkey-UID match
        for miner_id, uid in bittensor_miners.items():
            if miner_id not in ids_to_keep_set:
                continue

            # Get miner details to retrieve hotkey
            miner_details = get_miner_details(miner_id)
            hotkey = miner_details.get("hotkey")
            if not hotkey:
                logger.warning(f"No hotkey found for miner {miner_id}, skipping")
                continue

            # Verify UID on Bittensor subnet
            subnet_uid = get_miner_uid_by_hotkey(hotkey, netuid, network)
            if subnet_uid is None:
                logger.warning(f"Hotkey {hotkey} for miner {miner_id} not found on subnet {netuid}, skipping")
                continue

            if subnet_uid == uid:
                filtered_miners[miner_id] = uid
                logger.info(f"Miner {miner_id} validated: UID {uid} matches subnet")
            else:
                logger.warning(f"Miner {miner_id} UID {uid} does not match subnet UID {subnet_uid}, skipping")

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
    

def delete_miner(miner_id: str) -> bool:
    url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}"
    try:
        response = requests.delete(url)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error deleting miner {miner_id}: {e}")
        return False

def get_rejected_miners() -> list[str]:
    try:
        # Get current date dynamically and calculate 2 days ago
        today = datetime.now()
        two_days_ago = today - timedelta(days=2)
        
        # Fetch data from API
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
        response.raise_for_status()
        miners_data = response.json()
        
        # Filter miners with status "rejected" and created 2 days ago
        rejected_miners = [
            miner["id"]
            for miner in miners_data
            if miner.get("status") == "rejected"
            and miner.get("updated_at")  # Ensure created_at exists
            and datetime.fromisoformat(miner["updated_at"].replace("Z", "+00:00")).date() <= two_days_ago.date()
        ]
        
        return rejected_miners
    
    except Exception as e:
        logger.info(f"No data found: {e}")
        return []

def delete_rejected_miners():
    miner_ids = get_rejected_miners()
    two_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    
    if not miner_ids:
        logger.info(f"No rejected miners created on {two_days_ago} found.")
        return
    
    logger.info(f"Found {len(miner_ids)} rejected miners created on {two_days_ago}: {miner_ids}")
    
    # Delete each miner
    for miner_id in miner_ids:
        logger.info(f"Deleting miner {miner_id}...")
        if delete_miner(miner_id):
            logger.info(f"Unfortunately, we are saying goodbye to miner {miner_id}.")
        else:
            logger.error(f"Failed to delete miner {miner_id}")
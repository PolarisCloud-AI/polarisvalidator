import requests
from loguru import logger
import time
import uuid

def get_filtered_miners(allowed_uids: list[int]) -> dict[str, str]:
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

def update_miner_status(miner_id: str, status: str, percentage: float) -> str:
    url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/status"
    headers = {"Content-Type": "application/json"}
    payload = {"status": status}
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
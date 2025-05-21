import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
from threading import Lock
import logging
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)

# Log directory inside container
log_dir = "logs/uptime"
os.makedirs(log_dir, exist_ok=True)
os.chmod(log_dir, 0o777)
log_lock = Lock()


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_miner_rewards(miner_id: str, miner_score: float) -> Dict[str, Any]:
    """
    Calculate a miner's rewards based on incremental uptime and heartbeat improvements.
    Only rewards for increases in uptime since last payment log entry.
    If payment logs are empty, uses only heartbeat endpoint information.
    
    Args:
        miner_id (str): The ID of the miner to calculate rewards for
        miner_score (float): The pre-calculated score of the miner (0-100)
        
    Returns:
        Dict[str, Any]: A dictionary containing the calculated rewards and metrics
    """
    # Log file path for storing previous miner states
    log_dir = "miner_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, f"{miner_id}_logs.json")
    
    try:
        # Fetch miner state data
        state_url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/state"
        state_response = requests.get(state_url)
        state_response.raise_for_status()
        state_data = state_response.json()
        
        # Extract current metrics from state endpoint
        current_status = state_data.get("current_status", "offline")
        heartbeat_count = state_data.get("heartbeat_count", 0)
        last_heartbeat_str = state_data.get("last_heartbeat")
        current_metrics = state_data.get("current_metrics", {})
        system_info = current_metrics.get("system_info", {})
        current_uptime = system_info.get("uptime", 0)
        
        # Try to fetch payment data
        payment_logs_empty = False
        previous_uptime = 0
        previous_heartbeat_count = 0
        
        try:
            payments_url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/payments"
            payments_response = requests.get(payments_url)
            payments_response.raise_for_status()
            payments_data = payments_response.json()
            
            # Check if payment logs are empty or null
            if payments_data is None or (isinstance(payments_data, list) and len(payments_data) == 0):
                payment_logs_empty = True
                logger.info(f"Payment logs are empty for miner {miner_id}")
            elif isinstance(payments_data, list) and len(payments_data) > 0:
                # Sort payment logs by timestamp (newest first)
                sorted_payments = sorted(payments_data, key=lambda x: x.get('timestamp', ''), reverse=True)
                # Use most recent payment log for previous values
                if len(sorted_payments) > 0:
                    most_recent_payment = sorted_payments[0]
                    previous_uptime = most_recent_payment.get('uptime', 0)
                    previous_heartbeat_count = most_recent_payment.get('heartbeat_count', 0)
                    logger.info(f"Using most recent payment log: uptime={previous_uptime}, heartbeats={previous_heartbeat_count}")
            else:
                payment_logs_empty = True
                logger.warning(f"Unexpected payment data format: {type(payments_data)}")
        except Exception as e:
            payment_logs_empty = True
            logger.error(f"Error fetching payment data: {e}")
        
        # Parse last heartbeat time
        last_heartbeat_time = None
        time_since_heartbeat = None
        if last_heartbeat_str:
            try:
                last_heartbeat_time = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                time_since_heartbeat = (now - last_heartbeat_time).total_seconds()
            except Exception as e:
                logger.error(f"Error parsing heartbeat timestamp: {e}")
        
        # Adjust calculations based on payment logs status
        if payment_logs_empty:
            # If payment logs are empty, use the full current uptime for new miners
            # but apply a one-time discount to prevent abuse
            uptime_difference = current_uptime
            heartbeat_difference = heartbeat_count
            
            # Apply a one-time discount factor for full uptime reward calculation
            # This prevents abuse by miners registering and then immediately collecting full rewards
            first_time_discount_factor = 0.7  # Reduce reward to 70% of normal for first-time calculations
        else:
            # Normal incremental calculation
            uptime_difference = max(0, current_uptime - previous_uptime)
            heartbeat_difference = max(0, heartbeat_count - previous_heartbeat_count)
            first_time_discount_factor = 1.0  # No discount for incremental rewards
        
        # Calculate base reward
        base_reward = 0
        status_multiplier = 1.0 if current_status == "online" else 0.25
        
        if uptime_difference > 0:
            # Calculate base reward per hour of uptime
            hourly_rate = 0.02  # Base tokens per hour of uptime
            base_reward = (uptime_difference / 3600) * hourly_rate * miner_score
            
            # Apply first-time discount if applicable (for empty payment logs)
            base_reward *= first_time_discount_factor
            
            # Heartbeat quality bonus
            expected_heartbeats = uptime_difference / 300  # One per 5 minutes
            heartbeat_ratio = min(1.5, heartbeat_difference / max(1, expected_heartbeats))
            heartbeat_bonus = heartbeat_ratio * 0.2  # Up to 20% bonus
            
            # Freshness bonus
            freshness_bonus = 0
            if time_since_heartbeat is not None and time_since_heartbeat < 3600:  # Within last hour
                freshness_bonus = 0.1  # 10% bonus for recent heartbeat
            
            # Calculate final reward
            reward_multiplier = status_multiplier * (1 + heartbeat_bonus + freshness_bonus)
            final_reward = base_reward * reward_multiplier
        else:
            # No new uptime, no reward
            base_reward = 0
            heartbeat_bonus = 0
            freshness_bonus = 0
            reward_multiplier = 0
            final_reward = 0
        
        # Create result object
        result = {
            "miner_id": miner_id,
            "reward": round(final_reward, 6),
            "uptime": {
                "current": current_uptime,
                "previous": previous_uptime,
                "difference": uptime_difference,
                "difference_hours": round(uptime_difference / 3600, 2)
            },
            "heartbeat": {
                "current_count": heartbeat_count,
                "previous_count": previous_heartbeat_count,
                "difference": heartbeat_difference,
                "last_heartbeat": last_heartbeat_str,
                "time_since_seconds": time_since_heartbeat
            },
            "status": current_status,
            "payment_logs_empty": payment_logs_empty,
            "first_time_calculation": payment_logs_empty,
            "calculation_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add detailed reward components if there was a reward
        if final_reward > 0:
            result["reward_components"] = {
                "base_reward": round(base_reward, 6),
                "heartbeat_bonus": round(heartbeat_bonus * 100, 2),
                "freshness_bonus": round(freshness_bonus * 100, 2),
                "status_multiplier": status_multiplier,
                "first_time_discount": 100 - (first_time_discount_factor * 100) if payment_logs_empty else 0,
                "total_multiplier": round(reward_multiplier, 4)
            }
        
        # Save current state for next comparison
        try:
            with open(log_file, 'w') as f:
                log_data = {
                    "last_uptime": current_uptime,
                    "last_heartbeat_count": heartbeat_count,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                json.dump(log_data, f)
        except Exception as e:
            logger.error(f"Error saving current state to log: {e}")
        
        return {
            "miner_id":miner_id,
            "reward_amount":result['reward'],
            "uptime":result['uptime']['current'],
            "heartbeat_count":result['heartbeat']['current_count'],
            "timestamp":last_heartbeat_str,
            "additional_details": {}
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from API: {e}")
        return {
            "miner_id": miner_id,
            "reward": 0,
            "error": f"Failed to fetch data: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error calculating rewards: {e}")
        return {
            "miner_id": miner_id,
            "reward": 0,
            "error": f"Failed to calculate rewards: {str(e)}"
        }

# def send_reward_log(reward_data: dict):
#     """
#     Sends a reward log to the record_payment endpoint.

#     Args:
#         reward_data (dict): Dictionary containing:
#             - miner_id
#             - reward_amount
#             - uptime
#             - heartbeat_count
#             - additional_details
#     """
#     try:
#         # Generate log_id using UUID
#         log_id = str(uuid.uuid4())

#         # Get current UTC timestamp in ISO 8601 format

#         # Build payload
#         payload = {
#             "log_id": log_id,
#             "miner_id": reward_data["miner_id"],
#             "timestamp": reward_data["timestamp"],
#             "reward_amount": reward_data["reward_amount"],
#             "uptime": reward_data["uptime"],
#             "heartbeat_count": reward_data["heartbeat_count"],
#             "additional_details": reward_data.get("additional_details", {})
#         }

#         # Send POST request
#         response = requests.post("https://orchestrator-gekh.onrender.com/api/v1/record_payment", json=payload)

#         # Check response
#         if response.status_code == 200:
#             internal_miner_id=reward_data["miner_id"]
#             print(f"✅ Successfully recorded payment for internal miner id {internal_miner_id}")
#         else:
#             print(f"❌ Failed to record payment: {response.status_code} - {response.text}")

#         return response

#     except Exception as e:
#         print(f"🔥 Exception during payment recording: {e}")
#         return None

# def verify_log_integrity(log_file: str) -> bool:
#     try:
#         with open(log_file, "rb") as f:
#             data = f.read()
#         checksum_file = log_file + ".sha256"
#         if not os.path.exists(checksum_file):
#             return False
#         with open(checksum_file, "r") as f:
#             stored_checksum = f.read().strip()
#         computed_checksum = hashlib.sha256(data).hexdigest()
#         return stored_checksum == computed_checksum
#     except Exception as e:
#         logger.error(f"Error verifying log integrity for {log_file}: {e}")
#         return False

# def save_checksum(log_file: str):
#     try:
#         with open(log_file, "rb") as f:
#             data = f.read()
#         checksum = hashlib.sha256(data).hexdigest()
#         with open(log_file + ".sha256", "w") as f:
#             f.write(checksum)
#         os.chmod(log_file + ".sha256", 0o600)
#     except Exception as e:
#         logger.error(f"Error saving checksum for {log_file}: {e}")

# def log_uptime(miner_uid: int, status: str, compute_score: float, uptime_reward: float, block_number: int, reason: str = ""):
#     log_entry = {
#         "timestamp": datetime.now(timezone.utc).isoformat(),
#         "miner_uid": miner_uid,
#         "status": status,
#         "compute_score": compute_score,
#         "uptime_reward": uptime_reward,
#         "block_number": block_number,
#         "reason": reason
#     }
#     log_file = os.path.join(log_dir, f"miner_{miner_uid}_uptime.json")
#     try:
#         with log_lock:
#             rotate_logs(miner_uid)  # Rotate before writing
#             if os.path.exists(log_file) and verify_log_integrity(log_file):
#                 with open(log_file, "r") as f:
#                     data = json.load(f)
#             else:
#                 data = []
#                 logger.warning(f"Log file for miner {miner_uid} missing or tampered. Starting fresh.")
#             data.append(log_entry)
#             with open(log_file, "w") as f:
#                 json.dump(data, f, indent=2)
#             os.chmod(log_file, 0o600)
#             save_checksum(log_file)
#     except Exception as e:
#         logger.error(f"Failed to log uptime for miner {miner_uid}: {e}")

# def calculate_uptime(miner_uid: int, current_block: int, lookback_blocks: int = 7200) -> float:
#     log_file = os.path.join(log_dir, f"miner_{miner_uid}_uptime.json")
#     if not os.path.exists(log_file) or not verify_log_integrity(log_file):
#         logger.info(f"No valid logs for miner {miner_uid}. Uptime: 0%")
#         return 0.0
#     try:
#         with open(log_file, "r") as f:
#             logs = json.load(f)
#         if not logs:
#             logger.info(f"No logs for miner {miner_uid}. Uptime: 0%")
#             return 0.0
#         start_block = max(0, current_block - lookback_blocks)
#         logs = [log for log in logs if log.get("block_number", 0) >= start_block]
#         if not logs:
#             logger.info(f"No logs within {lookback_blocks} blocks for miner {miner_uid}. Uptime: 0%")
#             return 0.0
#         active_blocks = sum(1 for log in logs if log["status"] in ["active", "initial_active"])
#         uptime_percent = (active_blocks / len(logs)) * 100 if logs else 0.0
#         logger.info(f"Miner {miner_uid} uptime: {uptime_percent:.2f}% over {len(logs)} blocks")
#         return uptime_percent
#     except Exception as e:
#         logger.error(f"Error calculating uptime for miner {miner_uid}: {e}")
#         return 0.0


# def calculate_miner_rewards(miner_id: str, miner_score: float, current_block: int, tempo: int) -> Dict[str, Any]:
#     """
#     Calculate rewards based on blocks since the last rewarded block.
#     Args:
#         miner_id: Miner ID (string).
#         miner_score: Scaled compute score.
#         current_block: Current block number.
#         tempo: Block interval in seconds.
#     Returns:
#         Dict with miner_id, reward_amount, uptime, blocks_active, timestamp, additional_details.
#     """
#     payment_log_file = os.path.join(log_dir, f"miner_{miner_id}_payment_logs.json")
#     try:
#         # Rotate logs before writing
#         rotate_logs(int(miner_id))
        
#         # Initialize metrics
#         current_status = "active"
#         uptime_percent = calculate_uptime(int(miner_id), current_block)
#         current_uptime = uptime_percent * tempo * 7200 / 100  # Seconds for 7200 blocks
#         blocks_active = 1  # Current block
#         payment_logs_empty = False
#         last_rewarded_block = 0
#         previous_uptime = 0

#         # Check payment logs
#         if os.path.exists(payment_log_file) and verify_log_integrity(payment_log_file):
#             with open(payment_log_file, "r") as f:
#                 payment_logs = json.load(f)
#             if payment_logs:
#                 latest_payment = max(payment_logs, key=lambda x: x["block_number"])
#                 last_rewarded_block = latest_payment.get("block_number", 0)
#                 previous_uptime = latest_payment.get("uptime", 0)
#             else:
#                 payment_logs_empty = True
#         else:
#             payment_logs_empty = True

#         # Calculate blocks since last reward
#         blocks_since_last = max(0, current_block - last_rewarded_block)
#         if payment_logs_empty:
#             blocks_active = 1  # Current block only
#             first_time_discount = 0.7
#         else:
#             blocks_active = blocks_since_last
#             first_time_discount = 1.0

#         # Calculate reward
#         base_reward = 0
#         status_multiplier = 1.0 if current_status in ["active", "initial_active"] else 0.25
#         if blocks_active > 0:
#             hourly_rate = 0.02  # Tokens per hour
#             uptime_hours = (blocks_active * tempo) / 3600
#             base_reward = uptime_hours * hourly_rate * miner_score
#             base_reward *= first_time_discount
#             final_reward = base_reward * status_multiplier
#         else:
#             final_reward = 0

#         # Save payment log
#         payment_log = {
#             "miner_id": miner_id,
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "uptime": current_uptime,
#             "blocks_active": blocks_active,
#             "block_number": current_block,
#             "reward_amount": round(final_reward, 6)
#         }
#         try:
#             with open(payment_log_file, "a+") as f:
#                 f.seek(0)
#                 payment_logs = json.load(f) if f.read(1) else []
#                 payment_logs.append(payment_log)
#                 f.seek(0)
#                 f.truncate()
#                 json.dump(payment_logs, f)
#             os.chmod(payment_log_file, 0o600)
#             save_checksum(payment_log_file)
#         except Exception as e:
#             logger.error(f"Error saving payment log for miner {miner_id}: {e}")

#         return {
#             "miner_id": miner_id,
#             "reward_amount": round(final_reward, 6),
#             "uptime": current_uptime,
#             "blocks_active": blocks_active,
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "additional_details": {
#                 "blocks_since_last": blocks_since_last,
#                 "first_time_calculation": payment_logs_empty
#             }
#         }
#     except Exception as e:
#         logger.error(f"Error calculating rewards for miner {miner_id}: {e}")
#         return {
#             "miner_id": miner_id,
#             "reward_amount": 0,
#             "uptime": 0,
#             "blocks_active": 0,
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "additional_details": {"error": str(e)}
#         }
    
# def rotate_logs(miner_uid: int, max_size_bytes: int = 10_000_000):
#     """
#     Rotate log files for a miner if they exceed max_size_bytes.
#     Args:
#         miner_uid: Miner UID.
#         max_size_bytes: Maximum file size before rotation (default: 10MB).
#     """
#     for log_type in ["uptime", "payment_logs"]:
#         log_file = os.path.join(log_dir, f"miner_{miner_uid}_{log_type}.json")
#         if os.path.exists(log_file) and os.path.getsize(log_file) > max_size_bytes:
#             timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
#             os.rename(log_file, f"{log_file}.{timestamp}")
#             logger.info(f"Rotated log file {log_file} to {log_file}.{timestamp}")
#             if os.path.exists(log_file + ".sha256"):
#                 os.rename(log_file + ".sha256", f"{log_file}.{timestamp}.sha256")

# def get_block_number(tempo: int) -> int:
#     """
#     Calculate the current block number based on tempo and a genesis timestamp.
#     Args:
#         tempo: Block interval in seconds.
#     Returns:
#         int: Current block number.
#     """
#     genesis_file = os.path.join(log_dir, "genesis.json")
#     try:
#         # Load or initialize genesis timestamp
#         if os.path.exists(genesis_file):
#             with open(genesis_file, "r") as f:
#                 genesis_data = json.load(f)
#             genesis_time = datetime.fromisoformat(genesis_data["genesis_time"]).timestamp()
#         else:
#             genesis_time = datetime.now(timezone.utc).timestamp()
#             with open(genesis_file, "w") as f:
#                 json.dump({"genesis_time": datetime.fromtimestamp(genesis_time, timezone.utc).isoformat()}, f)
#             os.chmod(genesis_file, 0o600)
#             save_checksum(genesis_file)

#         current_time = datetime.now(timezone.utc).timestamp()
#         block_number = int((current_time - genesis_time) / tempo)
#         return block_number
#     except Exception as e:
#         logger.error(f"Error calculating block number: {e}")
#         return 0
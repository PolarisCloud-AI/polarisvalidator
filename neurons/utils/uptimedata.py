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

def verify_log_integrity(log_file: str) -> bool:
    try:
        with open(log_file, "rb") as f:
            data = f.read()
        checksum_file = log_file + ".sha256"
        if not os.path.exists(checksum_file):
            return False
        with open(checksum_file, "r") as f:
            stored_checksum = f.read().strip()
        computed_checksum = hashlib.sha256(data).hexdigest()
        return stored_checksum == computed_checksum
    except Exception as e:
        logger.error(f"Error verifying log integrity for {log_file}: {e}")
        return False

def save_checksum(log_file: str):
    try:
        with open(log_file, "rb") as f:
            data = f.read()
        checksum = hashlib.sha256(data).hexdigest()
        with open(log_file + ".sha256", "w") as f:
            f.write(checksum)
        os.chmod(log_file + ".sha256", 0o600)
    except Exception as e:
        logger.error(f"Error saving checksum for {log_file}: {e}")

def log_uptime(miner_uid: int, status: str, compute_score: float, uptime_reward: float, block_number: int, reason: str = ""):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "miner_uid": miner_uid,
        "status": status,
        "compute_score": compute_score,
        "uptime_reward": uptime_reward,
        "block_number": block_number,
        "reason": reason
    }
    log_file = os.path.join(log_dir, f"miner_{miner_uid}_uptime.json")
    try:
        with log_lock:
            rotate_logs(miner_uid)  # Rotate before writing
            if os.path.exists(log_file) and verify_log_integrity(log_file):
                with open(log_file, "r") as f:
                    data = json.load(f)
            else:
                data = []
                logger.warning(f"Log file for miner {miner_uid} missing or tampered. Starting fresh.")
            data.append(log_entry)
            with open(log_file, "w") as f:
                json.dump(data, f, indent=2)
            os.chmod(log_file, 0o600)
            save_checksum(log_file)
    except Exception as e:
        logger.error(f"Failed to log uptime for miner {miner_uid}: {e}")

def calculate_uptime(miner_uid: str, current_block: int, lookback_blocks: int = 7200) -> float:
    log_file = os.path.join(log_dir, f"miner_{miner_uid}_uptime.json")
    if not os.path.exists(log_file) or not verify_log_integrity(log_file):
        logger.info(f"No valid logs for miner {miner_uid}. Uptime: 0%")
        return 0.0
    try:
        with open(log_file, "r") as f:
            logs = json.load(f)
        if not logs:
            logger.info(f"No logs for miner {miner_uid}. Uptime: 0%")
            return 0.0
        start_block = max(0, current_block - lookback_blocks)
        logs = [log for log in logs if log.get("block_number", 0) >= start_block]
        if not logs:
            logger.info(f"No logs within {lookback_blocks} blocks for miner {miner_uid}. Uptime: 0%")
            return 0.0
        active_blocks = sum(1 for log in logs if log["status"] in ["active", "initial_active"])
        uptime_percent = (active_blocks / len(logs)) * 100 if logs else 0.0
        logger.info(f"Miner {miner_uid} uptime: {uptime_percent:.2f}% over {len(logs)} blocks")
        return uptime_percent
    except Exception as e:
        logger.error(f"Error calculating uptime for miner {miner_uid}: {e}")
        return 0.0


def calculate_miner_rewards(miner_id: str, miner_score: float, current_block: int, tempo: int) -> Dict[str, Any]:
    """
    Calculate rewards based on blocks since the last rewarded block.
    Args:
        miner_id: Miner ID (string).
        miner_score: Scaled compute score.
        current_block: Current block number.
        tempo: Block interval in seconds.
    Returns:
        Dict with miner_id, reward_amount, uptime, blocks_active, timestamp, additional_details.
    """
    payment_log_file = os.path.join(log_dir, f"miner_{miner_id}_payment_logs.json")
    try:
        # Rotate logs before writing
        rotate_logs(miner_id)
        
        # Initialize metrics
        current_status = "active"
        uptime_percent = calculate_uptime(miner_id, current_block)
        current_uptime = uptime_percent * tempo * 7200 / 100  # Seconds for 7200 blocks
        blocks_active = 1  # Current block
        payment_logs_empty = False
        last_rewarded_block = 0
        previous_uptime = 0

        # Check payment logs
        if os.path.exists(payment_log_file) and verify_log_integrity(payment_log_file):
            with open(payment_log_file, "r") as f:
                payment_logs = json.load(f)
            if payment_logs:
                latest_payment = max(payment_logs, key=lambda x: x["block_number"])
                last_rewarded_block = latest_payment.get("block_number", 0)
                previous_uptime = latest_payment.get("uptime", 0)
            else:
                payment_logs_empty = True
        else:
            payment_logs_empty = True

        # Calculate blocks since last reward
        blocks_since_last = max(0, current_block - last_rewarded_block)
        if payment_logs_empty:
            blocks_active = 1  # Current block only
            first_time_discount = 0.7
        else:
            blocks_active = blocks_since_last
            first_time_discount = 1.0

        # Calculate reward
        base_reward = 0
        status_multiplier = 2.0 if current_status in ["active", "initial_active"] else 0.25
        if blocks_active > 0:
            hourly_rate = 0.2  # Tokens per hour
            uptime_hours = (blocks_active * tempo) / 3600
            base_reward = uptime_hours * hourly_rate * miner_score
            base_reward *= first_time_discount
            final_reward = base_reward * status_multiplier
        else:
            final_reward = 0

        # Save payment log
        payment_log = {
            "miner_id": miner_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": current_uptime,
            "blocks_active": blocks_active,
            "block_number": current_block,
            "reward_amount": round(final_reward, 6)
        }
        try:
            with open(payment_log_file, "a+") as f:
                f.seek(0)
                payment_logs = json.load(f) if f.read(1) else []
                payment_logs.append(payment_log)
                f.seek(0)
                f.truncate()
                json.dump(payment_logs, f)
            os.chmod(payment_log_file, 0o600)
            save_checksum(payment_log_file)
        except Exception as e:
            logger.error(f"Error saving payment log for miner {miner_id}: {e}")

        return {
            "miner_id": miner_id,
            "reward_amount": round(final_reward, 6),
            "uptime": current_uptime,
            "blocks_active": blocks_active,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "additional_details": {
                "blocks_since_last": blocks_since_last,
                "first_time_calculation": payment_logs_empty
            }
        }
    except Exception as e:
        logger.error(f"Error calculating rewards for miner {miner_id}: {e}")
        return {
            "miner_id": miner_id,
            "reward_amount": 0,
            "uptime": 0,
            "blocks_active": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "additional_details": {"error": str(e)}
        }
    
def rotate_logs(miner_uid: str, max_size_bytes: int = 10_000_000):
    """
    Rotate log files for a miner if they exceed max_size_bytes.
    Args:
        miner_uid: Miner UID.
        max_size_bytes: Maximum file size before rotation (default: 10MB).
    """
    for log_type in ["uptime", "payment_logs"]:
        log_file = os.path.join(log_dir, f"miner_{miner_uid}_{log_type}.json")
        if os.path.exists(log_file) and os.path.getsize(log_file) > max_size_bytes:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            os.rename(log_file, f"{log_file}.{timestamp}")
            logger.info(f"Rotated log file {log_file} to {log_file}.{timestamp}")
            if os.path.exists(log_file + ".sha256"):
                os.rename(log_file + ".sha256", f"{log_file}.{timestamp}.sha256")

def get_block_number(tempo: int) -> int:
    """
    Calculate the current block number based on tempo and a genesis timestamp.
    Args:
        tempo: Block interval in seconds.
    Returns:
        int: Current block number.
    """
    genesis_file = os.path.join(log_dir, "genesis.json")
    try:
        # Load or initialize genesis timestamp
        if os.path.exists(genesis_file):
            with open(genesis_file, "r") as f:
                genesis_data = json.load(f)
            genesis_time = datetime.fromisoformat(genesis_data["genesis_time"]).timestamp()
        else:
            genesis_time = datetime.now(timezone.utc).timestamp()
            with open(genesis_file, "w") as f:
                json.dump({"genesis_time": datetime.fromtimestamp(genesis_time, timezone.utc).isoformat()}, f)
            os.chmod(genesis_file, 0o600)
            save_checksum(genesis_file)

        current_time = datetime.now(timezone.utc).timestamp()
        block_number = int((current_time - genesis_time) / tempo)
        return block_number
    except Exception as e:
        logger.error(f"Error calculating block number: {e}")
        return 0
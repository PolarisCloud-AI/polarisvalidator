import requests
import datetime
import json
from typing import Dict, Any, Optional
import logging
import os
import uuid
from datetime import timezone

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
                last_heartbeat_time = datetime.datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
                now = datetime.datetime.now(datetime.timezone.utc)
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
            "calculation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
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
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
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

def send_reward_log(reward_data: dict):
    """
    Sends a reward log to the record_payment endpoint.

    Args:
        reward_data (dict): Dictionary containing:
            - miner_id
            - reward_amount
            - uptime
            - heartbeat_count
            - additional_details
    """
    try:
        # Generate log_id using UUID
        log_id = str(uuid.uuid4())

        # Get current UTC timestamp in ISO 8601 format

        # Build payload
        payload = {
            "log_id": log_id,
            "miner_id": reward_data["miner_id"],
            "timestamp": reward_data["timestamp"],
            "reward_amount": reward_data["reward_amount"],
            "uptime": reward_data["uptime"],
            "heartbeat_count": reward_data["heartbeat_count"],
            "additional_details": reward_data.get("additional_details", {})
        }

        # Send POST request
        response = requests.post("https://orchestrator-gekh.onrender.com/api/v1/record_payment", json=payload)

        # Check response
        if response.status_code == 200:
            internal_miner_id=reward_data["miner_id"]
            print(f"✅ Successfully recorded payment for internal miner id {internal_miner_id}")
        else:
            print(f"❌ Failed to record payment: {response.status_code} - {response.text}")

        return response

    except Exception as e:
        print(f"🔥 Exception during payment recording: {e}")
        return None

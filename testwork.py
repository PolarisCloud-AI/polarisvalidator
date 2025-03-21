import bittensor as bt
import time
import uuid
from loguru import logger
import requests
import sys

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
    colorize=True,
)

wallet = bt.wallet(name="validator")  # Replace with your wallet name
print(wallet.hotkey.ss58_address)


def track_tokens(miner_uid: str, tokens: float, validator: str, platform: str):
        """
        Sends a POST request to the scores/add API to track tokens rewarded to miners.

        Args:
            miner_uid (str): The UID of the miner being rewarded.
            tokens (float): The number of tokens rewarded.
            validator (str): The validator issuing the reward.
            platform (str): The platform associated with the reward.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        url = "https://orchestrator-gekh.onrender.com/api/v1/scores/add"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "id": str(uuid.uuid4()),  # Generate a unique ID
            "miner_uid": miner_uid,
            "tokens": tokens,
            "date_received": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),  # Current UTC time
            "validator": validator,
            "platform": platform,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())  # Current UTC time
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Successfully tracked tokens for miner {miner_uid}.")
                return True
            else:
                logger.error(f"Failed to track tokens for miner {miner_uid}. "
                            f"Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error while tracking tokens for miner {miner_uid}: {e}")
            return False

# sample function call 
wallet="model"
tokens=3000.0
platform="bittensor"
miner_uid="103"

track_tokens(miner_uid,tokens,wallet,platform)
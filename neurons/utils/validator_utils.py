import asyncio
from typing import List, Callable, Dict, Any,Tuple
from loguru import logger
import numpy as np
import requests
import os
import tenacity
import time
from utils.api_utils import _get_cached_miners_data,sub_verification,reward_mechanism,aggregate_rewards
import asyncio
import bittensor as bt
import json
import logging
logging.getLogger("websockets.client").setLevel(logging.WARNING)

async def process_miners(
    miners: List[int],
    tempo: int,
    max_score: float = 500.0,
    netuid: int = 49,
    network: str = "finney",
) -> Tuple[Dict[int, float], Dict[int, List[str]], Dict[int, Dict]]:
    """
    Process miners and compute their rewards with robust error handling.

    Args:
        miners: List of miner IDs to process
        tempo: Tempo value for reward calculation
        max_score: Maximum score for reward calculation (default: 500.0)
        netuid: Network unique identifier (default: 49)
        network: Network name (default: "finney")

    Returns:
        Tuple containing total rewards, compute rewards, and uptime rewards

    Raises:
        ValueError: If input parameters are invalid
        RuntimeError: If critical operations fail
    """
    # Input validation
    if not isinstance(miners, list) or not all(isinstance(m, int) for m in miners):
        logger.error("Invalid miners list: must be a list of integers")
        raise ValueError("Miners must be a list of integers")
    
    if not isinstance(tempo, int) or tempo <= 0:
        logger.error(f"Invalid tempo value: {tempo}. Must be a positive integer")
        raise ValueError("Tempo must be a positive integer")
    
    if not isinstance(max_score, (int, float)) or max_score <= 0:
        logger.error(f"Invalid max_score: {max_score}. Must be a positive number")
        raise ValueError("max_score must be a positive number")
    
    if not isinstance(netuid, int):
        logger.error(f"Invalid netuid: {netuid}. Must be an integer")
        raise ValueError("netuid must be an integer")
    
    if not isinstance(network, str):
        logger.error(f"Invalid network: {network}. Must be a string")
        raise ValueError("network must be a string")

    # Initialize default return values in case of failure
    default_rewards: Dict[int, float] = {miner: 0.0 for miner in miners}
    default_details: Dict[int, List[str]] = {miner: [] for miner in miners}
    default_metadata: Dict[int, Dict] = {miner: {} for miner in miners}
    default_return = (default_rewards, default_details, default_metadata)

    try:
        # Refresh cached miners data
        try:
            _get_cached_miners_data(force_refresh=True)
            logger.info("Successfully refreshed cached miners data")
        except Exception as e:
            logger.warning(f"Failed to refresh cached miners data: {e}")
            # Continue execution as cache refresh is not critical

        # Initialize subtensor connection
        current_block = 0
        try:
            subtensor = bt.subtensor(network=network)
            current_block = subtensor.get_current_block()
            logger.info(f"Current block number: {current_block}")
        except Exception as e:
            logger.error(f"Failed to initialize subtensor or fetch block: {e}")
            # Continue with default block number (0)

        # Calculate rewards
        try:
            compute_rewards, uptime_rewards = await reward_mechanism(
                allowed_uids=miners,
                netuid=netuid,
                network=network,
                tempo=tempo,
                max_score=max_score,
                current_block=current_block
            )
        except Exception as e:
            logger.error(f"Error in reward_mechanism: {e}")
            return default_return

        # Aggregate rewards
        try:
            total_rewards = aggregate_rewards(compute_rewards, uptime_rewards)
            logger.info(f"Successfully processed miners rewards: {total_rewards}")
            return total_rewards
        except Exception as e:
            logger.info(f"No resources to be rewarded")
            return {}

    except Exception as e:
        logger.error(f"Unexpected error in process_miners: {e}")
        return default_return
    finally:
        # Clean up subtensor connection if established
        if subtensor is not None:
            try:
                subtensor.close()
                logger.debug("Subtensor connection closed")
            except Exception as e:
                logger.warning(f"Error closing subtensor connection: {e}")

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)


async def verify_miners(
    allowed_uids: List[str],
) -> None:
    try:
        _get_cached_miners_data(force_refresh=True)
        # Input validation
        verification_results =await sub_verification(allowed_uids)
        if verification_results:
            logger.info(f"Verifiction complete .........")
        else:
            logger.info(f"Verification failed ...... ")
    except ConnectionError as e:
        logger.info(f"verificatio fialed ")
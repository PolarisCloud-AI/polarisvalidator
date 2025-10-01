import numpy as np
import torch
import random
import bittensor as bt
from typing import Tuple, List
from loguru import logger
from template.base.utils.config import __spec_version__

def normalize_max_weight(x: np.ndarray, limit: float = 0.1) -> np.ndarray:
    """
    Normalizes weights to sum to 1.0 with a per-miner limit.
    
    Args:
        x: Array of raw scores.
        limit: Maximum weight per miner (default: 0.1).
    
    Returns:
        Normalized weights summing to 1.0.
    """
    weights = x.copy()
    
    if weights.size == 0 or weights.sum() == 0:
        return np.zeros_like(weights)
    
    weights = weights / weights.sum()
    
    if weights.max() > limit:
        excess = weights - limit
        excess[excess < 0] = 0
        total_excess = excess.sum()
        weights = np.minimum(weights, limit)
        non_capped = weights < limit
        if non_capped.sum() > 0 and total_excess > 0:
            redistribution = total_excess * (weights[non_capped] / weights[non_capped].sum())
            weights[non_capped] += redistribution
    
    if weights.sum() > 0:
        weights = weights / weights.sum()
    
    return weights

def convert_weights_and_uids_for_emit(
    uids: np.ndarray, weights: np.ndarray
) -> Tuple[List[int], List[int]]:
    r"""Converts weights into integer u32 representation that sum to MAX_INT_WEIGHT.
    Args:
        uids (:obj:`np.ndarray,`):
            Array of uids as destinations for passed weights.
        weights (:obj:`np.ndarray,`):
            Array of weights.
    Returns:
        weight_uids (List[int]):
            Uids as a list.
        weight_vals (List[int]):
            Weights as a list.
    """
    # Ensure weights sum to exactly 1.0
    if weights.sum() > 0:
        weights = weights / weights.sum()
    
    # Convert to Bittensor's expected integer format
    MAX_INT_WEIGHT = 4294967295  # 2^32 - 1
    
    # Debug: Log the weights before conversion
    logger.debug(f"Normalized weights before conversion: {weights.tolist()}")
    logger.debug(f"Weight sum before conversion: {weights.sum():.10f}")
    
    # Use a different approach: distribute weights proportionally
    # First, calculate how many total "units" we have
    total_units = MAX_INT_WEIGHT
    
    # Calculate proportional integer weights
    weight_vals = []
    for weight in weights:
        # Calculate proportional share
        proportional_share = int(weight * total_units)
        # Ensure minimum weight of 1 for any non-zero weight
        if weight > 0 and proportional_share == 0:
            proportional_share = 1
        weight_vals.append(proportional_share)
    
    weight_vals = np.array(weight_vals, dtype=np.int64)
    
    # Debug: Log the weights after conversion
    logger.debug(f"Weights after conversion: {weight_vals.tolist()}")
    logger.debug(f"Weight sum after conversion: {weight_vals.sum()}")
    
    # Ensure the total sum is exactly MAX_INT_WEIGHT (handle rounding errors)
    total_weight = weight_vals.sum()
    if total_weight != MAX_INT_WEIGHT:
        # Adjust the largest weight to make total exactly MAX_INT_WEIGHT
        diff = MAX_INT_WEIGHT - total_weight
        max_idx = np.argmax(weight_vals)
        weight_vals[max_idx] += diff
        logger.debug(f"Adjusted weight at index {max_idx} by {diff}, new total: {weight_vals.sum()}")
    
    # Convert to lists
    uids_list = uids.tolist()
    weights_list = weight_vals.tolist()
    
    logger.info(f"Converted weights: UIDs={uids_list}, Weights={weights_list}, Sum={sum(weights_list)}")
    return uids_list, weights_list

def process_weights_for_netuid(
    weights: list[float],
    uids: list[int],
    netuid: int,
    subtensor: bt.subtensor,
    wallet: bt.wallet
) -> bool:
    """
    Processes and submits weights to the blockchain.
    
    Args:
        weights: List of weights.
        uids: List of UIDs.
        netuid: Network UID.
        subtensor: Bittensor subtensor instance.
        wallet: Validator wallet.
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        if not weights or not uids:
            logger.warning("Empty weights or UIDs. Skipping weight setting.")
            return False
        if any(np.isnan(weights)):
            logger.warning("Weights contain NaN values. Skipping weight setting.")
            return False
        weights = torch.tensor(weights, dtype=torch.float32)
        weight_sum = weights.sum()
        if abs(weight_sum - 1.0) > 1e-5:
            logger.info(f"Adjusting weights sum from {weight_sum} to 1.0")
            weights = weights / weight_sum
        filtered_uids = [uid for i, uid in enumerate(uids) if weights[i] > 0]
        filtered_weights = weights[weights > 0].tolist()
        filtered_weights = [float(w) for w in filtered_weights]
        if not filtered_uids:
            logger.warning("No non-zero weights after filtering. Skipping weight setting.")
            return False
        logger.info(f"Setting weights: UIDs={filtered_uids}, Weights={filtered_weights}, Sum={sum(filtered_weights)}")
        logger.info(f"Wallet: {wallet}")
        result = subtensor.set_weights(
            wallet,
            netuid=netuid,
            uids=torch.tensor(filtered_uids, dtype=torch.int64),
            weights=torch.tensor(filtered_weights, dtype=torch.float32),
            wait_for_finalization=False,
            wait_for_inclusion=False,
            version_key=__spec_version__
        )
        if result[0]:
            logger.success(f"Weights set successfully: {result[0]}")
            return True
        else:
            logger.warning(f"Weight setting failed: {result[1]}")
            return False
    except Exception as e:
        logger.error(f"Error setting weights for netuid {netuid}: {e}")
        return False
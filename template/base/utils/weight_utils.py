import numpy as np
import torch
import random
import bittensor as bt
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

def convert_weights_and_uids_for_emit(weighted_scores):
    """
    Converts weighted scores to weights and UIDs.
    
    Args:
        weighted_scores: Dict of UID to score.
    
    Returns:
        Tuple of (weights, uids).
    """
    weighted_scores = weighted_scores.copy()
    
    total_score = sum(weighted_scores.values())
    if total_score <= 0:
        logger.warning("No valid scores. Returning empty weights.")
        return [], []
    
    uids = [int(uid) for uid in weighted_scores.keys()]
    scores = np.array([weighted_scores.get(str(uid), 0.0) for uid in uids], dtype=np.float32)
    
    weights = normalize_max_weight(scores, limit=0.1)
    
    logger.info(f"Converted weights: UIDs={uids}, Weights={weights.tolist()}, Sum={sum(weights)}")
    return weights.tolist(), uids

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
            netuid=netuid,
            uids=torch.tensor(filtered_uids, dtype=torch.int64),
            weights=torch.tensor(filtered_weights, dtype=torch.float32),
            wait_for_finalization=False,
            wait_for_inclusion=False,
            wallet=wallet,
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
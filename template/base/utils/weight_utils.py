import numpy as np
import bittensor as bt
import torch
from typing import List
import sys
from loguru import logger

# Configure loguru for world-class logging
logger.remove()  # Remove default logger
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
    colorize=True,
)
U32_MAX = 4294967295
U16_MAX = 65535


def normalize_max_weight(x: np.ndarray, limit: float = 0.1) -> np.ndarray:
    r"""Normalizes the numpy array x so that sum(x) = 1 and the max value is not greater than the limit.
    Args:
        x (:obj:`np.ndarray`):
            Array to be max_value normalized.
        limit: float:
            Max value after normalization.
    Returns:
        y (:obj:`np.ndarray`):
            Normalized x array.
    """
    epsilon = 1e-7  # For numerical stability after normalization

    weights = x.copy()
    values = np.sort(weights)

    if x.sum() == 0 or len(x) * limit <= 1:
        return np.ones_like(x) / x.size
    else:
        estimation = values / values.sum()

        if estimation.max() <= limit:
            return weights / weights.sum()

        # Find the cumulative sum and sorted array
        cumsum = np.cumsum(estimation, 0)

        # Determine the index of cutoff
        estimation_sum = np.array(
            [(len(values) - i - 1) * estimation[i] for i in range(len(values))]
        )
        n_values = (
            estimation / (estimation_sum + cumsum + epsilon) < limit
        ).sum()

        # Determine the cutoff based on the index
        cutoff_scale = (limit * cumsum[n_values - 1] - epsilon) / (
            1 - (limit * (len(estimation) - n_values))
        )
        cutoff = cutoff_scale * values.sum()

        # Applying the cutoff
        weights[weights > cutoff] = cutoff

        y = weights / weights.sum()

        return y


def convert_weights_and_uids_for_emit(weighted_scores):
    """
    Convert weighted scores to weights and uids for emitting to the chain.

    Args:
        weighted_scores (dict): A dictionary of scores for each uid.

    Returns:
        tuple (List[float], List[int]): A tuple containing the weights and uids.
    """
    # Sort the scores in descending order based on values
    logger.info(f"Weighted scores: {weighted_scores}")
    sorted_scores = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)

    # Extract uids and scores from the sorted list
    uids = [int(item[0]) for item in sorted_scores]
    weights = [item[1] for item in sorted_scores]

    return weights, uids


def process_weights_for_netuid(
    weights: List[float],
    uids: List[int],
    netuid: int,
    subtensor: bt.subtensor,
    wallet: bt.wallet
) -> bool:
    """
    Process and set weights on the Bittensor network for a given netuid.

    Args:
        weights (List[float]): A list of weights for each uid.
        uids (List[int]): A list of uids to set weights for.
        netuid (int): The netuid of the subnet to set weights for.
        subtensor (bt.subtensor): The subtensor object to use for setting weights.

    Returns:
        bool: True if the weights were set successfully, False otherwise.
    """
    try:
        # Check if weights contains any NaN values
        if any(np.isnan(weights)):
            logger.warning("Weights contain NaN values. Skipping weight setting.")
            return False

        # Convert weights to torch tensor
        weights = torch.tensor(weights, dtype=torch.float32)

        # Normalize weights to sum to 1
        weights = torch.nn.functional.normalize(weights, p=1.0, dim=0)

        # Filter out uids with zero weights
        filtered_uids = [
            uid for i, uid in enumerate(uids) if weights[i] > 0
        ]  # Keep uids with non-zero weights
        filtered_weights = weights[weights > 0].tolist()  # Keep corresponding weights

        # Convert filtered weights to float64
        filtered_weights = [
            float(w) for w in filtered_weights
        ]  # Convert weights to Python floats

        # Log the filtered weights and uids
        logger.info(
            f"Setting weights: UIDs: {filtered_uids}, Weights: {filtered_weights}"
        )

        # Set weights on the Bittensor network
        result = subtensor.set_weights(
            netuid=netuid,
            uids=torch.tensor(filtered_uids, dtype=torch.int64),
            weights=torch.tensor(filtered_weights, dtype=torch.float32),
            wait_for_inclusion=False,
            wallet=wallet
        )

        # Log the result of the weight setting
        logger.success(f"Successfully set weights on netuid {netuid}: {result}")

        return True

    except Exception as e:
        logger.error(f"Error setting weights on netuid {netuid}: {e}")
        return False

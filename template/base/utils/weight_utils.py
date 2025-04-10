import numpy as np
import torch
import bittensor as bt
from loguru import logger
from template.base.utils.config import __spec_version__

def normalize_max_weight(x: np.ndarray, limit: float = 0.1) -> np.ndarray:
    epsilon = 1e-7
    weights = x.copy()
    values = np.sort(weights)

    if x.sum() == 0 or len(x) * limit <= 1:
        return np.ones_like(x) / x.size
    else:
        estimation = values / values.sum()
        if estimation.max() <= limit:
            return weights / weights.sum()

        cumsum = np.cumsum(estimation, 0)
        estimation_sum = np.array([(len(values) - i - 1) * estimation[i] for i in range(len(values))])
        n_values = (estimation / (estimation_sum + cumsum + epsilon) < limit).sum()

        cutoff_scale = (limit * cumsum[n_values - 1] - epsilon) / (1 - (limit * (len(estimation) - n_values)))
        cutoff = cutoff_scale * values.sum()

        weights[weights > cutoff] = cutoff
        y = weights / weights.sum()
        return y

def convert_weights_and_uids_for_emit(weighted_scores):
    logger.info(f"Weighted scores: {weighted_scores}")
    sorted_scores = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)
    uids = [int(item[0]) for item in sorted_scores]
    weights = [item[1] for item in sorted_scores]
    return weights, uids

def process_weights_for_netuid(weights: list[float], uids: list[int], netuid: int, subtensor: bt.subtensor, wallet: bt.wallet) -> bool:
    try:
        if any(np.isnan(weights)):
            logger.warning("Weights contain NaN values. Skipping weight setting.")
            return False

        weights = torch.tensor(weights, dtype=torch.float32)
        weights = torch.nn.functional.normalize(weights, p=1.0, dim=0)

        filtered_uids = [uid for i, uid in enumerate(uids) if weights[i] > 0]
        filtered_weights = weights[weights > 0].tolist()
        filtered_weights = [float(w) for w in filtered_weights]

        logger.info(f"Setting weights: UIDs: {filtered_uids}, Weights: {filtered_weights}")
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
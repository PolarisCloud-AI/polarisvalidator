import numpy as np
import torch
import random
import bittensor as bt
from loguru import logger
from template.base.utils.config import __spec_version__

def normalize_max_weight(x: np.ndarray, limit: float = 0.1, total_burn_emission: float = 0.0) -> np.ndarray:
    """
    Normalizes weights to sum to (1 - total_burn_emission) with a per-miner limit.
    
    Args:
        x: Array of raw scores.
        limit: Maximum weight per miner (default: 0.1).
        total_burn_emission: Total weight reserved for burners (default: 0.0).
    
    Returns:
        Normalized weights summing to (1 - total_burn_emission).
    """
    weights = x.copy()
    
    if weights.size == 0 or weights.sum() == 0:
        return np.zeros_like(weights)
    
    weights = weights / weights.sum() * (1.0 - total_burn_emission)
    
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
        weights = weights / weights.sum() * (1.0 - total_burn_emission)
    
    return weights

def convert_weights_and_uids_for_emit(
    weighted_scores,
    burners=None,
    total_burn_emission=0.0,
    burner_emission=0.0,
    last_mechanism_step_block=None
):
    """
    Converts weighted scores to weights and UIDs, including burners.
    
    Args:
        weighted_scores: Dict of UID to score.
        burners: List of burner UIDs.
        total_burn_emission: Total weight for burners.
        burner_emission: Weight per secondary burner.
        last_mechanism_step_block: Block number for deterministic burner selection.
    
    Returns:
        Tuple of (weights, uids).
    """
    burners = burners or []
    weighted_scores = weighted_scores.copy()
    
    total_score = sum(weighted_scores.values())
    if total_score <= 0:
        if not burners:
            logger.warning("No scores and no burners. Returning empty weights.")
            return [], []
        uids = burners.copy()
        if len(burners) > 1 and last_mechanism_step_block is not None:
            main_burner = random.Random(last_mechanism_step_block).choice(burners)
            weights = [total_burn_emission - (len(burners) - 1) * burner_emission if uid == main_burner else burner_emission for uid in uids]
        else:
            weights = [total_burn_emission / len(burners)] * len(burners)
        logger.info(f"Burner-only weights: UIDs={uids}, Weights={weights}")
        return weights, uids
    
    regular_uids = [int(uid) for uid in weighted_scores.keys() if int(uid) not in burners]
    regular_scores = np.array([weighted_scores.get(str(uid), 0.0) for uid in regular_uids], dtype=np.float32)
    
    regular_weights = normalize_max_weight(regular_scores, limit=0.1, total_burn_emission=total_burn_emission)
    
    uids = regular_uids.copy()
    weights = regular_weights.tolist()
    
    if burners and total_burn_emission > 0:
        if len(burners) > 1 and last_mechanism_step_block is not None:
            main_burner = random.Random(last_mechanism_step_block).choice(burners)
            for uid in burners:
                uids.append(uid)
                if uid == main_burner:
                    weights.append(total_burn_emission - (len(burners) - 1) * burner_emission)
                else:
                    weights.append(burner_emission)
        else:
            burner_weight = total_burn_emission / len(burners)
            uids.extend(burners)
            weights.extend([burner_weight] * len(burners))
    
    logger.info(f"Converted weights: UIDs={uids}, Weights={weights}, Sum={sum(weights)}")
    return weights, uids

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

def select_burner_uids(
    metagraph: bt.metagraph,
    subtensor: bt.subtensor,
    num_burners: int = 3,
    stake_threshold: float = 0.9,
    config_burners: list[int] = None,
    last_mechanism_step_block: int = None
) -> list[int]:
    """
    Dynamically selects burner miner UIDs based on stake and registration time.
    
    Args:
        metagraph: Bittensor metagraph.
        subtensor: Bittensor subtensor instance.
        num_burners: Desired number of burners.
        stake_threshold: Top percentile of stake to consider.
        config_burners: Fallback burner UIDs from config.
        last_mechanism_step_block: Block for deterministic shuffling.
    
    Returns:
        List of burner UIDs.
    """
    try:
        config_burners = config_burners or []
        valid_config_burners = [uid for uid in config_burners if uid < len(metagraph.hotkeys)]
        if len(valid_config_burners) >= num_burners:
            logger.info(f"Using {len(valid_config_burners)} burners from config: {valid_config_burners}")
            return valid_config_burners[:num_burners]
        
        stakes = np.array(metagraph.S, dtype=np.float32)
        uids = np.arange(len(metagraph.hotkeys), dtype=np.int32)
        valid_mask = stakes > 0
        valid_uids = uids[valid_mask]
        valid_stakes = stakes[valid_mask]
        
        if len(valid_uids) < num_burners:
            logger.warning(f"Only {len(valid_uids)} valid miners found, returning all")
            return valid_uids.tolist()

        stake_percentile = np.percentile(valid_stakes, stake_threshold * 100)
        high_stake_mask = valid_stakes >= stake_percentile
        candidate_uids = valid_uids[high_stake_mask]
        candidate_stakes = valid_stakes[high_stake_mask]
        
        if len(candidate_uids) < num_burners:
            logger.warning(f"Only {len(candidate_uids)} high-stake miners found, using all")
            num_burners = len(candidate_uids)

        candidate_indices = np.argsort(candidate_uids)
        candidate_uids = candidate_uids[candidate_indices]
        candidate_stakes = candidate_stakes[candidate_indices]
        
        if last_mechanism_step_block is not None:
            rng = np.random.default_rng(last_mechanism_step_block)
            indices = np.arange(len(candidate_uids))
            rng.shuffle(indices)
            candidate_uids = candidate_uids[indices]
            candidate_stakes = candidate_stakes[indices]
        
        selected_uids = candidate_uids[:num_burners].tolist()
        logger.info(f"Selected {len(selected_uids)} burner UIDs: {selected_uids}")
        return selected_uids
    
    except Exception as e:
        logger.error(f"Error selecting burner UIDs: {e}")
        return config_burners[:num_burners] if config_burners else []
import json
import os
import numpy as np
from loguru import logger

def load_state(validator):
    """
    Loads the validator state from a file.
    
    Args:
        validator: The validator instance (e.g., PolarisNode).
    """
    try:
        logger.info("Loading validator state.")
        state_path = os.path.join(validator.config.neuron.full_path, "state.json")
        if not os.path.exists(state_path):
            logger.warning("No previous state file found. Starting fresh.")
            # Ensure critical attributes are initialized
            validator.step = getattr(validator, "step", 0)
            validator.scores = getattr(validator, "scores", np.zeros(validator.metagraph.n, dtype=np.float32))
            validator.hotkeys = getattr(validator, "hotkeys", validator.metagraph.hotkeys.copy())
            validator.last_weight_update_block = getattr(validator, "last_weight_update_block", 0)
            validator.tempo = getattr(validator, "tempo", validator.subtensor.tempo(validator.config.netuid))
            validator.weights_rate_limit = getattr(validator, "weights_rate_limit", validator.tempo)
            validator.burner_uids = getattr(validator, "burner_uids", [])
            return

        with open(state_path, "r") as f:
            state = json.load(f)
        
        validator.step = state.get("step", 0)
        validator.scores = np.array(
            state.get("scores", np.zeros(validator.metagraph.n, dtype=np.float32).tolist()),
            dtype=np.float32
        )
        validator.hotkeys = state.get("hotkeys", validator.metagraph.hotkeys.copy())
        validator.last_weight_update_block = state.get("last_weight_update_block", 0)
        validator.tempo = state.get("tempo", validator.subtensor.tempo(validator.config.netuid))
        validator.weights_rate_limit = state.get("weights_rate_limit", validator.tempo)
        validator.burner_uids = state.get("burner_uids", [])
        
        logger.info("State loaded successfully.")
        logger.debug(f"Loaded state: step={validator.step}, "
                    f"scores_sum={validator.scores.sum()}, "
                    f"hotkeys_len={len(validator.hotkeys)}, "
                    f"last_weight_update_block={validator.last_weight_update_block}, "
                    f"tempo={validator.tempo}, "
                    f"weights_rate_limit={validator.weights_rate_limit}, "
                    f"burner_uids={validator.burner_uids}")
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        # Set defaults to ensure validator can continue
        validator.step = getattr(validator, "step", 0)
        validator.scores = getattr(validator, "scores", np.zeros(validator.metagraph.n, dtype=np.float32))
        validator.hotkeys = getattr(validator, "hotkeys", validator.metagraph.hotkeys.copy())
        validator.last_weight_update_block = getattr(validator, "last_weight_update_block", 0)
        validator.tempo = getattr(validator, "tempo", validator.subtensor.tempo(validator.config.netuid))
        validator.weights_rate_limit = getattr(validator, "weights_rate_limit", validator.tempo)
        validator.burner_uids = getattr(validator, "burner_uids", [])

def save_state(validator):
    """
    Saves the validator state to a file.
    
    Args:
        validator: The validator instance (e.g., PolarisNode).
    """
    try:
        logger.info("Saving validator state.")
        # Debug log to trace attributes
        state = {
            "step": getattr(validator, "step", 0),
            "scores": validator.scores.tolist() if hasattr(validator, "scores") else np.zeros(validator.metagraph.n, dtype=np.float32).tolist(),
            "hotkeys": getattr(validator, "hotkeys", validator.metagraph.hotkeys.copy()),
            "last_weight_update_block": getattr(validator, "last_weight_update_block", 0),
            "tempo": getattr(validator, "tempo", validator.subtensor.tempo(validator.config.netuid)),
            "weights_rate_limit": getattr(validator, "weights_rate_limit", getattr(validator, "tempo", validator.subtensor.tempo(validator.config.netuid))),
            "burner_uids": getattr(validator, "burner_uids", [])
        }
        
        os.makedirs(validator.config.neuron.full_path, exist_ok=True)
        state_path = os.path.join(validator.config.neuron.full_path, "state.json")
        with open(state_path, "w") as f:
            json.dump(state, f)
        logger.info(f"State saved successfully to {state_path}.")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
import json
import os
import numpy as np
from loguru import logger

def load_state(validator):
    """
    Loads the validator state from a file and returns state data.
    
    Args:
        validator: The validator instance (e.g., PolarisNode).
        
    Returns:
        dict: State data or None if no state file exists
    """
    try:
        logger.info("Loading validator state.")
        state_path = os.path.join(validator.config.neuron.full_path, "state.json")
        if not os.path.exists(state_path):
            logger.warning("No previous state file found. Starting fresh.")
            return None

        with open(state_path, "r") as f:
            state = json.load(f)
        
        logger.info("State loaded successfully.")
        logger.debug(f"Loaded state: step={state.get('step', 0)}, "
                    f"scores_count={len(state.get('scores', []))}, "
                    f"last_weight_update_block={state.get('last_weight_update_block', 0)}")
        
        return state
        
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        return None

def save_state(validator, state_data=None):
    """
    Saves the validator state to a file.
    
    Args:
        validator: The validator instance (e.g., PolarisNode).
        state_data: Optional state data dict to save. If None, uses validator attributes.
    """
    try:
        logger.info("Saving validator state.")
        
        if state_data is not None:
            # Use provided state data (new approach)
            state = state_data
        else:
            # Fallback to old approach for backward compatibility
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
            json.dump(state, f, indent=2)
        logger.info(f"State saved successfully to {state_path}.")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
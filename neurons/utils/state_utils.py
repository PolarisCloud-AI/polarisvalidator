import json
import os
import numpy as np
from loguru import logger

def load_state(validator):
    try:
        logger.info("Loading validator state.")
        with open(os.path.join(validator.config.neuron.full_path, "state.json"), "r") as f:
            state = json.load(f)
            validator.step = state.get("step", 0)
            validator.scores = np.array(state.get("scores", np.zeros(validator.metagraph.n, dtype=np.float32)), dtype=np.float32)
            validator.hotkeys = state.get("hotkeys", validator.metagraph.hotkeys.copy())
            validator.last_weight_update_block = state.get("last_weight_update_block", 0)
            validator.tempo = state.get("tempo", validator.subtensor.tempo(validator.config.netuid))
            validator.weights_rate_limit = state.get("weights_rate_limit", validator.tempo)
    except FileNotFoundError:
        logger.warning("No previous state found. Starting fresh.")
    except Exception as e:
        logger.error(f"Error loading state: {e}")

def save_state(validator):
    try:
        logger.info("Saving validator state.")
        state = {
            "step": validator.step,
            "scores": validator.scores.tolist() if hasattr(validator, 'scores') else np.zeros(validator.metagraph.n, dtype=np.float32).tolist(),
            "hotkeys": validator.hotkeys if hasattr(validator, 'hotkeys') else validator.metagraph.hotkeys.copy(),
            "last_weight_update_block": validator.last_weight_update_block if hasattr(validator, 'last_weight_update_block') else 0,
            "tempo": validator.tempo if hasattr(validator, 'tempo') else validator.subtensor.tempo(validator.config.netuid),
            "weights_rate_limit": validator.weights_rate_limit if hasattr(validator, 'weights_rate_limit') else validator.tempo
        }
        os.makedirs(validator.config.neuron.full_path, exist_ok=True)
        with open(os.path.join(validator.config.neuron.full_path, "state.json"), "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
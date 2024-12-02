import argparse
import asyncio
import uuid
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def get_config():
    parser = argparse.ArgumentParser()
    
    # Bittensor arguments
    parser.add_argument('--netuid', type=int, default=1,
                      help='Network UID')
    parser.add_argument('--subtensor.network', type=str, default='test',
                      help='Subtensor network')
    parser.add_argument('--wallet.name', type=str, default='miner',
                      help='Wallet name')
    parser.add_argument('--wallet.hotkey', type=str, default='default',
                      help='Wallet hotkey')
    
    # Training arguments
    parser.add_argument('--model_type', type=str, required=True,
                      choices=['gpt2', 'llama2'],
                      help='Type of model to train')
    parser.add_argument('--dataset_id', type=str, required=True,
                      help='Dataset ID on HuggingFace')
    parser.add_argument('--epochs', type=int, default=1,
                      help='Number of training epochs')
    parser.add_argument('--batch_size', type=int,
                      help='Training batch size')
    parser.add_argument('--learning_rate', type=float,
                      help='Learning rate')
    parser.add_argument('--job_id', type=str, default=str(uuid.uuid4()),
                      help='Unique job ID')
    parser.add_argument('--hf_token', type=str, required=True,
                      help='HuggingFace API token')
    parser.add_argument('--device', type=str, default='cuda',
                      help='Device to use for training')

    config = parser.parse_args()

    # Set model-specific defaults
    if config.model_type == 'gpt2':
        config.model_name = 'openai-community/gpt2'
        config.batch_size = config.batch_size or 16
        config.learning_rate = config.learning_rate or 5e-5
    elif config.model_type == 'llama2':
        config.model_name = 'NousResearch/Llama-2-7b-chat-hf'
        config.batch_size = config.batch_size or 8
        config.learning_rate = config.learning_rate or 2e-5
    elif config.model_type == 'openelm':
        config.model_name = 'apple/OpenELM-270M'
        config.batch_size = config.batch_size or 2
        config.learning_rate = config.learning_rate or 5e-5
    elif config.model_type == 'gemma':
        config.model_name = 'google/gemma-2b'
        config.batch_size = config.batch_size or 4
        config.learning_rate = config.learning_rate or 2e-4
    else:
        print("Please specify the model type to train")

    return config

def run_miner(config):
    try:
        # Import the appropriate miner class based on model type
        if config.model_type == 'gpt2':
            from gpt2_miner import TrainingMiner as MinerClass
        elif config.model_type == 'llama2':
            from llama2_miner import Llama2TrainingMiner as MinerClass
        elif config.model_type == 'openelm':
            from openelm_miner import OpenELMTrainingMiner as MinerClass
        elif config.model_type == 'gemma':
            from gemma_miner import GemmaFineTuningMiner as MinerClass
        else:
            print("Please specify the model type to train")
            
        # Initialize the selected miner with configuration
        miner = MinerClass(
            model_name=config.model_name,
            dataset_id=config.dataset_id,
            epochs=config.epochs,
            batch_size=config.batch_size,
            learning_rate=config.learning_rate,
            device=config.device,
            hf_token=config.hf_token,
            job_id=config.job_id
        )

        # Define main async function
        async def main():
            try:
                await miner.run_training_loop()
            except KeyboardInterrupt:
                print("\nMiner stopped by user.")
            except Exception as e:
                print(f"\nError running miner: {str(e)}")
                raise

        # Run the miner
        asyncio.run(main())
        
    except ImportError as e:
        print(f"Error: Could not import miner module. Make sure both gpt2_miner.py and "
              f"llama2_miner.py are in the same directory as run_miners.py\n{str(e)}")
    except Exception as e:
        print(f"Error initializing miner: {str(e)}")

if __name__ == "__main__":
    config = get_config()
    run_miner(config)
import wandb
import os

def initialize_wandb(job_id, miner_id):
    wandb_api_key="650810c567842db08fc2707d0668dc568cad00b4"
    wandb.login(key=wandb_api_key)  
    run_name = f"miner_{str(miner_id)}"
    wandb.init(
        project=str(job_id),
        name=run_name,
        config={
            "framework": "PyTorch",
        }
    )

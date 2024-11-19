import wandb
import os

def initialize_wandb(job_id, miner_id):
    wandb_api_key="650810c567842db08fc2707d0668dc568cad00b4"
    wandb.login(key=wandb_api_key)  
    wandb.init(
        project=job_id,
        name=miner_id,
        config={
            "framework": "PyTorch",
        }
    )

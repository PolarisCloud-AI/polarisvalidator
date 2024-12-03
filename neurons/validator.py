import time
import json
import requests
import torch
import bittensor as bt
from template.base.validator import BaseValidatorNeuron
from template.protocol import TrainingProtocol
import asyncio
import os
from dotenv import load_dotenv
import logging
from huggingface_hub import HfApi
from typing import List, Dict, Optional
from neurons.utils.HFManager import fetch_training_metrics_commits
from neurons.utils.Helper import fetch_open_jobs, update_job_status
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Add the utils directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))

load_dotenv()  # Load environment variables from .env file

class TrainingValidator(BaseValidatorNeuron):
    def __init__(self, config=None, repo_name=None):
        super().__init__(config=config)
        
        self.repo_name = repo_name

    def read_commits(self):
        """Read commits from the central Hugging Face repository."""
        commits = fetch_training_metrics_commits(repo_id=self.repo_name)
        return commits

    def group_commits(self, commits):
        """Group commits by job."""
        job_groups = {}
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(fetch_open_jobs())
        for commit in commits:
            job_id = commit["metrics"]["job_id"]
            if job_id in result:
                if job_id not in job_groups:
                    job_groups[job_id] = []
                job_groups[job_id].append(commit)
        return job_groups

    def load_and_evaluate(self, job_groups):
        """Load and evaluate each job."""
        
        for job_id, commits in job_groups.items():
            metrics_list = self.extract_metrics_by_job_id(job_id, commits)
            if metrics_list:
                print(f"rewarding and scoring miners for jobid {job_id}")
                results = self.score_miners(metrics_list)
                for miner_uid, score in results['rewards'].items():
                    self.update_scores(score, miner_uid)
            self.mark_job_as_done(job_id)

    def extract_metrics_by_job_id(self, job_id, commits):
        # Initialize an empty list to store the results
        results = []
        
        # Iterate over each commit in the commits list
        for commit in commits:
            # Check if the 'job_id' in the commit matches the input job_id
            if commit['job_id'] == job_id:
                # Extract the needed information
                miner_uid = commit['miner_uid']
                final_loss = commit['metrics']['final_loss']
                model_repo = commit['model_repo']
                
                # Append the extracted data to the results list
                results.append({
                    'miner_uid': miner_uid,
                    'final_loss': final_loss,
                    'model_repo': model_repo
                })
        return results

    def score_miners(self, metrics_list):
        """
        Scores miners based on their final_loss, rewards the best miner, and ranks all miners.

        Parameters:
            metrics_list (list): A list of dictionaries containing 'miner_uid', 'final_loss', and 'model_repo'.

        Returns:
            dict: A dictionary containing:
                - 'ranked_miners': List of miners with their ranking positions, 'miner_uid', and 'final_loss'.
                - 'best_miner': Details of the best miner with 'miner_uid', 'final_loss', and 'model_repo'.
                - 'rewards': A dictionary mapping 'miner_uid' to their reward (1 token for the best miner).
        """
        # Sort the miners based on their final_loss in ascending order
        sorted_miners = sorted(metrics_list, key=lambda x: x['final_loss'])
        
        # Assign positions (rankings) to the miners
        ranked_miners = []
        for position, miner in enumerate(sorted_miners, start=1):
            ranked_miners.append({
                'position': position,
                'miner_uid': miner['miner_uid'],
                'final_loss': miner['final_loss']
            })
        
        # Identify the best miner (the one with the lowest final_loss)
        best_miner = sorted_miners[0]
        
        # Award one token to the best miner
        rewards = {best_miner['miner_uid']: 1.0}
        
        # Extract details of the best miner
        best_miner_info = {
            'miner_uid': best_miner['miner_uid'],
            'final_loss': best_miner['final_loss'],
            'model_repo': best_miner['model_repo']
        }
        
        # Return the results
        return {
            'ranked_miners': ranked_miners,
            'best_miner': best_miner_info,
            'rewards': rewards
        }

    def mark_job_as_done(self, job_id):
        """Mark the evaluated job as complete."""
        self.update_job_status(job_id)


    async def forward(self):
        """Main execution method."""
        try:
            logging.info("Fetching commits...")
            commits = self.read_commits()
            logging.info("Grouping jobs ...")
            job_groups = self.group_commits(commits)
            self.load_and_evaluate(job_groups)
        except Exception as e:
            logging.error(f"Error in forward: {str(e)}")

    async def __aenter__(self):
        await self.setup()  # Assuming you have a setup method
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()  # Assuming you have a cleanup method

    async def setup(self):
        # Initialization logic here
        pass

    async def cleanup(self):
        # Cleanup logic here
        pass

# Main execution
if __name__ == "__main__":
    async def main():
        async with TrainingValidator(repo_name="Tobius/yogpt_v1") as validator:
            while True:
                bt.logging.info(f"Validator running... {time.time()}")
                await validator.forward()
                await asyncio.sleep(5) 

    asyncio.run(main())

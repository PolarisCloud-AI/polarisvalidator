# # import paramiko
# # import os

# # def connect_to_remote_machine(host, port=22, username="user"):
# #     # Initialize SSH client
# #     client = paramiko.SSHClient()
# #     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
# #     # Path to your private key
# #     key_path = os.path.join(os.path.dirname(_file_), "ssh_host_key")
    
# #     try:
# #         # Connect using the private key
# #         client.connect(
# #             hostname=host,
# #             port=port,
# #             username=username,
# #             key_filename=key_path,
# #             timeout=5
# #         )
        
# #         print(f"Successfully connected to {username}@{host}:{port}")
        
# #         # Execute a command
# #         stdin, stdout, stderr = client.exec_command("hostname")
# #         print(f"Remote hostname: {stdout.read().decode().strip()}")
        
# #         # Close the connection
# #         client.close()
# #         return True
        
# #     except Exception as e:
# #         print(f"Failed to connect: {str(e)}")
# #         return False

# # # Example usage
# # connect_to_remote_machine("192.168.1.100", username="admin")


import json
import re
import logging
from datetime import datetime,timedelta
import requests
import tenacity
from typing import Dict, Any, List, Union
from loguru import logger
import numpy as np
from collections import defaultdict


# # from neurons.utils.pogs import execute_ssh_tasks, compare_compute_resources, compute_resource_score
def get_unverified_miners() -> dict[str, dict]:
    try:
        response = requests.get("https://polaris-test-server.onrender.com/api/v1/miners")
        response.raise_for_status()
        miners_data = response.json()
        return {
            miner["id"]: miner.get("compute_resources", {})
            for miner in miners_data
            if miner.get("status") == "rejected"
        }
    except Exception as e:
        print(f"No data found: {e}")
        return {}
# # unverified_miners=get_unverified_miners()
# # miner="OcaIXLgNDnwAIiDETFiM"
# # miner_resources = unverified_miners.get(miner)
# # print(f"miner resources {miner_resources[0]}")


# # def execute_ssh_tasks(miner_id: str) -> Dict[str, Any]:
# #     """
# #     Execute SSH tasks for a given miner ID by calling the orchestrator API.
    
# #     Args:
# #         miner_id (str): The ID of the miner to execute tasks for.
    
# #     Returns:
# #         Dict[str, Any]: A dictionary containing:
# #             - status: "success" or "error"
# #             - message: Descriptive message about the outcome
# #             - task_results: Dictionary of task results or empty dict if failed
# #     """
# #     logger.info(f"Executing SSH tasks for miner {miner_id}")
    
# #     # Validate miner_id
# #     if not isinstance(miner_id, str) or not miner_id.strip():
# #         logger.error("Invalid miner_id: must be a non-empty string")
# #         return {
# #             "status": "error",
# #             "message": "Invalid miner_id: must be a non-empty string",
# #             "task_results": {}
# #         }
    
# #     url = url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/perform-tasks"
# #     logger.debug(f"Requesting SSH tasks at: {url}")
    
# #     try:
# #         response = requests.get(url, timeout=10)
# #         logger.info(f"Response status: {response.status_code}")
        
# #         if response.status_code == 200:
# #             try:
# #                 result = response.json()
# #                 logger.debug(f"Server response: {result}")
                
# #                 if result.get("status") != "success":
# #                     logger.error(f"Server error: {result.get('message', 'Unknown error')}")
# #                     return {
# #                         "status": "error",
# #                         "message": result.get("message", "Server reported failure"),
# #                         "task_results": {}
# #                     }
                
# #                 # Extract task_results (adjust key based on actual server response)
# #                 task_results = result.get("task_results", result.get("specifications", {}))
# #                 logger.info("SSH tasks executed successfully")
# #                 return {
# #                     "status": "success",
# #                     "message": "SSH tasks executed successfully",
# #                     "task_results": task_results
# #                 }
# #             except ValueError as e:
# #                 logger.error(f"Failed to parse JSON response: {str(e)}")
# #                 return {
# #                     "status": "error",
# #                     "message": f"Invalid server response: {str(e)}",
# #                     "task_results": {}
# #                 }
# #         else:
# #             logger.error(f"Unexpected status code: {response.status_code}")
# #             return {
# #                 "status": "error",
# #                 "message": f"Server returned status code {response.status_code}",
# #                 "task_results": {}
# #             }
            
# #     except requests.exceptions.RequestException as e:
# #         logger.error(f"Request failed for {url}: {str(e)}")
# #         return {
# #             "status": "error",
# #             "message": f"Request error: {str(e)}",
# #             "task_results": {}
# #         }
# #     except Exception as e:
# #         logger.error(f"Unexpected error executing SSH tasks: {str(e)}")
# #         return {
# #             "status": "error",
# #             "message": f"Unexpected error: {str(e)}",
# #             "task_results": {}
# #         }



def update_miner_status(miner_id: str, status: str, percentage: float) -> str:
    url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/status"
    headers = {"Content-Type": "application/json"}
    payload = {"status": status}
    try:
        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("status", "unknown")
    except Exception as e:
        print(f"Error updating miner {miner_id}: {e}")
        return None

def update_rejected_miners_to_pending():
    # Get the list of rejected miners
    unverified_miners = get_unverified_miners()
    
    # Extract miner IDs
    miner_ids = list(unverified_miners.keys())
    
    if not miner_ids:
        print("No miners with 'rejected' status found.")
        return
    
    print(f"Found {len(miner_ids)} miners with 'rejected' status: {miner_ids}")
    
    # Update each miner's status to pending_verification
    for miner_id in miner_ids:
        print(f"Updating miner {miner_id} to 'pending_verification'...")
        new_status = update_miner_status(miner_id, "pending_verification", 0.0)
        if new_status:
            print(f"Successfully updated miner {miner_id} to status: {new_status}")
        else:
            print(f"Failed to update miner {miner_id}")
update_rejected_miners_to_pending()

# # def get_filtered_miners() -> tuple[Dict[str, str], List[str]]:
# #     try:
# #         response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
# #         response.raise_for_status()
# #         miners_data = response.json()
        
# #         # Initialize outputs
# #         miners_to_reject = []
        
# #         # Process each miner
# #         for miner in miners_data:
# #             miner_id = miner.get("miner_id")
# #             miner_uid = miner.get("miner_uid")
# #             print(f"miner uid {miner_id} and {miner_uid}")
# #             if miner_uid is None:
# #                 miners_to_reject.append(miner_id)
        
# #         return miners_to_reject
    
# #     except Exception as e:
# #         logger.error(f"Error fetching filtered miners: {e}")
# #         return {}, []
# # allowed_uids=[2,0,13,131,207]
# # def get_filtered_miners(allowed_uids: List[int]) -> tuple[Dict[str, str], List[str]]:
# #     try:
# #         response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
# #         response.raise_for_status()
# #         miners_data = response.json()
        
# #         # Initialize outputs
# #         filtered_miners = {}
# #         miners_to_reject = []
        
# #         # Process each miner
# #         for miner in miners_data:
# #             miner_id = miner.get("miner_id")
# #             miner_uid = miner.get("miner_uid")
# #             if miner_uid is None:
# #                 miners_to_reject.append(miner_id)
# #             elif int(miner_uid) in allowed_uids:
# #                 # Include miners with valid miner_uid in allowed_uids
# #                 filtered_miners[miner_id] = str(miner_uid)
        
# #         return filtered_miners, miners_to_reject
    
# #     except Exception as e:
# #         logger.error(f"Error fetching filtered miners: {e}")
# #         return {}, []
    
# filtered,miners_to_reject =get_filtered_miners(allowed_uids)
# print(miners_to_reject)
# print(filtered)
# # def get_rejected_miners() -> list[str]:
# #     try:
# #         # Get current date dynamically and calculate 2 days ago
# #         today = datetime.now()
# #         two_days_ago = today - timedelta(days=2)
        
# #         # Fetch data from API
# #         response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
# #         response.raise_for_status()
# #         miners_data = response.json()
        
# #         # Filter miners with status "rejected" and created 2 days ago
# #         rejected_miners = [
# #             miner["id"]
# #             for miner in miners_data
# #             if miner.get("status") == "pending_verification"
# #             and miner.get("created_at")  # Ensure created_at exists
# #             and datetime.fromisoformat(miner["created_at"].replace("Z", "+00:00")).date() <= two_days_ago.date()
# #         ]
        
# #         return rejected_miners
    
# #     except Exception as e:
# #         print(f"No data found: {e}")
# #         return []
    


# # def delete_miner(miner_id: str) -> bool:
# #     url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}"
# #     try:
# #         response = requests.delete(url)
# #         response.raise_for_status()
# #         return True
# #     except Exception as e:
# #         print(f"Error deleting miner {miner_id}: {e}")
# #         return False
    

# # def delete_rejected_miners():
# #     # Get the list of rejected miners created 2 days ago
# #     miner_ids = get_rejected_miners()
    
# #     # Format the date 2 days ago for output
# #     two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
# #     if not miner_ids:
# #         print(f"No rejected miners created on {two_days_ago} found.")
# #         return
    
# #     print(f"Found {len(miner_ids)} rejected miners created on {two_days_ago}: {miner_ids}")
    
# #     # Delete each miner
# #     for miner_id in miner_ids:
# #         print(f"Deleting miner {miner_id}...")
# #         if delete_miner(miner_id):
# #             print(f"Successfully deleted miner {miner_id}")
# #         else:
# #             print(f"Failed to delete miner {miner_id}")
    
# # if __name__ == "__main__":
# #     delete_rejected_miners()

# # 
logger = logging.getLogger("remote_access")

# 
# from neurons.utils.pow import  perform_ssh_tasks
# from neurons.utils.compute_score import pow_tasks
# from neurons.utils.pogs import compare_compute_resources
# import asyncio
# data={'0WKTOGat9IUVDWIvbynF': 49, '0sy5sozr8YlBQGYU0OuV': 47, '1arXF3eSoXrzJbdsYFFC': 19, '2LpLqWHWf7AUVY2vPy7i': 46, '2dsYOnw7cY4ARdcX4yyx': 29, '340NevUIWzoVhiYh669j': 37, '4xegUUWQnAcydIapQR4a': 30, '8hvxxUmM16AAouBqmRsr': 61, '9ASVBbVjvD1DGWYPSmyB': 12, 'CQcHZz7sWxptocMqV5bS': 13, 'DnA8lTBnRTPu2d1dURMb': 17, 'E3iNoIeQgz1mDI8FqFRA': 2, 'MQ96vMXYB6J37ZV9llJm': 63, 'QPqj8HRJaKH7IxWCccho': 29, 'XML66pyn1S5APUwxJydi': 23, 'YILsF8Qxxr8UlKkwLzKt': 33, 'ZmtqC29ZCqhDYQCpHaIG': 6, 'aBid5pRnNo7Jv68Di2OZ': 62, 'aETz6JkF5PdrZaAN0Htw': 35, 'b7q1mnJYeAkMm0eeyIEa': 53, 'eKScaWF2H96SAdPk774y': 19, 'iZZ5mjvP7VfLorGOlT0s': 24, 'jXCfREtMUnWNyY5xuosp': 12, 'jiSqAr1BmdbrABvWOTcU': 48, 'k4nE5C4mRwcs1RJwWRUq': 21, 'navcdCleGl4qsbRNuzZN': 3, 'p7opgZyOqn8cGPadKEZU': 28, 'qIixWdT07862KFu87tIa': 4, 's663AjJ38d9YEWvrn3Kn': 57, 'tGVsmZHm2DTuFK4PgTgY': 13, 'tHInHJ6VnoBY2PKd5WDR': 22, 'uMtcUAZUQIKS1iCtTYUv': 48, 'vMB61leym52C97xv2SfU': 27, 'veZPvA20PexrpUHDPiKb': 40}

# def get_miner_list_with_resources(miner_commune_map: dict[str, str]) -> dict:
#     logger.info(f"hhewhehehe {miner_commune_map}")
#     try:
#         response = requests.get("https://polaris-test-server.onrender.com/api/v1/miners")
#         response.raise_for_status()
#         miners_data = response.json()
#         return {
#             miner["id"]: {
#                 "compute_resources": miner["compute_resources"],
#                 "miner_uid": miner_commune_map.get(miner["id"])
#             }
#             for miner in miners_data
#             if miner["id"] in miner_commune_map
#         }
#     except Exception as e:
#         logger.error(f"Error fetching miner list with resources: {e}")
#         return {}

# async def main():
#     miner_id = "0sy5sozr8YlBQGYU0OuV"
#     result = get_miner_list_with_resources(data)
#     miner_resource = result.get(miner_id)
#     wrk =miner_resource["compute_resources"][0]["network"]["ssh"]
#     result2 = await perform_ssh_tasks(wrk)  # Await the coroutine
#     specs = result2.get("task_results", {})
#     resource_type =miner_resource["compute_resources"][0]["resource_type"]
#     score_vall =calculate_compute_score(resource_type,specs)
#     comparison_score = await pow_tasks(wrk)
#     print(f"new stauff {comparison_score}")

# if __name__ == "__main__":
#     asyncio.run(main())


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
# def get_unverified_miners() -> dict[str, dict]:
#     try:
#         response = requests.get("https://polaris-test-server.onrender.com/api/v1/miners")
#         response.raise_for_status()
#         miners_data = response.json()
#         return {
#             miner["id"]: miner.get("compute_resources", {})
#             for miner in miners_data
#             if miner.get("status") == "rejected"
#         }
#     except Exception as e:
#         print(f"No data found: {e}")
#         return {}
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



# def update_miner_status(miner_id: str, status: str, percentage: float) -> str:
#     url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/status"
#     headers = {"Content-Type": "application/json"}
#     payload = {"status": status}
#     try:
#         response = requests.patch(url, json=payload, headers=headers)
#         response.raise_for_status()
#         return response.json().get("status", "unknown")
#     except Exception as e:
#         print(f"Error updating miner {miner_id}: {e}")
#         return None

# def update_rejected_miners_to_pending():
#     # Get the list of rejected miners
#     unverified_miners = get_unverified_miners()
    
#     # Extract miner IDs
#     miner_ids = list(unverified_miners.keys())
    
#     if not miner_ids:
#         print("No miners with 'rejected' status found.")
#         return
    
#     print(f"Found {len(miner_ids)} miners with 'rejected' status: {miner_ids}")
    
#     # Update each miner's status to pending_verification
#     for miner_id in miner_ids:
#         print(f"Updating miner {miner_id} to 'pending_verification'...")
#         new_status = update_miner_status(miner_id, "pending_verification", 0.0)
#         if new_status:
#             print(f"Successfully updated miner {miner_id} to status: {new_status}")
#         else:
#             print(f"Failed to update miner {miner_id}")
# update_rejected_miners_to_pending()

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
data={'7RnrqmhcC8Nr5rD1YmLO': 134}
# data={'04bwZkkZpSP1ioavmVRe': 158, '081Oqu75ZFkm7S6EO9LN': 240, '0FMSrY4xx62xMy9KN6xd': 158, '0WKTOGat9IUVDWIvbynF': 49, '0e8CRALWdml3Pnf27Z4C': 1, '0icypK4pgzlAuTS9c5Kl': 117, '0riqI6Q4Y9CIcqFA8tgO': 186, '0rny3Vhvmne8DKEDHVsa': 192, '0sy5sozr8YlBQGYU0OuV': 47, '0tsNfjpKviJ6jZrG2WUh': 203, '0uUAe3aeK2QDcYbUxzQj': 99, '0wPkDVmtwb1WYqdga71i': 66, '1Eg7uR28urM0AlEFSpj8': 231, '1EhIkNvpPubXZGd573Zm': 97, '1arXF3eSoXrzJbdsYFFC': 19, '1eYBryIJWdHV76gmxT2S': 73, '1jycXfgBunIv7GqFSDgV': 164, '1spnC8cxYgcncqvU73qo': 0, '1wEnm0ZcnWF3JuW355NT': 88, '22LJtOsYm93BY9FRegek': 233, '2DKFzsg0gaaIOvyP9nhL': 97, '2LpLqWHWf7AUVY2vPy7i': 46, '2N3MuHHWoq0AHxwm2Ut2': 49, '2T8Yono9z7HeuBiFC5lc': 84, '2dsYOnw7cY4ARdcX4yyx': 29, '2jN2m0492M9YMpfWKoxA': 251, '2pDgM79QuL0TJ8BV0kq7': 170, '340NevUIWzoVhiYh669j': 37, '3APsdH6RIYoiyd9JYbTS': 50, '3BkSOPHggi9Abw7PSvcE': 175, '3UiPMCOaMqheCmfUCfQv': 63, '3joc5Z84xzObVFnG7FKg': 39, '41SxnzgjAOGtaL5ePiMi': 249, '4EhchXbVdDeizxHJlK4e': 243, '4FRdZepSee2MaufETcDe': 63, '4aYGEHCAIZfs9eqW6Zyq': 103, '4cus7Od9UxkhAd3b2J74': 223, '4eQQsfwqiVsa2Tq2jRS5': 199, '4k2AITwc5ssFsXbpQots': 85, '4r6R71dJ4vyvErClkd9x': 18, '4xegUUWQnAcydIapQR4a': 30, '4zZvLl5pFfbydvcJ1rjH': 209, '53x5q3zIeSrE54LhUmqk': 232, '5FXy6x6R8wPgMBuRtGqc': 203, '5KSVBePo35qH2ABQbCdt': 166, '5Y4fAuTMNEdLZmQkzh5b': 97, '5lOdoOA3VCXy8DB77oet': 152, '5nhKJm3EpPbNOi9B9n5c': 77, '5tOL7jdpat6sMG1kdGHz': 115, '5yTOuv18ptPzPiN06VzG': 104, '66RkSt5JP8FLEASg9Btd': 118, '6W3hfViUMTvrucL4AkmW': 158, '6Zm3qP907FBS0rUE6Whd': 223, '6iHkv8kHiqzsyebxe9dP': 211, '6lqIN9A4fVM23b1YBNBf': 63, '6osulq8hR6oHSCbYY7Kw': 80, '6sIevKH8rfPwK8XxWQcF': 222, '6tPieGNxlh6f9oCcF6Kh': 0, '6ta26nyLZIwg6Qj2cxCR': 94, '6vwYtiUcSz3PWTCYjXMr': 200, '73MouZ0VbVM5hqSxvYz1': 27, '7RnrqmhcC8Nr5rD1YmLO': 134, '7vNTj807zMbJdcxhGe05': 112, '882LN53XUHv9JXpD6WU7': 252, '8Ol1o9uSYf1DYj0cKFIL': 213, '8fuPYK7hsDxtf4aFRogn': 103, '8hvxxUmM16AAouBqmRsr': 61, '8iqtRaIv1TaBMqf6xsbe': 219, '9ASVBbVjvD1DGWYPSmyB': 12, '9NHamtJ2qfZiTYDuFzQy': 250, '9bNKURPAgAt0leX2o9eU': 39, '9d4KAfmPhXNhfsqlltq3': 179, 'A0bel7PDzm5KbjWaPxsg': 184, 'A91HlSx28B5yJfUCHXEz': 63, 'AH3KEUkoQeuTaruKYcHj': 232, 'AJjmbYUdYwBRfQRs2WeX': 99, 'AOoep8Z84sMW3V57Mclc': 106, 'AWWiwutnp7O7XIBNFdf2': 12, 'B14zFYQjX1kD2STC308b': 141, 'BATNDvNCJKvzBgKEOr1n': 166, 'Bb4VubdZMok1cfXBUR6w': 90, 'BgyLLm5JvzmQbEjHZYa8': 107, 'C7KRZtz9ddSJjqMbqEA3': 233, 'CAeObeERUS5JMpYVwlIp': 27, 'CNrPZc8dmBIYe9qcvyX8': 80, 'CQcHZz7sWxptocMqV5bS': 13, 'CbbtTIRzXzbVumXOpj1J': 105, 'D2UxBEP6BkNC3nMTugQ7': 248, 'D63CYkdLlWMaIf5i8Yh8': 103, 'DaPaRHc26J9TKwV4QDZe': 139, 'DnA8lTBnRTPu2d1dURMb': 17, 'DsuQIsNllCNIamVIveqs': 187, 'E4QpIamMLoYsNffk2Izw': 106, 'EIimoD7nnKPLUMdtDWDX': 152, 'EMOvwLoypHqa9V1vcncZ': 229, 'EMPcUVp4WgSrX22ZgVxI': 0, 'Ehu9NHoswgfKePLbTkj0': 191, 'EsFaFAb8RFvX8quj0SZ9': 78, 'EuTWQ1utRSlmhsqyOxCJ': 85, 'F0wy6QD9MnSSHwFf8eil': 230, 'FFVyjiDrdC2p0DNIRooE': 176, 'GMkAHTWBFArdzciK7f9f': 128, 'GYcaqFyVvm3TAkImFYFF': 109, 'GataupE9Is4vwJeIBu4g': 233, 'GccnlU0H3RGR5s5BP6rP': 226, 'GjhCaWtT4CIf1piSoFkU': 63, 'H77hxM1S9cfko0BFqae1': 216, 'HAE7ML6SC5owGWFycHCx': 233, 'HCTiOLS6a6X7qYdMHCmA': 71, 'HDyTezxTLaPF0xwtTZWQ': 76, 'HNeGZT1fO6MMiaFvQXig': 76, 'HgPiXlvOvqYmpct3moTo': 16, 'HnFnHAaZvVFphMnudjnt': 222, 'HnKXNUjoF6oRPnA4bom2': 38, 'IEj6xad3k98Hv7LssVS1': 237, 'IHkLesAOka0VDC0oUM1F': 84, 'IOMcdoI0mY2gLE3H3USf': 63, 'IZDOmm6Xxs5LysowIEi8': 199, 'IxMgfuxMUlhKGzIy9bJk': 13, 'Iyi5dOU30VZxcERR13dC': 55, 'J4wqKHpewMbvp8yaU8Rs': 76, 'JVwomKQkGgyRX6lxxwy6': 62, 'JWxHOLyH6WBrFp00VNHm': 232, 'Jm0yRjsnfmwivZmV4bns': 239, 'JsYvMK8xtKY4lx9mPqfm': 158, 'JynmRVdFw2wYYTgFOaZa': 184, 'KJaxiKrZDEmcFMnKSbnB': 225, 'KOrqZobxXpvxA7T6byoY': 227, 'Kb3SlbFxGNAinDQCbOLq': 144, 'KeGnUMSNssqgSAoDiHwK': 145, 'KmPadhTTI9dozBvXP8F5': 133, 'KsEqoQFRsmKRetueH2aF': 7, 'LB2E7VEtqchGri0Bl2qB': 0, 'LDToI07GM3y89vPmg1kt': 116, 'LUXVnefVWTBlVVQuzyLv': 0, 'LtAopv9otDEnR1TcdEHL': 203, 'LvPSJbE9kIyBvTONrEc2': 195, 'M1kMP40ZaaAuX3s5ciCz': 146, 'M4XIJeiCThGaxZQcN5H9': 13, 'M60nA9uDZMLDT3V6a1Ak': 218, 'MFHh8lRpWKL4ucFkxZZX': 218, 'MPf2Xl4mwNpXJToWsuHo': 230, 'MQ96vMXYB6J37ZV9llJm': 63, 'MT4O1PvKSDOcR5qOLuOW': 197, 'MflXMI4aMWNLoyC8z8HI': 162, 'N4jfmWUvQ1Yfd24dBUeM': 117, 'ND0e3MtUuukQR2PflDgL': 40, 'NKq72ntMqp6878pGWv1a': 3, 'NTOadeiCOeRPj8vwoo9e': 22, 'Nis8zIqgXUCISj8SMo8G': 177, 'NuOZRx0KMk7F81Hqxtco': 38, 'NyKoFh9xhRzKERPBuft2': 217, 'OGyw7st2uWf3d5CUbyUk': 158, 'OavzlQhRKlbZWOplNoBU': 227, 'OlAcCHLSkxjEZwWYgKhn': 0, 'P8vw6BuadZrqKEsoSsfP': 4, 'PIDnNGShw3UlvGnst2VI': 211, 'PYOdznWwjqtfhGUmUw5W': 124, 'Pe9I9QyTs4nbQyTjJrzc': 87, 'PrANARGCTPJ5PDtaEh0I': 172, 'Q1uWqH7MwBPXxcBApYgv': 97, 'Q6qlifLxb88jgm3N3P1n': 64, 'QL2Pj9Bz2rBkGxAriGni': 99, 'QP7Y8pm9xiJfMxymWTGc': 143, 'QPqj8HRJaKH7IxWCccho': 29, 'QXb08OOxpADaMj7Xb7uV': 167, 'Qo58fb85M23qr3xrJXpx': 64, 'REMtH6wUkFLIivmlGdF2': 27, 'RtY9gpCjlllu8bmmh85H': 210, 'Rtl3qvMWMvPIZv8D8UcQ': 21, 'S6fWiD5yjreK3xw0h5kf': 97, 'SCJ2kuYzFhzQtEiTzAJ8': 0, 'SUlQ0XyDJAj3b5yjIQi8': 253, 'T2h1RxfnUwWrGVKmuFla': 79, 'TMWgtEf4S5lp14mC1BbM': 233, 'Th91HEEhtWhC4ylJnPMt': 101, 'TuLi2e3paFDt1KrFy8EB': 127, 'TueHEDGFxt9KCdJXA3PB': 121, 'UlFpSbz5Rv7uoUmC4l0V': 166, 'UqU9m4BXeBw4bOYkp8br': 233, 'VIv5j5ZtU0iOgUEemmps': 217, 'VPtE5Eb2sGJmnwT0LW4M': 31, 'VTFxMIrze1deRrZGDGKj': 87, 'VraUo9eCGiAmCTdnz9eC': 154, 'Vt3EtMPhsUbmBqgcuXlY': 233, 'Wbjht0arLPqeQ8ktEX0L': 173, 'WtSMNXfN9tx8B3f2D7bp': 103, 'WvOcrfWgVhJpAJiyrlHj': 96, 'XJ1ZF9XrTJsIGjgQ3LO1': 195, 'XML66pyn1S5APUwxJydi': 23, 'XORDAt6vljYsR31xowvj': 203, 'XaaJ0RSTMA5gDbWK29Sp': 3, 'Xc8tfUJj2VYSuDGY905Y': 249, 'YILsF8Qxxr8UlKkwLzKt': 33, 'YlMRUaBYi1ZZJ0Kg8Pjj': 97, 'ZM7CwG22glJLuVKpK0Ur': 85, 'ZPSZNsOyHFHCise636vu': 250, 'ZPhSU58HYfff2cCFqyJ5': 233, 'ZmtqC29ZCqhDYQCpHaIG': 6, 'ZpV5O1EbJhVEWXW9rMvr': 186, 'ZqjWKfL0feEaAfWQyqiG': 224, 'aBid5pRnNo7Jv68Di2OZ': 62, 'aETz6JkF5PdrZaAN0Htw': 35, 'aPEICXX6LBgjZDieNTJd': 84, 'afyeqT9XaCz6iSCrqNb5': 112, 'aqHZLmhcXhYInfnGqNWu': 206, 'au71Fozydjb6XxEzbT1D': 241, 'b7q1mnJYeAkMm0eeyIEa': 53, 'bMMGWXnSb7b80bCecKwm': 131, 'bqrUXvmfmOps40bO97xH': 164, 'c6vri8OZpxYDvktmyDXZ': 112, 'c92FHnjhUWSvscCkbFG8': 117, 'cPCN9jRRePOJww4ZxO08': 181, 'cbWF3ko52Xf2KuN9RxsT': 65, 'cfjDdlCpsupcq0eCl4z0': 238, 'ciobv0ZWgzMlvxBNMmLv': 230, 'csuWox5RtI11d73TBbbF': 212, 'ctQ2N2txxCQbrTU1Tmwn': 221, 'd2QnTaOwVGXDcM4AYvQI': 158, 'd3HHbWnbkCvll1lURxTF': 157, 'drtLwtVkV8q1njADEBm1': 22, 'e3jNfF4eaVCM1RZRDcWQ': 105, 'eIkiUFkJgSPBoF4kXkvV': 84, 'eKScaWF2H96SAdPk774y': 19, 'eURPmpf42Pee8rxGCj89': 0, 'egl7lBFHIGfJttPEiEPh': 21, 'eibn4Ho4E2JTgjYqEMTQ': 212, 'fJGaHD2t22KZjU9hab0o': 76, 'fSlqfnLbecubkrOpAw8Q': 120, 'fWOw3kQSeopsQnpnnkWL': 255, 'fWZZgVAVj2Ho1qCiL7E0': 203, 'fZJJYjQrCV9e2uneeR2Q': 0, 'fhqLSC5WHn8oA7aVDxLd': 202, 'fqrKl4j5SAnFqwt71BVj': 75, 'gTOo7rTfzpIkxLeXfU94': 0, 'gUqbUnjFxhsuCABDO7cM': 30, 'gaJ4IiCvWxEPeKm0oVXC': 107, 'gniIpn1OZaGgcB2TrKFh': 158, 'grYwTA7fnZatSR3qcezS': 249, 'gvpnUzp1qVdmJO8KH6do': 30, 'gwk7FImD0Yl0ZdZ0dBWc': 106, 'gzgBaIfgmDWE1knCxKe4': 166, 'h1nYxCo2xom42gkiP0lu': 182, 'hLoV2OXPw60SFHF51vYE': 197, 'hNYuhTB3g6bosNUe1pHn': 155, 'hUarPqf7f0DppiuYa0co': 112, 'hyQdy1k8Z4igoyxi5N2F': 65, 'i5entoHTdTjC1HucVYcH': 3, 'iArUCOD1ylnGEgrKVDKV': 60, 'iE0kLc88vWpz1qzOiSS6': 191, 'iH1SFIA8nAtF8lEWDCey': 0, 'iIMd28uY1pMa3pBQPeLV': 108, 'iZZ5mjvP7VfLorGOlT0s': 24, 'idHHih1nFoOhKEIBUxRt': 150, 'izx2TS5ZXjKgLHdwQbj6': 75, 'jJhod5DBG7OfzLgECReE': 86, 'jXCfREtMUnWNyY5xuosp': 12, 'jermjTpker76OG3Kx65z': 97, 'jwqvKdPTL0XLY4mkMWAm': 207, 'k4nE5C4mRwcs1RJwWRUq': 21, 'kO4NiuQW6rXZveDq6VKo': 117, 'kYRKgzuoFKz5P86rwIeM': 63, 'klOBnZR1eFWtgOFOWDej': 87, 'kwDVOdlG6QCimBQWwyMJ': 112, 'l2oQm4OHla9CUI50pmlT': 0, 'l7qOkd06IC05yhPikcWZ': 235, 'lVAB77j4Bgp24Cgt0d7v': 233, 'lZ2Q9Ys6R3ynP3gfBJ9w': 27, 'm7SiNgH6hCUIaEJci335': 48, 'mLEqdYsJFfrXdHO8cC0S': 8, 'mXgKwyKmqcEQEpjhmHXp': 172, 'mZ6frccstmQ3tGqWOHmk': 97, 'md94sqyYwsm8ppbJKR6q': 117, 'mdSIRXm1x8OJJScmIn9q': 117, 'n3ly9JsfRx5PGOarpPhm': 124, 'n7S3yErH9GcHl7APSbx0': 120, 'nArXNaO53DQhMv3GSG3o': 160, 'nIasxVk4T68JkATgbtyl': 253, 'navcdCleGl4qsbRNuzZN': 3, 'nb9q0v4fmG2sKz7FJ3Sz': 91, 'nfcPkLPoTY2I8zEfeeoT': 22, 'nqqSELEP1y5kHPuG9393': 166, 'ntIXLWFaQVj1lqQwWOqe': 88, 'nzQIc2THYhLiINzEtRBb': 163, 'o5IW4Frmu8XFu80Fvv0n': 158, 'o6yYmyNsID29l7jJMqMU': 106, 'op9g21jep0DW5YsZhF6M': 112, 'ovtxvy6xXX97szRH7IMO': 2, 'p7opgZyOqn8cGPadKEZU': 28, 'p8mwFBAKYHe9pRLMyJgq': 228, 'pKqfUtgCv3D5USZFNgbU': 223, 'pPPJZQ6ZTjrYuSZDKxsP': 49, 'pWzainbPBkgA8Nag2GAI': 158, 'pbPc0b4Uf1TxjwtQHsSN': 188, 'pcMrbPzBFu8iNwZ2wint': 29, 'pdJpM3kpwNQbl8h26Q0Z': 243, 'pnaLQnPbIABhaQMNahMT': 63, 'prxBVPSzSpQGu7NLVAfF': 0, 'q192hC5vy3z4tukH1L2C': 158, 'q8oiO4OsVhPBYS2iikkA': 141, 'qGDz5Bsdc9wc1QAWKY2r': 94, 'qHbwde7rHDEjkm4ybb9M': 18, 'qIY6tpyFXTuT0zSWGNwB': 158, 'qKbLm39SqgbGAjwBjttp': 237, 'qZ5ou08lPalMTUCWT3Nn': 94, 'qmJEdNYSYaToARHVyiCb': 154, 'qtYNDsUkH0lxyLfAcmL7': 69, 'rAIWlYAyjI4g92dQKKAK': 97, 'rLQ1kttoG0nREKPizFKH': 136, 'rbC5Eo75UEZjjtKcD9JA': 16, 'ro3Jhn52pK8A7x02mJip': 214, 's663AjJ38d9YEWvrn3Kn': 57, 'sDYgGR0WT3maMom712HB': 126, 'sG3D9cMKoayIHId8Ib2h': 183, 'sHWLu91MB3QPcBYlpH7f': 112, 'sP1QXKT46E48RyIsY4kM': 106, 'tHInHJ6VnoBY2PKd5WDR': 22, 'tIlqtLp4CxG3UIYaIuYP': 47, 'tIvwvtUntMoOFmZNfUom': 148, 'tdnIlo7ZsStHVTMdFTTa': 181, 'tlw9yqs4QFX6LRNmyu9g': 166, 'tnk7nDFUqKpaQ3tcPSR0': 87, 'uWwXp6L82A3Zc0Q1nqnP': 125, 'uhbaT0mLyYgF17zxwPxN': 177, 'uuD9ZsZeYPXZu08gSa1u': 176, 'uvFkoIK2wGRaegpbZr97': 226, 'uz99VNhk2WdvF6vPicwy': 60, 'uzpc9XtPlAy27FHGShY0': 182, 'vMB61leym52C97xv2SfU': 27, 'vSuUtJs3VxpYt12UxUGL': 0, 'vU6qRuGBaSh4AuYOLAko': 243, 'vb8qYkkdJMjxs2ImI5ZO': 247, 'veZPvA20PexrpUHDPiKb': 40, 'vuCbFEiS0SbnhXwVGTQg': 164, 'vzazHtvIaPVWab976yps': 77, 'w61UzuH7I0xV5l2vVzZK': 233, 'w8FVsQszJYRHDkgEQgNR': 147, 'wQ9x3tdwKvPM9tGibz5r': 74, 'weBgVtZwsKWtmwCEPIVb': 87, 'wzPGHTJpqgQcC60zgyyK': 229, 'x5jF5TopBn1Ij4vW84q7': 234, 'x5qOPnQpyKY8NVprK8p1': 185, 'xHXtyMvHAvZ4WEKHNLM6': 111, 'xOygCIuLsMSVZh4geA39': 158, 'xSQbPSAlnbPy5z7gnWnl': 117, 'xX1j8Sl5IpzIiO7vvsrG': 22, 'xuzS80dcNyIZDWmfcmoT': 141, 'yHQj7qDWqnQVi61yqQzJ': 109, 'yRi08zQBH3NLvFcf19Bl': 75, 'ybOweO11ru3MHjlSTS3r': 63, 'ytnr9WDEcCsB53FXyUzp': 189, 'yueTiA1EIVOYEoTI5886': 174, 'z6zPZzzCgpVuCGAhOP6G': 164, 'z7ybNECH1yKh8QfllxzA': 0, 'zJ4WeDzkiakWwxi8wEqE': 83, 'zMJCmBjFQlLDupQPRGqa': 72, 'zSTDjQQL0uTH03DDvwwj': 131, 'zVxhJWFEsznmw8jRAMNL': 149, 'zaxo2ATNVsEagb6ABbug': 252, 'zexiPSfZ404mKfg5s52U': 60, 'zlGakvHqctqNDoW69or8': 145, 'zuERoymc9gRWByz6jcXs': 170}
# import requests
# import logging

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # First data dictionary (33 miner IDs)

# def get_miner_list_with_resources(data) -> dict:
#     logger.info(f"Fetching miner list with resources for {len(data)} miner IDs")
#     try:
#         response = requests.get("https://polaris-test-server.onrender.com/api/v1/miners")
#         response.raise_for_status()
#         miners_data = response.json()
#         results = {}
#         for miner in miners_data:
#             miner_id = miner["id"]
#             print(f"Processing miner ID: {miner_id}")  # Print miner ID being worked on
#             if miner_id in data:
#                 results[miner_id] = {
#                     "compute_resources": miner["compute_resources"],
#                     "miner_uid": data.get(miner_id)
#                 }
#         return results
#     except Exception as e:
#         logger.error(f"Error fetching miner list with resources: {e}")
#         return {}


# results = get_miner_list_with_resources(data)

# # Collect unmapped miner IDs in a list
# unmapped_miners = list(set(data.keys()) - set(results.keys()))

# # Print unmapped miner IDs
# print("\nMiner IDs whose resources are not found:", unmapped_miners)
# print("\nReason: These miner IDs are not present in the API response (miners_data) from https://polaris-test-server.onrender.com/api/v1/miners.")
# print(f"\n results found for {results.keys()}")
# if not results:
#     print("Note: The API request failed, so no miner resources were returned, making all IDs unmapped.")
# else:
#     print("Possible causes: The miner IDs may be invalid, not registered, or the API returned an incomplete miner list.")
# def get_unmapped_miners_from_results(data, results):
#     # Extract miner IDs from data and results
#     data_miner_ids = set(data.keys())
#     mapped_miner_ids = set(results.keys())
    
#     # Find miner IDs in data but not in results
#     unmapped_miners = data_miner_ids - mapped_miner_ids
    
#     return unmapped_miners

# # Run get_miner_list_with_resources
# results = get_miner_list_with_resources(data)

# # Get unmapped miner IDs
# unmapped_miners = get_unmapped_miners_from_results(data, results)

# # Print results
# print("Unmapped miner IDs (not returned by get_miner_list_with_resources):")
# if unmapped_miners:
#     for miner_id in sorted(unmapped_miners):
#         print(miner_id)
# else:
#     print("None (all miner IDs were found in the API response).")

# print("\nReason: These miner IDs are not present in the API response (miners_data) from https://polaris-test-server.onrender.com/api/v1/miners.")
# if not results:
#     print("Note: The API request failed, so no miner information was returned, making all IDs unmapped.")
# else:
#     print("Possible causes: The miner IDs may be invalid, not registered, or the API returned an incomplete miner list.")

# print("\nMapped miners (for reference):")
# if results:
#     for miner_id, info in sorted(results.items()):
#         print(f"{miner_id}: {info}")
# else:
#     print("None (no miners were mapped due to API failure or no matching IDs).")
# async def main():
#     miner_id = "0sy5sozr8YlBQGYU0OuV"
    # result = get_miner_list_with_resources(data)
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




import requests
from typing import List, Dict, Tuple
import logging

import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# Cache for hotkey-to-UID mapping
_hotkey_to_uid_cache: Dict[str, int] = {}
_last_metagraph_sync: float = 0
_metagraph_sync_interval: float = 300  # 5 minutes in seconds
_metagraph = None
_miner_details_cache: Dict[str, dict] = {}

# Cache for miners data from the common API endpoint
_miners_data_cache: Dict = {}
_miners_data_last_fetch: float = 0
_miners_data_cache_interval: float = 3600  # 1 hour in seconds

def _sync_miners_data() -> None:
    """Fetches and caches miners data from the common API endpoint."""
    global _miners_data_cache, _miners_data_last_fetch
    try:
        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "53c8f1eba578f46cd3361d243a62c2c46e2852f80acaf5ccc35eaf16304bc60b",
            "service-name": "miner_service"
        }
        url = "https://polaris-interface.onrender.com/api/v1/services/miner/miners"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        _miners_data_cache = response.json().get("data", {}).get("miners", [])
        _miners_data_last_fetch = time.time()
        logger.info(f"Cached miners data, total miners: {len(_miners_data_cache)}")
    except Exception as e:
        logger.error(f"Error caching miners data: {e}")
        _miners_data_cache = []
        _miners_data_last_fetch = time.time()

def _get_cached_miners_data() -> List[dict]:
    """Returns cached miners data, refreshing if necessary."""
    global _miners_data_last_fetch
    if time.time() - _miners_data_last_fetch > _miners_data_cache_interval or not _miners_data_cache:
        _sync_miners_data()
    return _miners_data_cache

def _sync_metagraph(netuid: int, network: str = "finney") -> None:
    """Syncs the metagraph and updates the hotkey-to-UID cache."""
    global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
    try:
        if time.time() - _last_metagraph_sync > _metagraph_sync_interval or _metagraph is None:
            subtensor = bt.subtensor(network=network)
            _metagraph = subtensor.metagraph(netuid=netuid)
            _hotkey_to_uid_cache = {hotkey: uid for uid, hotkey in enumerate(_metagraph.hotkeys)}
            _last_metagraph_sync = time.time()
            logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(_metagraph.hotkeys)}")
    except Exception as e:
        logger.error(f"Error syncing metagraph for netuid {netuid}: {e}")
        _hotkey_to_uid_cache = {}
        _metagraph = None

# def get_filtered_miners(allowed_uids: List[int]) -> Tuple[Dict[str, str], List[str]]:
#     try:
#         # Get cached miners data
#         miners = _get_cached_miners_data()

#         # Initialize outputs
#         filtered_miners = {}
#         miners_to_reject = []

#         for miner in miners:
#             print(miner)
#             miner_id = miner.get("id")
#             bittensor_reg = miner.get("bittensor_registration")

#             if not miner_id:
#                 continue 

#             if bittensor_reg is not None:
#                 miner_uid = bittensor_reg.get("miner_uid")
#                 if miner_uid is None:
#                     miners_to_reject.append(miner_id)
#                 elif int(miner_uid) in allowed_uids:
#                     filtered_miners[miner_id] = str(miner_uid)
#             else:
#                 miners_to_reject.append(miner_id)

#         return filtered_miners, miners_to_reject

#     except Exception as e:
#         logger.error(f"Error fetching filtered miners: {e}")
#         return {}, []


# # Example usage
# allowed_uids = [0,4,13,27,231, 88, 188, 183, 203]  # Example list of allowed UIDs
# filtered_miners = get_filtered_miners(allowed_uids)
def extract_miner_ids(data: List[dict]) -> List[str]:
    """
    Extract miner IDs from the 'unique_miners_ips' list in the data.
    
    Args:
        data: List of dictionaries from get_miners_compute_resources().
    
    Returns:
        List of miner IDs (strings).
    """
    miner_ids = []
    
    try:
        # Validate input
        if not isinstance(data, list) or not data:
            logger.error("Data is not a non-empty list")
            return miner_ids
        
        # Access unique_miners_ips from the first dict
        multiple_miners_ips = data[0].get("unique_miners_ips", [])
        if not isinstance(multiple_miners_ips, list):
            logger.error("unique_miners_ips is not a list")
            return miner_ids
        
        # Extract keys from each dict in unique_miners_ips
        for item in multiple_miners_ips:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict item: {item}")
                continue
            if len(item) != 1:
                logger.warning(f"Skipping dict with unexpected key count: {item}")
                continue
            miner_id = next(iter(item))  # Get the single key
            if isinstance(miner_id, str) and miner_id:
                miner_ids.append(miner_id)
            else:
                logger.warning(f"Skipping invalid miner ID: {miner_id}")
        
        logger.info(f"Extracted {len(miner_ids)} miner IDs")
        return miner_ids
    
    except Exception as e:
        logger.error(f"Error extracting miner IDs: {e}")
        return miner_ids

def get_miners_compute_resources() -> dict[str, list]:
    """
    Retrieves compute resources for all miners.

    Returns:
        dict[str, list]: A dictionary mapping miner IDs to their compute_resources_details list.
    """
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct dictionary of miner IDs to compute resource details
        return extract_miner_ids(miners)

    except Exception as e:
        logger.error(f"Error fetching miners compute resources: {e}")
        return {} 


def get_miner_details(miner_id: str) -> dict:
    """
    Retrieve miner details from _miners_data_cache by miner_id.

    Args:
        miner_id (str): The ID of the miner to look up.

    Returns:
        dict: The miner details if found in _miners_data_cache, otherwise an empty dict.
    """
    logger.info(f"Looking up miner {miner_id} in _miners_data_cache")
    
    # Get cached miners data
    miners_data = _get_cached_miners_data()
    
    # Search for the miner by ID
    for miner in miners_data:
        
        if miner.get("id") == miner_id:
            logger.info(f"Found miner {miner_id} in _miners_data_cache")
            return miner
    
    logger.warning(f"Miner {miner_id} not found in _miners_data_cache")
    return {}


def filter_miners_by_id(
    bittensor_miners: Dict[str, int],
    netuid: int = 49,
    network: str = "finney",
    hotkey_to_uid: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep, removing all others.
    
    Args:
        bittensor_miners: Dictionary mapping miner IDs to UIDs from get_filtered_miners.
        netuid: The subnet ID (default: 49).
        network: The Bittensor network to query (default: "finney").
        hotkey_to_uid: Optional cached mapping of hotkeys to UIDs (e.g., from PolarisNode).
    
    Returns:
        Dictionary mapping retained miner IDs to their UIDs.
    """
    try:
        # Validate inputs
        if not isinstance(bittensor_miners, dict):
            logger.error("bittensor_miners is not a dictionary")
            return {}
        # ids_to_keep = get_miners_compute_resources()
        
        ids_to_keep = list(bittensor_miners.keys())
        # Convert ids_to_keep to a set for O(1) lookup
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Use provided hotkey_to_uid cache or sync metagraph
        uid_cache = hotkey_to_uid if hotkey_to_uid is not None else _hotkey_to_uid_cache
        if hotkey_to_uid is None:
            _sync_metagraph(netuid, network)

        # Filter miners and verify hotkey-UID match
        for miner_id, uid in bittensor_miners.items():
            if miner_id not in ids_to_keep_set:
                logger.debug(f"Miner {miner_id} not in ids_to_keep, skipping")
                continue

            # Get miner details
            miner_details = get_miner_details(miner_id)
            hotkey = miner_details.get("bittensor_registration", {}).get("hotkey")
            if not hotkey or hotkey == "default":
                logger.warning(f"Invalid or missing hotkey for miner {miner_id}, skipping")
                continue

            # Verify UID using cached mapping
            subnet_uid = uid_cache.get(hotkey)
            if subnet_uid is None:
                _sync_metagraph(netuid, network)
                subnet_uid = _hotkey_to_uid_cache.get(hotkey)
                if subnet_uid is None:
                    logger.warning(f"Hotkey {hotkey} still not found after sync, skipping")
                    continue
            if subnet_uid != uid:
                logger.warning(f"UID mismatch for miner {miner_id}: metagraph UID {subnet_uid}, reported UID {uid}")
                continue

            filtered_miners[miner_id] = uid

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
# info = filter_miners_by_id(data, netuid=49, network="finney")


def get_miner_list_with_resources(miner_commune_map: Dict[str, str]) -> Dict[str, dict]:
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct and return the desired output
        return {
            miner.get("id"): {
                "compute_resource_details": miner.get("compute_resources_details", []),
                "miner_uid": miner_commune_map.get(miner.get("id"))
            }
            for miner in miners
            if miner.get("status") == "verified" and miner.get("id") in miner_commune_map
        }

    except Exception as e:
        logger.error(f"Error fetching miner list with resources: {e}")
        return {}
info = get_miner_list_with_resources(data)
print(f"new data {info}")
# print("Miners to Reject:", miners_to_reject)
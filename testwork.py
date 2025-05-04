# import paramiko
# import os

# def connect_to_remote_machine(host, port=22, username="user"):
#     # Initialize SSH client
#     client = paramiko.SSHClient()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
#     # Path to your private key
#     key_path = os.path.join(os.path.dirname(_file_), "ssh_host_key")
    
#     try:
#         # Connect using the private key
#         client.connect(
#             hostname=host,
#             port=port,
#             username=username,
#             key_filename=key_path,
#             timeout=5
#         )
        
#         print(f"Successfully connected to {username}@{host}:{port}")
        
#         # Execute a command
#         stdin, stdout, stderr = client.exec_command("hostname")
#         print(f"Remote hostname: {stdout.read().decode().strip()}")
        
#         # Close the connection
#         client.close()
#         return True
        
#     except Exception as e:
#         print(f"Failed to connect: {str(e)}")
#         return False

# # Example usage
# connect_to_remote_machine("192.168.1.100", username="admin")


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


# from neurons.utils.pogs import execute_ssh_tasks, compare_compute_resources, compute_resource_score
def get_unverified_miners() -> dict[str, dict]:
    try:
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
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
unverified_miners=get_unverified_miners()
# miner="OcaIXLgNDnwAIiDETFiM"
# miner_resources = unverified_miners.get(miner)
# print(f"miner resources {miner_resources[0]}")


# def execute_ssh_tasks(miner_id: str) -> Dict[str, Any]:
#     """
#     Execute SSH tasks for a given miner ID by calling the orchestrator API.
    
#     Args:
#         miner_id (str): The ID of the miner to execute tasks for.
    
#     Returns:
#         Dict[str, Any]: A dictionary containing:
#             - status: "success" or "error"
#             - message: Descriptive message about the outcome
#             - task_results: Dictionary of task results or empty dict if failed
#     """
#     logger.info(f"Executing SSH tasks for miner {miner_id}")
    
#     # Validate miner_id
#     if not isinstance(miner_id, str) or not miner_id.strip():
#         logger.error("Invalid miner_id: must be a non-empty string")
#         return {
#             "status": "error",
#             "message": "Invalid miner_id: must be a non-empty string",
#             "task_results": {}
#         }
    
#     url = url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/perform-tasks"
#     logger.debug(f"Requesting SSH tasks at: {url}")
    
#     try:
#         response = requests.get(url, timeout=10)
#         logger.info(f"Response status: {response.status_code}")
        
#         if response.status_code == 200:
#             try:
#                 result = response.json()
#                 logger.debug(f"Server response: {result}")
                
#                 if result.get("status") != "success":
#                     logger.error(f"Server error: {result.get('message', 'Unknown error')}")
#                     return {
#                         "status": "error",
#                         "message": result.get("message", "Server reported failure"),
#                         "task_results": {}
#                     }
                
#                 # Extract task_results (adjust key based on actual server response)
#                 task_results = result.get("task_results", result.get("specifications", {}))
#                 logger.info("SSH tasks executed successfully")
#                 return {
#                     "status": "success",
#                     "message": "SSH tasks executed successfully",
#                     "task_results": task_results
#                 }
#             except ValueError as e:
#                 logger.error(f"Failed to parse JSON response: {str(e)}")
#                 return {
#                     "status": "error",
#                     "message": f"Invalid server response: {str(e)}",
#                     "task_results": {}
#                 }
#         else:
#             logger.error(f"Unexpected status code: {response.status_code}")
#             return {
#                 "status": "error",
#                 "message": f"Server returned status code {response.status_code}",
#                 "task_results": {}
#             }
            
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Request failed for {url}: {str(e)}")
#         return {
#             "status": "error",
#             "message": f"Request error: {str(e)}",
#             "task_results": {}
#         }
#     except Exception as e:
#         logger.error(f"Unexpected error executing SSH tasks: {str(e)}")
#         return {
#             "status": "error",
#             "message": f"Unexpected error: {str(e)}",
#             "task_results": {}
#         }



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
# update_rejected_miners_to_pending()

# def get_filtered_miners() -> tuple[Dict[str, str], List[str]]:
#     try:
#         response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
#         response.raise_for_status()
#         miners_data = response.json()
        
#         # Initialize outputs
#         miners_to_reject = []
        
#         # Process each miner
#         for miner in miners_data:
#             miner_id = miner.get("miner_id")
#             miner_uid = miner.get("miner_uid")
#             print(f"miner uid {miner_id} and {miner_uid}")
#             if miner_uid is None:
#                 miners_to_reject.append(miner_id)
        
#         return miners_to_reject
    
#     except Exception as e:
#         logger.error(f"Error fetching filtered miners: {e}")
#         return {}, []
# allowed_uids=[2,0,13,131,207]
# def get_filtered_miners(allowed_uids: List[int]) -> tuple[Dict[str, str], List[str]]:
#     try:
#         response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/bittensor/miners")
#         response.raise_for_status()
#         miners_data = response.json()
        
#         # Initialize outputs
#         filtered_miners = {}
#         miners_to_reject = []
        
#         # Process each miner
#         for miner in miners_data:
#             miner_id = miner.get("miner_id")
#             miner_uid = miner.get("miner_uid")
#             if miner_uid is None:
#                 miners_to_reject.append(miner_id)
#             elif int(miner_uid) in allowed_uids:
#                 # Include miners with valid miner_uid in allowed_uids
#                 filtered_miners[miner_id] = str(miner_uid)
        
#         return filtered_miners, miners_to_reject
    
#     except Exception as e:
#         logger.error(f"Error fetching filtered miners: {e}")
#         return {}, []
    
# filtered,miners_to_reject =get_filtered_miners(allowed_uids)
# print(miners_to_reject)
# print(filtered)
def get_rejected_miners() -> list[str]:
    try:
        # Get current date dynamically and calculate 2 days ago
        today = datetime.now()
        two_days_ago = today - timedelta(days=2)
        
        # Fetch data from API
        response = requests.get("https://orchestrator-gekh.onrender.com/api/v1/miners")
        response.raise_for_status()
        miners_data = response.json()
        
        # Filter miners with status "rejected" and created 2 days ago
        rejected_miners = [
            miner["id"]
            for miner in miners_data
            if miner.get("status") == "pending_verification"
            and miner.get("created_at")  # Ensure created_at exists
            and datetime.fromisoformat(miner["created_at"].replace("Z", "+00:00")).date() <= two_days_ago.date()
        ]
        
        return rejected_miners
    
    except Exception as e:
        print(f"No data found: {e}")
        return []
    


def delete_miner(miner_id: str) -> bool:
    url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}"
    try:
        response = requests.delete(url)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deleting miner {miner_id}: {e}")
        return False
    

def delete_rejected_miners():
    # Get the list of rejected miners created 2 days ago
    miner_ids = get_rejected_miners()
    
    # Format the date 2 days ago for output
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    if not miner_ids:
        print(f"No rejected miners created on {two_days_ago} found.")
        return
    
    print(f"Found {len(miner_ids)} rejected miners created on {two_days_ago}: {miner_ids}")
    
    # Delete each miner
    for miner_id in miner_ids:
        print(f"Deleting miner {miner_id}...")
        if delete_miner(miner_id):
            print(f"Successfully deleted miner {miner_id}")
        else:
            print(f"Failed to delete miner {miner_id}")
    
if __name__ == "__main__":
    delete_rejected_miners()

# 
# logger = logging.getLogger("remote_access")

# SERVER_URL = "https://orchestrator-gekh.onrender.com"
# API_PREFIX = "/api/v1"

# def execute_ssh_tasks(miner_id):
#     logger.info(f"Trying for miner {miner_id}")
#     try:
#         url = f"{SERVER_URL}{API_PREFIX}/miners/{miner_id}/perform-tasks"
#         logger.info(f"Trying to execute SSH tasks at: {url}")
        
#         try:
#             response = requests.get(url)
#             logger.info(f"Response status: {response.status_code}")
            
#             if response.status_code == 200:
#                 result = response.json()
#                 logger.info(f"Server response: {result.get('message')}")
                
#                 if result.get("status") != "success":
#                     logger.error(f"Error from server: {result.get('message')}")
#                     return {
#                         "status": "error",
#                         "message": result.get('message')
#                     }
                    
#                 return {
#                     "status": "success",
#                     "message": "SSH tasks executed successfully",
#                     "task_results": result.get("task_results", {})
#                 }
#         except requests.exceptions.RequestException as e:
#             logger.error(f"Error with endpoint {url}: {str(e)}")
        
#         logger.error("Failed to execute SSH tasks")
#         return {
#             "status": "error",
#             "message": "Failed to execute SSH tasks"
#         }
        
#     except Exception as e:
#         logger.error(f"Error executing SSH tasks: {str(e)}")
#         return {
#             "status": "error",
#             "message": f"Error: {str(e)}"
#         }

# def normalize_memory_value(value: str) -> float:
#     """Convert memory value to GB, handling various formats including GiB."""
#     try:
#         if not value or not isinstance(value, str):
#             return 0.0
#         value = value.strip().upper()
#         match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|MB|TB|KB)?", value, re.IGNORECASE)
#         if not match:
#             return 0.0
#         num, unit = float(match.group(1)), match.group(2) or "GB"
#         if unit in ["GIB", "GI"]:
#             return num * 1.07374  # Convert GiB to GB
#         elif unit == "MB":
#             return num / 1024
#         elif unit == "TB":
#             return num * 1024
#         elif unit == "KB":
#             return num / (1024 * 1024)
#         return num
#     except (ValueError, TypeError) as e:
#         logger.error(f"Error normalizing memory value '{value}': {e}")
#         return 0.0

# def normalize_storage_capacity(value: str) -> float:
#     """Convert storage capacity to GB, handling various formats including GiB."""
#     try:
#         if not value or not isinstance(value, str):
#             return 0.0
#         value = value.strip().upper()
#         match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|TB|MB)?", value, re.IGNORECASE)
#         if not match:
#             return 0.0
#         num, unit = float(match.group(1)), match.group(2) or "GB"
#         if unit in ["GIB", "GI"]:
#             return num * 1.07374  # Convert GiB to GB
#         elif unit == "MB":
#             return num / 1024
#         elif unit == "TB":
#             return num * 1024
#         return num
#     except (ValueError, TypeError) as e:
#         logger.error(f"Error normalizing storage capacity '{value}': {e}")
#         return 0.0

# def normalize_speed(value: str) -> float:
#     """Convert speed (e.g., read_speed, write_speed) to MB/s."""
#     try:
#         if not value or not isinstance(value, str):
#             return 0.0
#         value = value.strip().upper()
#         match = re.match(r"(\d*\.?\d+)\s*(MB/S|GB/S|KB/S)?", value, re.IGNORECASE)
#         if not match:
#             return 0.0
#         num, unit = float(match.group(1)), match.group(2) or "MB/S"
#         if unit == "GB/S":
#             return num * 1000
#         elif unit == "KB/S":
#             return num / 1000
#         return num
#     except (ValueError, TypeError) as e:
#         logger.error(f"Error normalizing speed '{value}': {e}")
#         return 0.0

# def parse_memory_usage(memory_usage: str) -> float:
#     """Parse 'free' command output to get total memory in GB."""
#     try:
#         if not memory_usage or not isinstance(memory_usage, str):
#             return 0.0
#         lines = memory_usage.split("\n")
#         for line in lines:
#             if line.startswith("Mem:"):
#                 total_mb = float(line.split()[1])  # Total memory in MB
#                 return total_mb / 1024  # Convert to GB
#         return 0.0
#     except (IndexError, ValueError) as e:
#         logger.error(f"Error parsing memory usage: {e}")
#         return 0.0

# def parse_disk_space(disk_space: str) -> float:
#     """Parse 'df' command output to get root partition size in GB."""
#     try:
#         if not disk_space or not isinstance(disk_space, str):
#             return 0.0
#         lines = disk_space.split("\n")
#         for line in lines:
#             if " / " in line:  # Root partition
#                 size_gb = float(line.split()[1])  # Size in GB (df -h)
#                 return size_gb
#         return 0.0
#     except (IndexError, ValueError) as e:
#         logger.error(f"Error parsing disk space: {e}")
#         return 0.0

# def parse_cpu_info(cpu_info: str) -> Dict[str, Any]:
#     """Parse 'lscpu' output to extract CPU details."""
#     try:
#         if not cpu_info or not isinstance(cpu_info, str):
#             return {}
#         cpu_specs = {}
#         for line in cpu_info.split("\n"):
#             if ":" in line:
#                 key, value = [part.strip() for part in line.split(":", 1)]
#                 if key in ["Architecture", "Model name", "CPU(s)", "Vendor ID"]:
#                     cpu_specs[key.lower().replace(" ", "_")] = value
#         return cpu_specs
#     except Exception as e:
#         logger.error(f"Error parsing CPU info: {e}")
#         return {}

# def parse_gpu_info(gpu_info: str) -> Dict[str, Any]:
#     """Parse 'nvidia-smi' output to extract GPU details."""
#     try:
#         if not gpu_info or not isinstance(gpu_info, str):
#             return {}
#         gpu_specs = {}
#         lines = gpu_info.split("\n")
#         for line in lines:
#             if "NVIDIA" in line and "MiB" in line:  # Typical nvidia-smi output
#                 parts = line.split()
#                 gpu_specs["gpu_name"] = parts[2] if len(parts) > 2 else "Unknown"
#                 memory = next((p for p in parts if "MiB" in p), "0MiB")
#                 gpu_specs["memory_size"] = str(float(memory.replace("MiB", "")) / 1024) + "GB"
#                 gpu_specs["total_gpus"] = 1  # Simplified assumption
#                 break
#         return gpu_specs
#     except Exception as e:
#         logger.error(f"Error parsing GPU info: {e}")
#         return {}

# def get_gpu_specs(resource: Dict[str, Any]) -> Dict[str, Any]:
#     """Extract GPU specs, checking SSH outputs if standard field is absent."""
#     gpu_specs = resource.get("gpu_specs", {}) or {}
#     if not gpu_specs and resource.get("nvidia_smi"):
#         gpu_specs = parse_gpu_info(resource.get("nvidia_smi", ""))
#     if isinstance(gpu_specs, list) and len(gpu_specs) > 0:
#         gpu_specs = gpu_specs[0]  # Take first GPU if multiple
#     return gpu_specs if isinstance(gpu_specs, dict) else {}

# def get_gpu_memory(gpu_specs: Dict[str, Any]) -> str:
#     """Extract GPU memory size, returning '0' if none."""
#     return gpu_specs.get("memory_size", "0") or gpu_specs.get("memory_total", "0") or "0"

# def extract_features(resource: Dict[str, Any]) -> Dict[str, Any]:
#     """Extract and normalize features from a resource for vectorization."""
#     features = defaultdict(float)
#     categorical = {}

#     # Resource Type
#     categorical["resource_type"] = resource.get("resource_type", "").lower()

#     # RAM
#     ram = normalize_memory_value(resource.get("ram", "0"))
#     features["ram"] = ram / 128  # Normalize to max 128GB

#     # Storage
#     storage = resource.get("storage", {})
#     features["storage_capacity"] = normalize_storage_capacity(storage.get("capacity", "0")) / 4000  # Max 4TB
#     categorical["storage_type"] = storage.get("type", "").lower()
#     features["storage_read_speed"] = normalize_speed(storage.get("read_speed", "0")) / 10000  # Max 10GB/s
#     features["storage_write_speed"] = normalize_speed(storage.get("write_speed", "0")) / 10000

#     # CPU Specs
#     cpu_specs = resource.get("cpu_specs", {})
#     features["cpu_total_cpus"] = cpu_specs.get("total_cpus", 0) / 64  # Max 64 cores
#     features["cpu_threads_per_core"] = cpu_specs.get("threads_per_core", 0) / 4  # Max 4 threads
#     features["cpu_cores_per_socket"] = cpu_specs.get("cores_per_socket", 0) / 32  # Max 32 cores/socket
#     features["cpu_sockets"] = cpu_specs.get("sockets", 0) / 4  # Max 4 sockets
#     categorical["cpu_name"] = cpu_specs.get("cpu_name", "").lower()
#     categorical["cpu_vendor_id"] = cpu_specs.get("vendor_id", "").lower()
#     features["cpu_max_mhz"] = cpu_specs.get("cpu_max_mhz", 0) / 5000  # Max 5GHz

#     # GPU Specs
#     gpu_specs = get_gpu_specs(resource)
#     categorical["gpu_name"] = gpu_specs.get("gpu_name", "").lower()
#     features["gpu_memory"] = normalize_memory_value(get_gpu_memory(gpu_specs)) / 48  # Max 48GB
#     features["gpu_total_gpus"] = gpu_specs.get("total_gpus", 0) / 8  # Max 8 GPUs

#     # Is Active
#     features["is_active"] = 1.0 if resource.get("is_active", False) else 0.0

#     return features, categorical

# @tenacity.retry(
#     stop=tenacity.stop_after_attempt(3),
#     wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
#     reraise=True
# )
# def compare_compute_resources(new_resource: Dict[str, Any], existing_resource: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Compare new and existing resources as a whole using a similarity matrix.
    
#     Args:
#         new_resource: Retrieved resources (e.g., from execute_ssh_tasks).
#         existing_resource: Expected resources (e.g., from miner_resources).
    
#     Returns:
#         Dict with 'percentage' key indicating similarity and optional 'errors' key.
#     """
#     logger.info("Starting comparison of compute resources")
#     logger.debug(f"New resource: {new_resource}")
#     logger.debug(f"Existing resource: {existing_resource}")

#     # Validate inputs
#     if not isinstance(new_resource, dict) or not isinstance(existing_resource, dict):
#         logger.error(f"Invalid resource types: new={type(new_resource)}, existing={type(existing_resource)}")
#         return {"percentage": 0.0, "errors": ["Invalid input types"]}

#     errors = []

#     # Extract features
#     try:
#         new_features, new_categorical = extract_features(new_resource)
#         existing_features, existing_categorical = extract_features(existing_resource)
#     except Exception as e:
#         errors.append(f"Feature extraction failed: {str(e)}")
#         logger.error(f"Error extracting features: {e}")
#         return {"percentage": 0.0, "errors": errors}

#     # Define similarity matrices for categorical attributes
#     resource_type_similarity = {
#         ("cpu", "cpu"): 1.0,
#         ("gpu", "gpu"): 1.0,
#         ("cpu", "gpu"): 0.2,
#         ("gpu", "cpu"): 0.2,
#         ("", ""): 1.0
#     }
#     storage_type_similarity = {
#         ("ssd", "ssd"): 1.0,
#         ("ssd", "disk"): 0.8,
#         ("disk", "ssd"): 0.8,
#         ("disk", "disk"): 1.0,
#         ("nvme", "ssd"): 0.9,
#         ("ssd", "nvme"): 0.9,
#         ("nvme", "nvme"): 1.0,
#         ("hdd", "hdd"): 1.0,
#         ("hdd", "ssd"): 0.7,
#         ("ssd", "hdd"): 0.7,
#         ("", ""): 1.0
#     }
#     cpu_name_similarity = {
#         ("amd epyc 7b12", "amd epyc 7b12"): 1.0,
#         ("amd epyc 7b12", "amd epyc 7b13"): 0.95,
#         ("intel xeon", "intel xeon"): 0.9,
#         ("", ""): 1.0
#     }
#     cpu_vendor_similarity = {
#         ("authenticamd", "authenticamd"): 1.0,
#         ("genuineintel", "genuineintel"): 1.0,
#         ("authenticamd", "genuineintel"): 0.5,
#         ("genuineintel", "authenticamd"): 0.5,
#         ("", ""): 1.0
#     }
#     gpu_name_similarity = {
#         ("", ""): 1.0,
#         ("nvidia rtx 3080", "nvidia rtx 3080"): 1.0,
#         ("nvidia rtx 3080", "nvidia rtx 3090"): 0.95,
#         ("nvidia", "nvidia"): 0.8,
#         ("amd radeon", "amd radeon"): 0.8
#     }

#     # Compute categorical similarities
#     categorical_scores = {}
#     try:
#         categorical_scores["resource_type"] = resource_type_similarity.get(
#             (new_categorical["resource_type"], existing_categorical["resource_type"]), 0.0)
#         categorical_scores["storage_type"] = storage_type_similarity.get(
#             (new_categorical["storage_type"], existing_categorical["storage_type"]), 0.0)
#         categorical_scores["cpu_name"] = cpu_name_similarity.get(
#             (new_categorical["cpu_name"], existing_categorical["cpu_name"]),
#             1.0 if new_categorical["cpu_name"] == existing_categorical["cpu_name"] else 0.0)
#         categorical_scores["cpu_vendor_id"] = cpu_vendor_similarity.get(
#             (new_categorical["cpu_vendor_id"], existing_categorical["cpu_vendor_id"]), 0.0)
#         categorical_scores["gpu_name"] = gpu_name_similarity.get(
#             (new_categorical["gpu_name"], existing_categorical["gpu_name"]),
#             1.0 if new_categorical["gpu_name"] == existing_categorical["gpu_name"] else 0.0)
#     except Exception as e:
#         errors.append(f"Categorical similarity computation failed: {str(e)}")
#         logger.error(f"Error computing categorical similarities: {e}")

#     # Feature weights
#     feature_weights = {
#         "ram": 0.15,
#         "storage_capacity": 0.15,
#         "storage_read_speed": 0.05,
#         "storage_write_speed": 0.05,
#         "cpu_total_cpus": 0.15,
#         "cpu_threads_per_core": 0.1,
#         "cpu_cores_per_socket": 0.05,
#         "cpu_sockets": 0.05,
#         "cpu_max_mhz": 0.05,
#         "gpu_memory": 0.05,
#         "gpu_total_gpus": 0.05,
#         "is_active": 0.05
#     }
#     categorical_weights = {
#         "resource_type": 0.1,
#         "storage_type": 0.1,
#         "cpu_name": 0.05,
#         "cpu_vendor_id": 0.05,
#         "gpu_name": 0.05
#     }

#     # Create feature vectors
#     try:
#         numerical_features = list(feature_weights.keys())
#         new_vector = np.array([new_features.get(f, 0.0) for f in numerical_features])
#         existing_vector = np.array([existing_features.get(f, 0.0) for f in numerical_features])
#         numerical_weights = np.array([feature_weights.get(f, 0.0) for f in numerical_features])

#         # Compute weighted cosine similarity for numerical features
#         if np.any(new_vector) or np.any(existing_vector):
#             weighted_new = new_vector * numerical_weights
#             weighted_existing = existing_vector * numerical_weights
#             cosine_sim = np.dot(weighted_new, weighted_existing) / (
#                 np.linalg.norm(weighted_new) * np.linalg.norm(weighted_existing) + 1e-10)
#             numerical_score = max(0.0, min(1.0, cosine_sim))
#         else:
#             numerical_score = 1.0  # Both empty
#         numerical_weight = sum(feature_weights.values())

#         # Combine with categorical scores
#         categorical_score = sum(score * categorical_weights[cat] for cat, score in categorical_scores.items())
#         categorical_weight = sum(categorical_weights.values())
        
#         # Total score
#         total_weight = numerical_weight + categorical_weight
#         if total_weight > 0:
#             score = (numerical_score * numerical_weight + categorical_score) / total_weight
#         else:
#             score = 0.0

#         percentage = score * 100
#         logger.debug(f"Numerical score: {numerical_score:.2f}, Categorical score: {categorical_score:.2f}, Total percentage: {percentage:.2f}%")
#     except Exception as e:
#         errors.append(f"Similarity computation failed: {str(e)}")
#         logger.error(f"Error computing similarity: {e}")
#         return {"percentage": 0.0, "errors": errors}

#     result = {"percentage": percentage}
#     if errors:
#         result["errors"] = errors
#     logger.info(f"Comparison complete: percentage={percentage:.2f}%")
#     return result


# result = execute_ssh_tasks(miner)
# if not result or "task_results" not in result:
#     print("go data")


# specs = result.get("task_results", {})
# pog_score = compare_compute_resources(specs, miner_resources[0])
# print(f"scores {pog_score}")
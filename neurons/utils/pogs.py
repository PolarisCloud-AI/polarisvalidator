import json
import re
import logging
from datetime import datetime
import requests
import tenacity
from typing import Dict, Any,List, Union
from loguru import logger
import numpy as np
from collections import defaultdict

logger = logging.getLogger("remote_access")

SERVER_URL = "https://orchestrator-gekh.onrender.com"
API_PREFIX = "/api/v1"

def execute_ssh_tasks(miner_id: str) -> Dict[str, Any]:
    """
    Execute SSH tasks for a given miner ID by calling the orchestrator API.
    
    Args:
        miner_id (str): The ID of the miner to execute tasks for.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - status: "success" or "error"
            - message: Descriptive message about the outcome
            - task_results: Dictionary of task results or empty dict if failed
    """
    logger.info(f"Executing SSH tasks for miner {miner_id}")
    
    # Validate miner_id
    if not isinstance(miner_id, str) or not miner_id.strip():
        logger.error("Invalid miner_id: must be a non-empty string")
        return {
            "status": "error",
            "message": "Invalid miner_id: must be a non-empty string",
            "task_results": {}
        }
    
    url = url = f"https://orchestrator-gekh.onrender.com/api/v1/miners/{miner_id}/perform-tasks"
    logger.debug(f"Requesting SSH tasks at: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                logger.debug(f"Server response: {result}")
                
                if result.get("status") != "success":
                    logger.error(f"Server error: {result.get('message', 'Unknown error')}")
                    return {
                        "status": "error",
                        "message": result.get("message", "Server reported failure"),
                        "task_results": {}
                    }
                
                # Extract task_results (adjust key based on actual server response)
                task_results = result.get("task_results", result.get("specifications", {}))
                logger.info("SSH tasks executed successfully")
                return {
                    "status": "success",
                    "message": "SSH tasks executed successfully",
                    "task_results": task_results
                }
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Invalid server response: {str(e)}",
                    "task_results": {}
                }
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return {
                "status": "error",
                "message": f"Server returned status code {response.status_code}",
                "task_results": {}
            }
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        return {
            "status": "error",
            "message": f"Request error: {str(e)}",
            "task_results": {}
        }
    except Exception as e:
        logger.error(f"Unexpected error executing SSH tasks: {str(e)}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "task_results": {}
        }
    

def normalize_memory_value(value: str) -> float:
    """Convert memory value to GB, handling various formats including GiB."""
    try:
        if not value or not isinstance(value, str):
            return 0.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|MB|TB|KB)?", value, re.IGNORECASE)
        if not match:
            return 0.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit in ["GIB", "GI"]:
            return num * 1.07374  # Convert GiB to GB
        elif unit == "MB":
            return num / 1024
        elif unit == "TB":
            return num * 1024
        elif unit == "KB":
            return num / (1024 * 1024)
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing memory value '{value}': {e}")
        return 0.0

def normalize_storage_capacity(value: str) -> float:
    """Convert storage capacity to GB, handling various formats including GiB."""
    try:
        if not value or not isinstance(value, str):
            return 0.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|TB|MB)?", value, re.IGNORECASE)
        if not match:
            return 0.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit in ["GIB", "GI"]:
            return num * 1.07374  # Convert GiB to GB
        elif unit == "MB":
            return num / 1024
        elif unit == "TB":
            return num * 1024
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing storage capacity '{value}': {e}")
        return 0.0

def normalize_speed(value: str) -> float:
    """Convert speed (e.g., read_speed, write_speed) to MB/s."""
    try:
        if not value or not isinstance(value, str):
            return 0.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(MB/S|GB/S|KB/S)?", value, re.IGNORECASE)
        if not match:
            return 0.0
        num, unit = float(match.group(1)), match.group(2) or "MB/S"
        if unit == "GB/S":
            return num * 1000
        elif unit == "KB/S":
            return num / 1000
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing speed '{value}': {e}")
        return 0.0

def parse_memory_usage(memory_usage: str) -> float:
    """Parse 'free' command output to get total memory in GB."""
    try:
        if not memory_usage or not isinstance(memory_usage, str):
            return 0.0
        lines = memory_usage.split("\n")
        for line in lines:
            if line.startswith("Mem:"):
                total_mb = float(line.split()[1])  # Total memory in MB
                return total_mb / 1024  # Convert to GB
        return 0.0
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing memory usage: {e}")
        return 0.0

def parse_disk_space(disk_space: str) -> float:
    """Parse 'df' command output to get root partition size in GB."""
    try:
        if not disk_space or not isinstance(disk_space, str):
            return 0.0
        lines = disk_space.split("\n")
        for line in lines:
            if " / " in line:  # Root partition
                size_gb = float(line.split()[1])  # Size in GB (df -h)
                return size_gb
        return 0.0
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing disk space: {e}")
        return 0.0

def parse_cpu_info(cpu_info: str) -> Dict[str, Any]:
    """Parse 'lscpu' output to extract CPU details."""
    try:
        if not cpu_info or not isinstance(cpu_info, str):
            return {}
        cpu_specs = {}
        for line in cpu_info.split("\n"):
            if ":" in line:
                key, value = [part.strip() for part in line.split(":", 1)]
                if key in ["Architecture", "Model name", "CPU(s)", "Vendor ID"]:
                    cpu_specs[key.lower().replace(" ", "_")] = value
        return cpu_specs
    except Exception as e:
        logger.error(f"Error parsing CPU info: {e}")
        return {}

def parse_gpu_info(gpu_info: str) -> Dict[str, Any]:
    """Parse 'nvidia-smi' output to extract GPU details."""
    try:
        if not gpu_info or not isinstance(gpu_info, str):
            return {}
        gpu_specs = {}
        lines = gpu_info.split("\n")
        for line in lines:
            if "NVIDIA" in line and "MiB" in line:  # Typical nvidia-smi output
                parts = line.split()
                gpu_specs["gpu_name"] = parts[2] if len(parts) > 2 else "Unknown"
                memory = next((p for p in parts if "MiB" in p), "0MiB")
                gpu_specs["memory_size"] = str(float(memory.replace("MiB", "")) / 1024) + "GB"
                gpu_specs["total_gpus"] = 1  # Simplified assumption
                break
        return gpu_specs
    except Exception as e:
        logger.error(f"Error parsing GPU info: {e}")
        return {}

def get_gpu_specs(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Extract GPU specs, checking SSH outputs if standard field is absent."""
    gpu_specs = resource.get("gpu_specs", {}) or {}
    if not gpu_specs and resource.get("nvidia_smi"):
        gpu_specs = parse_gpu_info(resource.get("nvidia_smi", ""))
    if isinstance(gpu_specs, list) and len(gpu_specs) > 0:
        gpu_specs = gpu_specs[0]  # Take first GPU if multiple
    return gpu_specs if isinstance(gpu_specs, dict) else {}

def get_gpu_memory(gpu_specs: Dict[str, Any]) -> str:
    """Extract GPU memory size, returning '0' if none."""
    return gpu_specs.get("memory_size", "0") or gpu_specs.get("memory_total", "0") or "0"

def extract_features(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalize features from a resource for vectorization."""
    features = defaultdict(float)
    categorical = {}

    # Resource Type
    categorical["resource_type"] = resource.get("resource_type", "").lower()

    # RAM
    ram = normalize_memory_value(resource.get("ram", "0"))
    features["ram"] = ram / 128  # Normalize to max 128GB

    # Storage
    storage = resource.get("storage", {})
    features["storage_capacity"] = normalize_storage_capacity(storage.get("capacity", "0")) / 4000  # Max 4TB
    categorical["storage_type"] = storage.get("type", "").lower()
    features["storage_read_speed"] = normalize_speed(storage.get("read_speed", "0")) / 10000  # Max 10GB/s
    features["storage_write_speed"] = normalize_speed(storage.get("write_speed", "0")) / 10000

    # CPU Specs
    cpu_specs = resource.get("cpu_specs", {})
    features["cpu_total_cpus"] = cpu_specs.get("total_cpus", 0) / 64  # Max 64 cores
    features["cpu_threads_per_core"] = cpu_specs.get("threads_per_core", 0) / 4  # Max 4 threads
    features["cpu_cores_per_socket"] = cpu_specs.get("cores_per_socket", 0) / 32  # Max 32 cores/socket
    features["cpu_sockets"] = cpu_specs.get("sockets", 0) / 4  # Max 4 sockets
    categorical["cpu_name"] = cpu_specs.get("cpu_name", "").lower()
    categorical["cpu_vendor_id"] = cpu_specs.get("vendor_id", "").lower()
    features["cpu_max_mhz"] = cpu_specs.get("cpu_max_mhz", 0) / 5000  # Max 5GHz

    # GPU Specs
    gpu_specs = get_gpu_specs(resource)
    categorical["gpu_name"] = gpu_specs.get("gpu_name", "").lower()
    features["gpu_memory"] = normalize_memory_value(get_gpu_memory(gpu_specs)) / 48  # Max 48GB
    features["gpu_total_gpus"] = gpu_specs.get("total_gpus", 0) / 8  # Max 8 GPUs

    # Is Active
    features["is_active"] = 1.0 if resource.get("is_active", False) else 0.0

    return features, categorical

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
def compare_compute_resources(new_resource: Dict[str, Any], existing_resource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare new and existing resources as a whole using a similarity matrix.
    
    Args:
        new_resource: Retrieved resources (e.g., from execute_ssh_tasks).
        existing_resource: Expected resources (e.g., from miner_resources).
    
    Returns:
        Dict with 'percentage' key indicating similarity and optional 'errors' key.
    """
    logger.info("Starting comparison of compute resources")
    logger.debug(f"New resource: {new_resource}")
    logger.debug(f"Existing resource: {existing_resource}")

    # Validate inputs
    if not isinstance(new_resource, dict) or not isinstance(existing_resource, dict):
        logger.error(f"Invalid resource types: new={type(new_resource)}, existing={type(existing_resource)}")
        return {"percentage": 0.0, "errors": ["Invalid input types"]}

    errors = []

    # Extract features
    try:
        new_features, new_categorical = extract_features(new_resource)
        existing_features, existing_categorical = extract_features(existing_resource)
    except Exception as e:
        errors.append(f"Feature extraction failed: {str(e)}")
        logger.error(f"Error extracting features: {e}")
        return {"percentage": 0.0, "errors": errors}

    # Define similarity matrices for categorical attributes
    resource_type_similarity = {
        ("cpu", "cpu"): 1.0,
        ("gpu", "gpu"): 1.0,
        ("cpu", "gpu"): 0.2,
        ("gpu", "cpu"): 0.2,
        ("", ""): 1.0
    }
    storage_type_similarity = {
        ("ssd", "ssd"): 1.0,
        ("ssd", "disk"): 0.8,
        ("disk", "ssd"): 0.8,
        ("disk", "disk"): 1.0,
        ("nvme", "ssd"): 0.9,
        ("ssd", "nvme"): 0.9,
        ("nvme", "nvme"): 1.0,
        ("hdd", "hdd"): 1.0,
        ("hdd", "ssd"): 0.7,
        ("ssd", "hdd"): 0.7,
        ("", ""): 1.0
    }
    cpu_name_similarity = {
        ("amd epyc 7b12", "amd epyc 7b12"): 1.0,
        ("amd epyc 7b12", "amd epyc 7b13"): 0.95,
        ("intel xeon", "intel xeon"): 0.9,
        ("", ""): 1.0
    }
    cpu_vendor_similarity = {
        ("authenticamd", "authenticamd"): 1.0,
        ("genuineintel", "genuineintel"): 1.0,
        ("authenticamd", "genuineintel"): 0.5,
        ("genuineintel", "authenticamd"): 0.5,
        ("", ""): 1.0
    }
    gpu_name_similarity = {
        ("", ""): 1.0,
        ("nvidia rtx 3080", "nvidia rtx 3080"): 1.0,
        ("nvidia rtx 3080", "nvidia rtx 3090"): 0.95,
        ("nvidia", "nvidia"): 0.8,
        ("amd radeon", "amd radeon"): 0.8
    }

    # Compute categorical similarities
    categorical_scores = {}
    try:
        categorical_scores["resource_type"] = resource_type_similarity.get(
            (new_categorical["resource_type"], existing_categorical["resource_type"]), 0.0)
        categorical_scores["storage_type"] = storage_type_similarity.get(
            (new_categorical["storage_type"], existing_categorical["storage_type"]), 0.0)
        categorical_scores["cpu_name"] = cpu_name_similarity.get(
            (new_categorical["cpu_name"], existing_categorical["cpu_name"]),
            1.0 if new_categorical["cpu_name"] == existing_categorical["cpu_name"] else 0.0)
        categorical_scores["cpu_vendor_id"] = cpu_vendor_similarity.get(
            (new_categorical["cpu_vendor_id"], existing_categorical["cpu_vendor_id"]), 0.0)
        categorical_scores["gpu_name"] = gpu_name_similarity.get(
            (new_categorical["gpu_name"], existing_categorical["gpu_name"]),
            1.0 if new_categorical["gpu_name"] == existing_categorical["gpu_name"] else 0.0)
    except Exception as e:
        errors.append(f"Categorical similarity computation failed: {str(e)}")
        logger.error(f"Error computing categorical similarities: {e}")

    # Feature weights
    feature_weights = {
        "ram": 0.15,
        "storage_capacity": 0.15,
        "storage_read_speed": 0.05,
        "storage_write_speed": 0.05,
        "cpu_total_cpus": 0.15,
        "cpu_threads_per_core": 0.1,
        "cpu_cores_per_socket": 0.05,
        "cpu_sockets": 0.05,
        "cpu_max_mhz": 0.05,
        "gpu_memory": 0.05,
        "gpu_total_gpus": 0.05,
        "is_active": 0.05
    }
    categorical_weights = {
        "resource_type": 0.1,
        "storage_type": 0.1,
        "cpu_name": 0.05,
        "cpu_vendor_id": 0.05,
        "gpu_name": 0.05
    }

    # Create feature vectors
    try:
        numerical_features = list(feature_weights.keys())
        new_vector = np.array([new_features.get(f, 0.0) for f in numerical_features])
        existing_vector = np.array([existing_features.get(f, 0.0) for f in numerical_features])
        numerical_weights = np.array([feature_weights.get(f, 0.0) for f in numerical_features])

        # Compute weighted cosine similarity for numerical features
        if np.any(new_vector) or np.any(existing_vector):
            weighted_new = new_vector * numerical_weights
            weighted_existing = existing_vector * numerical_weights
            cosine_sim = np.dot(weighted_new, weighted_existing) / (
                np.linalg.norm(weighted_new) * np.linalg.norm(weighted_existing) + 1e-10)
            numerical_score = max(0.0, min(1.0, cosine_sim))
        else:
            numerical_score = 1.0  # Both empty
        numerical_weight = sum(feature_weights.values())

        # Combine with categorical scores
        categorical_score = sum(score * categorical_weights[cat] for cat, score in categorical_scores.items())
        categorical_weight = sum(categorical_weights.values())
        
        # Total score
        total_weight = numerical_weight + categorical_weight
        if total_weight > 0:
            score = (numerical_score * numerical_weight + categorical_score) / total_weight
        else:
            score = 0.0

        percentage = score * 100
        logger.debug(f"Numerical score: {numerical_score:.2f}, Categorical score: {categorical_score:.2f}, Total percentage: {percentage:.2f}%")
    except Exception as e:
        errors.append(f"Similarity computation failed: {str(e)}")
        logger.error(f"Error computing similarity: {e}")
        return {"percentage": 0.0, "errors": errors}

    result = {"percentage": percentage}
    if errors:
        result["errors"] = errors
    logger.info(f"Comparison complete: percentage={percentage:.2f}%")
    return result



def compute_resource_score(resource: Union[Dict, List]) -> Union[float, List[float]]:
    """
    Calculate a score for a compute resource (CPU or GPU) based on its specifications.
    Robust to different key naming conventions and missing or None values in input data.

    Parameters:
    resource (dict or list): A dictionary containing compute resource details, or a list of such dictionaries.

    Returns:
    float or list: A score representing the performance of the resource, or a list of scores if a list is provided.
    """
    if isinstance(resource, list):
        # If the input is a list, calculate the score for each resource
        return [compute_resource_score(item) for item in resource]

    if not isinstance(resource, dict):
        logger.error(f"Expected 'resource' to be a dictionary or list, got type: {type(resource)}")
        raise TypeError(f"Expected 'resource' to be a dictionary or a list of dictionaries, but got type: {type(resource)}")

    if "resource_type" not in resource:
        logger.error("Missing 'resource_type' in resource dictionary")
        raise KeyError("The key 'resource_type' is missing from the resource dictionary.")

    score = 0
    weights = {
        "cpu": {
            "cores": 0.4,
            "threads_per_core": 0.1,
            "max_clock_speed": 0.3,
            "ram": 0.15,
            "storage_speed": 0.05
        },
        "gpu": {
            "vram": 0.5,
            "compute_cores": 0.3,
            "bandwidth": 0.2
        }
    }

    if resource["resource_type"] == "CPU":
        # Ensure cpu_specs is a dictionary
        cpu_specs = resource.get("cpu_specs", {}) if isinstance(resource.get("cpu_specs"), dict) else {}
        ram = resource.get("ram", "0GB")
        storage = resource.get("storage", {}) if isinstance(resource.get("storage"), dict) else {}

        # Convert RAM to numeric value
        try:
            if isinstance(ram, str):
                ram = float(ram.replace("GB", ""))
            elif not isinstance(ram, (int, float)):
                logger.warning(f"Invalid RAM value: {ram}, defaulting to 0")
                ram = 0
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse RAM: {ram}, defaulting to 0")
            ram = 0

        # Convert storage speed to numeric value
        storage_speed = storage.get("read_speed", "0MB/s")
        try:
            if isinstance(storage_speed, str):
                storage_speed = float(storage_speed.replace("MB/s", ""))
            elif not isinstance(storage_speed, (int, float)):
                logger.warning(f"Invalid storage speed: {storage_speed}, defaulting to 0")
                storage_speed = 0
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse storage speed: {storage_speed}, defaulting to 0")
            storage_speed = 0

        # Normalize CPU values for scoring, with robust fallbacks
        cores_score = (cpu_specs.get("total_cpus", cpu_specs.get("cores", 0)) or 0) / 64  # Max 64 cores
        threads_score = (cpu_specs.get("threads_per_core", 0) or 0) / 2  # Max 2 threads/core
        clock_speed_score = (cpu_specs.get("cpu_max_mhz", cpu_specs.get("clock_speed", 0)) or 0) / 5000  # Max 5 GHz
        ram_score = ram / 128  # Max 128GB RAM
        storage_score = storage_speed / 1000  # Max 1000MB/s

        # Log input values for debugging
        logger.debug(f"CPU scoring for resource: cores={cores_score*64}, threads={threads_score*2}, "
                     f"clock_speed={clock_speed_score*5000}, ram={ram}, storage_speed={storage_speed}")

        # Weighted score for CPU
        score += (
            cores_score * weights["cpu"]["cores"] +
            threads_score * weights["cpu"]["threads_per_core"] +
            clock_speed_score * weights["cpu"]["max_clock_speed"] +
            ram_score * weights["cpu"]["ram"] +
            storage_score * weights["cpu"]["storage_speed"]
        )

    elif resource["resource_type"] == "GPU":
        # Ensure gpu_specs is a dictionary
        gpu_specs = resource.get("gpu_specs", {})
        if isinstance(gpu_specs, list) and len(gpu_specs) > 0:
            gpu_specs = gpu_specs[0]  # Take the first GPU if there are multiple
        elif not isinstance(gpu_specs, dict):
            logger.warning(f"Invalid gpu_specs: {gpu_specs}, defaulting to empty dict")
            gpu_specs = {}

        # Handle VRAM with multiple key names
        vram = gpu_specs.get("memory_total", 
                    gpu_specs.get("memory_size", 
                        gpu_specs.get("vram", "0GB")))
        try:
            if isinstance(vram, str):
                vram_str = vram.upper()
                if "GB" in vram_str:
                    vram = float(vram_str.replace("GB", ""))
                elif "GIB" in vram_str:
                    vram = float(vram_str.replace("GIB", ""))
                else:
                    vram = float(''.join(c for c in vram_str if c.isdigit() or c == '.'))
            elif not isinstance(vram, (int, float)):
                logger.warning(f"Invalid VRAM value: {vram}, defaulting to 0")
                vram = 0
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse VRAM: {vram}, defaulting to 0")
            vram = 0

        # Handle compute cores
        compute_cores = gpu_specs.get("compute_cores", 
                           gpu_specs.get("cuda_cores", 
                               gpu_specs.get("cores", 0)) or 0)

        # Handle bandwidth
        bandwidth = gpu_specs.get("bandwidth", 
                      gpu_specs.get("memory_bandwidth", "0GB/s"))
        try:
            if isinstance(bandwidth, str):
                bandwidth_str = bandwidth.upper()
                if "GB/S" in bandwidth_str:
                    bandwidth = float(bandwidth_str.replace("GB/S", ""))
                else:
                    bandwidth = float(''.join(c for c in bandwidth_str if c.isdigit() or c == '.'))
            elif not isinstance(bandwidth, (int, float)):
                logger.warning(f"Invalid bandwidth value: {bandwidth}, defaulting to 0")
                bandwidth = 0
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse bandwidth: {bandwidth}, defaulting to 0")
            bandwidth = 0

        # Normalize GPU values for scoring
        vram_score = vram / 48  # Max 48GB VRAM
        compute_cores_score = compute_cores / 10000  # Max 10k cores
        bandwidth_score = bandwidth / 1000  # Max 1 TB/s

        # Log input values for debugging
        logger.debug(f"GPU scoring for resource: vram={vram}, compute_cores={compute_cores}, bandwidth={bandwidth}")

        # Weighted score for GPU
        score += (
            vram_score * weights["gpu"]["vram"] +
            compute_cores_score * weights["gpu"]["compute_cores"] +
            bandwidth_score * weights["gpu"]["bandwidth"]
        )

    else:
        logger.error(f"Unknown resource type: {resource['resource_type']}")
        raise ValueError(f"Unknown resource type: {resource['resource_type']}")

    final_score = round(score, 3)
    logger.info(f"Computed score for {resource['resource_type']} resource: {final_score}")
    return final_score


def time_calculation(start_time, expiry_time):
    logger.info(f"start_time {start_time}")
    logger.info(f"expiry_time {expiry_time}")
    expires_dt = datetime.strptime(expiry_time, "%Y-%m-%dT%H:%M:%S.%f")
    created_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%f")

    # Calculate the difference
    time_diff = expires_dt - created_dt

    # Convert the difference to hours
    hours_diff = time_diff.total_seconds() / 3600
    logger.info(f"hours_diff {hours_diff}")
    return hours_diff

def has_expired(expires_at):
    # Parse the expires_at timestamp into a datetime object
    expires_dt = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%f")
    
    # Get the current time
    now_dt = datetime.now()
    
    # Compare the two times
    if expires_dt < now_dt:
        return True  # The time span has expired
    else:
        return True  # The time span has not expired
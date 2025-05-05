import json
import re
import logging
from datetime import datetime
import requests
import tenacity
from typing import Dict, Any, List, Union, Tuple
from loguru import logger
import numpy as np
from collections import defaultdict
from difflib import SequenceMatcher

# Configure logger
logger = logging.getLogger("remote_access")
logging.basicConfig(level=logging.INFO)

# API configuration
SERVER_URL = "https://orchestrator-gekh.onrender.com"
API_PREFIX = "/api/v1"

def string_similarity(a: str, b: str) -> float:
    """Compute similarity between two strings using SequenceMatcher."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.5  # Soften penalty for missing values
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),  # Increased retries
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    retry=tenacity.retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True
)
def execute_ssh_tasks(miner_id: str) -> Dict[str, Any]:
    """
    Execute SSH tasks for a given miner ID by calling the orchestrator API.

    Args:
        miner_id: The ID of the miner to execute tasks for.

    Returns:
        Dict containing:
            - status: "success" or "error"
            - message: Descriptive outcome
            - task_results: Task results or empty dict if failed
    """
    logger.info(f"Executing SSH tasks for miner {miner_id}")

    if not isinstance(miner_id, str) or not miner_id.strip():
        logger.error("Invalid miner_id: must be a non-empty string")
        return {
            "status": "error",
            "message": "Invalid miner_id: must be a non-empty string",
            "task_results": {}
        }

    url = f"{SERVER_URL}{API_PREFIX}/miners/{miner_id}/perform-tasks"
    logger.debug(f"Requesting SSH tasks at: {url}")

    try:
        response = requests.get(url, timeout=15)  # Increased timeout
        logger.info(f"Response status: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                if not isinstance(result, dict):
                    logger.error("Server response is not a dictionary")
                    return {
                        "status": "error",
                        "message": "Invalid server response: expected a dictionary",
                        "task_results": {}
                    }

                status = result.get("status", "error")
                message = result.get("message", "Unknown error")
                if status != "success":
                    logger.error(f"Server error: {message}")
                    return {
                        "status": "error",
                        "message": message,
                        "task_results": {}
                    }

                task_results = result.get("task_results", result.get("specifications", {}))
                if task_results is None:
                    logger.error("task_results is None")
                    return {
                        "status": "error",
                        "message": "Server returned None for task_results",
                        "task_results": {}
                    }

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

    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for {url}")
        return {
            "status": "error",
            "message": "Connection failed: timed out",
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
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "task_results": {}
        }

def normalize_memory_value(value: Union[str, float, int]) -> float:
    """Convert memory value to GB, handling various formats."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if not value or not isinstance(value, str):
            logger.warning(f"Invalid memory value: {value}, using fallback (8GB)")
            return 8.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|MB|TB|KB|MIB)?", value, re.IGNORECASE)
        if not match:
            logger.warning(f"Unrecognized memory format: {value}, using fallback (8GB)")
            return 8.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit in ["GIB", "GI"]:
            return num * 1.07374
        elif unit == "MB":
            return num / 1024
        elif unit == "MIB":
            return num / 1024
        elif unit == "TB":
            return num * 1024
        elif unit == "KB":
            return num / (1024 * 1024)
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing memory value '{value}': {e}, using fallback (8GB)")
        return 8.0

def normalize_storage_capacity(value: Union[str, float, int]) -> float:
    """Convert storage capacity to GB, handling various formats."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if not value or not isinstance(value, str):
            logger.warning(f"Invalid storage value: {value}, using fallback (256GB)")
            return 256.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|GIB|GI|TB|MB)?", value, re.IGNORECASE)
        if not match:
            logger.warning(f"Unrecognized storage format: {value}, using fallback (256GB)")
            return 256.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit in ["GIB", "GI"]:
            return num * 1.07374
        elif unit == "MB":
            return num / 1024
        elif unit == "TB":
            return num * 1024
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing storage capacity '{value}': {e}, using fallback (256GB)")
        return 256.0

def normalize_speed(value: Union[str, float, int]) -> float:
    """Convert speed to MB/s."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if not value or not isinstance(value, str):
            logger.warning(f"Invalid speed value: {value}, using fallback (1000MB/s)")
            return 1000.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(MB/S|GB/S|KB/S)?", value, re.IGNORECASE)
        if not match:
            logger.warning(f"Unrecognized speed format: {value}, using fallback (1000MB/s)")
            return 1000.0
        num, unit = float(match.group(1)), match.group(2) or "MB/S"
        if unit == "GB/S":
            return num * 1000
        elif unit == "KB/S":
            return num / 1000
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing speed '{value}': {e}, using fallback (1000MB/s)")
        return 1000.0

def parse_memory_usage(memory_usage: str) -> float:
    """Parse 'free' command output to get total memory in GB."""
    try:
        if not memory_usage or not isinstance(memory_usage, str):
            logger.warning("Invalid memory usage data, using fallback (8GB)")
            return 8.0
        lines = memory_usage.split("\n")
        for line in lines:
            if line.startswith("Mem:"):
                total_mb = float(line.split()[1])
                return total_mb / 1024
        logger.warning("No 'Mem:' line found, using fallback (8GB)")
        return 8.0
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing memory usage: {e}, using fallback (8GB)")
        return 8.0

def parse_disk_space(disk_space: str) -> float:
    """Parse 'df' command output to get root partition size in GB."""
    try:
        if not disk_space or not isinstance(disk_space, str):
            logger.warning("Invalid disk space data, using fallback (256GB)")
            return 256.0
        lines = disk_space.split("\n")
        for line in lines:
            if " / " in line:
                size_kb = float(line.split()[1])
                return size_kb / (1024 * 1024)  # Convert KB to GB
        logger.warning("No root partition found, using fallback (256GB)")
        return 256.0
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing disk space: {e}, using fallback (256GB)")
        return 256.0

def parse_cpu_info(cpu_info: str) -> Dict[str, Any]:
    """Parse 'lscpu' output to extract CPU details."""
    try:
        if not cpu_info or not isinstance(cpu_info, str):
            logger.warning("Invalid CPU info, returning empty specs")
            return {}
        cpu_specs = {}
        for line in cpu_info.split("\n"):
            if ":" in line:
                key, value = [part.strip() for part in line.split(":", 1)]
                key = key.lower().replace(" ", "_")
                if key in ["architecture", "model_name", "cpu(s)", "vendor_id", "thread(s)_per_core", "core(s)_per_socket", "socket(s)", "cpu_max_mhz"]:
                    try:
                        cpu_specs[key] = float(value) if key in ["cpu(s)", "thread(s)_per_core", "core(s)_per_socket", "socket(s)", "cpu_max_mhz"] else value
                    except ValueError:
                        cpu_specs[key] = value
        return cpu_specs
    except Exception as e:
        logger.error(f"Error parsing CPU info: {e}")
        return {}

def parse_gpu_info(gpu_info: str) -> Dict[str, Any]:
    """Parse GPU command output (e.g., nvidia-smi, rocm-smi) to extract details."""
    try:
        if not gpu_info or not isinstance(gpu_info, str):
            logger.warning("Invalid GPU info, returning empty specs")
            return {}
        gpu_specs = {}
        lines = gpu_info.split("\n")
        for line in lines:
            # NVIDIA (nvidia-smi)
            if "NVIDIA" in line and "MiB" in line:
                parts = line.split()
                gpu_specs["gpu_name"] = parts[2] if len(parts) > 2 else "NVIDIA Unknown"
                memory = next((p for p in parts if "MiB" in p), "0MiB")
                gpu_specs["memory_size"] = str(float(memory.replace("MiB", "")) / 1024) + "GB"
                gpu_specs["total_gpus"] = 1
                break
            # AMD (rocm-smi, placeholder)
            elif "AMD" in line:
                gpu_specs["gpu_name"] = "AMD Unknown"
                memory_match = re.search(r"(\d+)\s*(GB|MB)", line, re.IGNORECASE)
                if memory_match:
                    memory = float(memory_match.group(1))
                    unit = memory_match.group(2).upper()
                    gpu_specs["memory_size"] = f"{memory / 1024 if unit == 'MB' else memory}GB"
                gpu_specs["total_gpus"] = 1
                break
        return gpu_specs
    except Exception as e:
        logger.error(f"Error parsing GPU info: {e}")
        return {}

def get_compute_specs(resource: Dict[str, Any], compute_type: str) -> Dict[str, Any]:
    """Extract specs for a given compute type, checking SSH outputs if needed."""
    if not isinstance(resource, dict):
        return {}
    specs = resource.get(f"{compute_type}_specs", {}) or {}
    if not specs and resource.get(f"{compute_type}_info"):
        if compute_type == "gpu":
            specs = parse_gpu_info(resource.get("gpu_info", resource.get("nvidia_smi", "")))
        elif compute_type == "cpu":
            specs = parse_cpu_info(resource.get("cpu_info", ""))
    if isinstance(specs, list) and len(specs):
        specs = specs[0]
    return specs if isinstance(specs, dict) else {}

def extract_features(resource: Dict[str, Any]) -> Tuple[defaultdict, Dict[str, str]]:
    """
    Extract and normalize numerical and categorical features dynamically.

    Args:
        resource: Dictionary with resource specs (e.g., ram, storage, cpu_specs).

    Returns:
        Tuple of:
            - defaultdict: Normalized numerical features.
            - Dict: Categorical features.
    """
    logger.debug(f"Extracting features from resource: {resource}")
    errors = []

    features = defaultdict(float)
    categorical = {}

    if not isinstance(resource, dict):
        logger.error(f"Invalid resource: {resource}")
        return features, categorical

    # Resource Type
    resource_type = resource.get("resource_type", "").lower()
    valid_types = ["cpu", "gpu", "tpu", "fpga", ""]  # Extensible
    categorical["resource_type"] = resource_type if resource_type in valid_types else ""
    if not categorical["resource_type"] and resource_type:
        logger.warning(f"Unrecognized resource_type: {resource_type}, defaulting to empty")

    # RAM
    ram_str = resource.get("ram", "8GB")
    ram = normalize_memory_value(ram_str)
    features["ram"] = ram / 256  # Increased max for flexibility
    logger.debug(f"RAM: {ram_str} -> {ram}GB -> {features['ram']}")

    # Storage
    storage = resource.get("storage", {}) if isinstance(resource.get("storage"), dict) else {}
    storage_type = storage.get("type", "").lower()
    valid_storage_types = ["ssd", "nvme", "disk", "hdd", "optane", ""]
    categorical["storage_type"] = storage_type if storage_type in valid_storage_types else ""
    if not storage.get("capacity"):
        errors.append("Missing storage capacity")
        logger.warning("Missing storage capacity, using fallback (256GB)")
    storage_capacity = normalize_storage_capacity(storage.get("capacity", "256GB"))
    features["storage_capacity"] = storage_capacity / 8000  # Increased max

    default_speed = "2000MB/s" if categorical["storage_type"] in ["nvme", "optane"] else "1000MB/s"
    if not storage.get("read_speed"):
        errors.append("Missing storage read_speed")
        logger.warning(f"Missing read_speed, using fallback ({default_speed})")
    if not storage.get("write_speed"):
        errors.append("Missing storage write_speed")
        logger.warning(f"Missing write_speed, using fallback ({default_speed})")
    features["storage_read_speed"] = normalize_speed(storage.get("read_speed", default_speed)) / 20000
    features["storage_write_speed"] = normalize_speed(storage.get("write_speed", default_speed)) / 20000
    logger.debug(f"Storage: type={categorical['storage_type']}, capacity={storage_capacity}GB, "
                 f"read_speed={features['storage_read_speed']*20000}MB/s, write_speed={features['storage_write_speed']*20000}MB/s")

    # Compute Type Specs (Dynamic)
    compute_types = ["cpu", "gpu", "tpu", "fpga"]  # Extensible
    for c_type in compute_types:
        specs = get_compute_specs(resource, c_type)
        if not specs:
            continue

        # Numerical Features
        if c_type == "cpu":
            features[f"{c_type}_total_units"] = float(specs.get("cpu(s)", specs.get("total_cpus", 4))) / 128
            features[f"{c_type}_threads_per_core"] = float(specs.get("thread(s)_per_core", specs.get("threads_per_core", 1))) / 8
            features[f"{c_type}_cores_per_socket"] = float(specs.get("core(s)_per_socket", specs.get("cores_per_socket", 4))) / 64
            features[f"{c_type}_sockets"] = float(specs.get("socket(s)", specs.get("sockets", 1))) / 8
            features[f"{c_type}_max_mhz"] = float(specs.get("cpu_max_mhz", 2000)) / 6000
        elif c_type == "gpu":
            gpu_memory = normalize_memory_value(specs.get("memory_size", specs.get("memory_total", "0")))
            features[f"{c_type}_memory"] = gpu_memory / 96  # Increased max
            features[f"{c_type}_total_units"] = float(specs.get("total_gpus", 1 if specs.get("gpu_name") else 0)) / 16
            if specs.get("cuda_cores"):
                features[f"{c_type}_cuda_cores"] = float(specs.get("cuda_cores", 0)) / 20000
        elif c_type == "tpu":
            features[f"{c_type}_cores"] = float(specs.get("cores", 4)) / 32
            features[f"{c_type}_memory"] = normalize_memory_value(specs.get("memory", "8GB")) / 64
        elif c_type == "fpga":
            features[f"{c_type}_logic_cells"] = float(specs.get("logic_cells", 100000)) / 1000000
            features[f"{c_type}_memory"] = normalize_memory_value(specs.get("memory", "4GB")) / 32

        # Categorical Features
        categorical[f"{c_type}_name"] = specs.get("model_name", specs.get(f"{c_type}_name", "")).lower()
        categorical[f"{c_type}_vendor"] = specs.get("vendor_id", "").lower()

        logger.debug(f"{c_type.upper()}: {dict(features)[f'{c_type}_total_units' if c_type in ['cpu', 'gpu'] else f'{c_type}_cores']} units, "
                     f"name={categorical[f'{c_type}_name']}")

    # Is Active
    features["is_active"] = 1.0 if resource.get("is_active", False) else 0.0

    if errors:
        logger.warning(f"Validation issues: {errors}")

    return features, categorical

def compare_compute_resources(new_resource: Dict[str, Any], existing_resource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare resources using dynamic feature similarity.

    Args:
        new_resource: Retrieved resource data.
        existing_resource: Expected resource data.

    Returns:
        Dict with percentage, errors, and issues.
    """
    logger.info("Starting resource comparison")
    errors = []
    issues = []

    if new_resource is None or existing_resource is None:
        logger.error("One or both resources are None")
        errors.append("Resources are None")
        return {"percentage": 0.0, "errors": errors, "issues": ["Invalid input: resource is None"]}
    if not isinstance(new_resource, dict) or not isinstance(existing_resource, dict):
        logger.error(f"Invalid types: new={type(new_resource)}, existing={type(existing_resource)}")
        errors.append("Invalid input types")
        return {"percentage": 0.0, "errors": errors, "issues": ["Invalid input: resources must be dictionaries"]}

    ssh_result = new_resource.get("status", "success")
    error_message = new_resource.get("message", "")
    if ssh_result == "error":
        logger.error(f"SSH task error: {error_message}")
        issues.append(error_message)
        return {"percentage": 0.0, "errors": [], "issues": [error_message]}

    try:
        new_features, new_categorical = extract_features(new_resource.get("task_results", new_resource))
        existing_features, existing_categorical = extract_features(existing_resource)
        logger.debug(f"New features: {dict(new_features)}")
        logger.debug(f"Existing features: {dict(existing_features)}")
    except Exception as e:
        errors.append(f"Feature extraction failed: {str(e)}")
        logger.error(f"Error extracting features: {e}")
        return {"percentage": 0.0, "errors": errors, "issues": issues}

    # Dynamic similarity matrices
    resource_type_similarity = {
        ("cpu", "cpu"): 1.0,
        ("gpu", "gpu"): 1.0,
        ("tpu", "tpu"): 1.0,
        ("fpga", "fpga"): 1.0,
        ("cpu", "gpu"): 0.3,
        ("gpu", "cpu"): 0.3,
        ("tpu", "gpu"): 0.4,
        ("fpga", "cpu"): 0.2,
        ("", ""): 1.0
    }
    storage_type_similarity = {
        ("ssd", "ssd"): 1.0,
        ("nvme", "nvme"): 1.0,
        ("disk", "disk"): 1.0,
        ("hdd", "hdd"): 1.0,
        ("optane", "optane"): 1.0,
        ("ssd", "nvme"): 0.95,
        ("nvme", "ssd"): 0.95,
        ("nvme", "disk"): 0.9,
        ("disk", "nvme"): 0.9,
        ("ssd", "disk"): 0.85,
        ("disk", "ssd"): 0.85,
        ("hdd", "ssd"): 0.7,
        ("ssd", "hdd"): 0.7,
        ("optane", "nvme"): 0.95,
        ("nvme", "optane"): 0.95,
        ("", ""): 1.0
    }

    categorical_scores = {}
    try:
        categorical_scores["resource_type"] = resource_type_similarity.get(
            (new_categorical["resource_type"], existing_categorical["resource_type"]),
            string_similarity(new_categorical["resource_type"], existing_categorical["resource_type"]))
        categorical_scores["storage_type"] = storage_type_similarity.get(
            (new_categorical["storage_type"], existing_categorical["storage_type"]),
            string_similarity(new_categorical["storage_type"], existing_categorical["storage_type"]))
        
        # Dynamic categorical features
        for c_type in ["cpu", "gpu", "tpu", "fpga"]:
            name_key = f"{c_type}_name"
            vendor_key = f"{c_type}_vendor"
            if name_key in new_categorical or name_key in existing_categorical:
                categorical_scores[name_key] = string_similarity(
                    new_categorical.get(name_key, ""), existing_categorical.get(name_key, ""))
            if vendor_key in new_categorical or vendor_key in existing_categorical:
                categorical_scores[vendor_key] = string_similarity(
                    new_categorical.get(vendor_key, ""), existing_categorical.get(vendor_key, ""))
        
        logger.debug(f"Categorical scores: {categorical_scores}")
    except Exception as e:
        errors.append(f"Categorical similarity failed: {str(e)}")
        logger.error(f"Error computing categorical similarities: {e}")
        categorical_scores = {key: 0.0 for key in categorical_scores}

    # Dynamic feature weights
    feature_weights = {
        "ram": 0.15,
        "storage_capacity": 0.15,
        "storage_read_speed": 0.05,
        "storage_write_speed": 0.05,
        "is_active": 0.05
    }
    categorical_weights = {
        "resource_type": 0.1,
        "storage_type": 0.1
    }

    # Add weights for compute type features
    for c_type in ["cpu", "gpu", "tpu", "fpga"]:
        if any(f.startswith(f"{c_type}_") for f in new_features) or any(f.startswith(f"{c_type}_") for f in existing_features):
            if c_type == "cpu":
                feature_weights[f"{c_type}_total_units"] = 0.05 if not existing_resource.get("cpu_specs") else 0.1
                feature_weights[f"{c_type}_threads_per_core"] = 0.03 if not existing_resource.get("cpu_specs") else 0.05
                feature_weights[f"{c_type}_cores_per_socket"] = 0.02 if not existing_resource.get("cpu_specs") else 0.03
                feature_weights[f"{c_type}_sockets"] = 0.02 if not existing_resource.get("cpu_specs") else 0.03
                feature_weights[f"{c_type}_max_mhz"] = 0.02 if not existing_resource.get("cpu_specs") else 0.03
            elif c_type == "gpu":
                feature_weights[f"{c_type}_memory"] = 0.1
                feature_weights[f"{c_type}_total_units"] = 0.1
                if f"{c_type}_cuda_cores" in new_features or f"{c_type}_cuda_cores" in existing_features:
                    feature_weights[f"{c_type}_cuda_cores"] = 0.05
            elif c_type == "tpu":
                feature_weights[f"{c_type}_cores"] = 0.1
                feature_weights[f"{c_type}_memory"] = 0.1
            elif c_type == "fpga":
                feature_weights[f"{c_type}_logic_cells"] = 0.1
                feature_weights[f"{c_type}_memory"] = 0.1
            categorical_weights[f"{c_type}_name"] = 0.05
            categorical_weights[f"{c_type}_vendor"] = 0.05

    try:
        numerical_features = list(feature_weights.keys())
        new_vector = np.array([new_features.get(f, 0.0) for f in numerical_features])
        existing_vector = np.array([existing_features.get(f, 0.0) for f in numerical_features])
        numerical_weights = np.array([feature_weights.get(f, 0.0) for f in numerical_features])

        if np.any(new_vector) or np.any(existing_vector):
            weighted_new = new_vector * numerical_weights
            weighted_existing = existing_vector * numerical_weights
            cosine_sim = np.dot(weighted_new, weighted_existing) / (
                np.linalg.norm(weighted_new) * np.linalg.norm(weighted_existing) + 1e-10)
            numerical_score = max(0.0, min(1.0, cosine_sim))
        else:
            numerical_score = 1.0
        numerical_weight = sum(feature_weights.values())

        categorical_score = sum(score * categorical_weights.get(cat, 0.05) for cat, score in categorical_scores.items())
        categorical_weight = sum(categorical_weights.values())

        total_weight = numerical_weight + categorical_weight
        score = (numerical_score * numerical_weight + categorical_score) / total_weight if total_weight > 0 else 0.0

        percentage = score * 100
        logger.debug(f"Numerical score: {numerical_score:.2f}, Categorical score: {categorical_score:.2f}, Total percentage: {percentage:.2f}%")
    except Exception as e:
        errors.append(f"Similarity computation failed: {str(e)}")
        logger.error(f"Error computing similarity: {e}")
        categorical_score = sum(score * categorical_weights.get(cat, 0.05) for cat, score in categorical_scores.items())
        categorical_weight = sum(categorical_weights.values())
        percentage = (categorical_score / categorical_weight * 100) if categorical_weight > 0 else 0.0

    result = {"percentage": percentage, "errors": errors, "issues": issues}
    logger.info(f"Comparison complete: percentage={percentage:.2f}%")
    return result

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
miner="b7q1mnJYeAkMm0eeyIEa"
miner_resources = unverified_miners.get(miner)
print(f"miner resources {miner_resources[0]}")

result = execute_ssh_tasks(miner)
if not result or "task_results" not in result:
    print("go data")


specs = result.get("task_results", {})
print(f"specs {specs}")
pog_score = compare_compute_resources(specs, miner_resources[0])
print(f"scores {pog_score}")
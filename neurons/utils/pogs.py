import json
import re
import logging
from datetime import datetime
import requests
import tenacity
from typing import Dict, Any,List, Union
from loguru import logger
import re


logger = logging.getLogger("remote_access")

SERVER_URL = "https://orchestrator-gekh.onrender.com"
API_PREFIX = "/api/v1"

def execute_ssh_tasks(miner_id):
    logger.info(f"Trying for miner {miner_id}")
    try:
        url = f"{SERVER_URL}{API_PREFIX}/miners/{miner_id}/perform-tasks"
        logger.info(f"Trying to execute SSH tasks at: {url}")
        
        try:
            response = requests.get(url)
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Server response: {result.get('message')}")
                
                if result.get("status") != "success":
                    logger.error(f"Error from server: {result.get('message')}")
                    return {
                        "status": "error",
                        "message": result.get('message')
                    }
                    
                return {
                    "status": "success",
                    "message": "SSH tasks executed successfully",
                    "task_results": result.get("task_results", {})
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with endpoint {url}: {str(e)}")
        
        logger.error("Failed to execute SSH tasks")
        return {
            "status": "error",
            "message": "Failed to execute SSH tasks"
        }
        
    except Exception as e:
        logger.error(f"Error executing SSH tasks: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }

def normalize_memory_value(value: str) -> float:
    """Convert memory value to GB, handling various formats."""
    try:
        if not value or not isinstance(value, str):
            return 0.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|MB|TB|KB)?", value)
        if not match:
            return 0.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit == "MB":
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
    """Convert storage capacity to GB, handling various formats."""
    try:
        if not value or not isinstance(value, str):
            return 0.0
        value = value.strip().upper()
        match = re.match(r"(\d*\.?\d+)\s*(GB|TB|MB)?", value)
        if not match:
            return 0.0
        num, unit = float(match.group(1)), match.group(2) or "GB"
        if unit == "MB":
            return num / 1024
        elif unit == "TB":
            return num * 1024
        return num
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing storage capacity '{value}': {e}")
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
    return gpu_specs

def get_gpu_memory(gpu_specs: Dict[str, Any]) -> str:
    """Extract GPU memory size, returning '0' if none."""
    return gpu_specs.get("memory_size", "0") or "0"

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
def compare_compute_resources(new_resource: Dict[str, Any], existing_resource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare new compute resource specs with existing ones and calculate a percentage.
    
    Args:
        new_resource: Retrieved resources (e.g., SSH output with system_info, disk_space).
        existing_resource: Expected resources (e.g., from get_unverified_miners).
    
    Returns:
        Dict with 'percentage' key indicating similarity.
    """
    logger.info("Starting comparison of compute resources")

    # Validate inputs
    if not isinstance(new_resource, dict) or not isinstance(existing_resource, dict):
        logger.error(f"Invalid resource types: new={type(new_resource)}, existing={type(existing_resource)}")
        return {"percentage": 0.0, "error": "Invalid input types"}

    score = 0.0
    total_checks = 0
    weights = {
        "ram": 0.25,
        "storage_capacity": 0.25,
        "storage_type": 0.15,
        "os_compatibility": 0.1,
        "write_access": 0.1,
        "gpu_name": 0.1,
        "gpu_memory": 0.05
    }

    try:
        # --- RAM Comparison ---
        total_checks += 1
        try:
            new_ram = parse_memory_usage(new_resource.get("memory_usage", ""))
            existing_ram = normalize_memory_value(existing_resource.get("ram", "0"))
            ram_diff_percent = abs(new_ram - existing_ram) / max(new_ram, existing_ram) if max(new_ram, existing_ram) > 0 else 1.0
            ram_score = max(0, 1 - (ram_diff_percent / 0.05)) if ram_diff_percent < 0.1 else 0.0  # 5% tolerance
            score += ram_score * weights["ram"]
            logger.debug(f"RAM: new={new_ram:.2f}GB, existing={existing_ram:.2f}GB, score={ram_score:.2f}")
        except (ValueError, TypeError) as e:
            logger.error(f"Error comparing RAM: {e}")
            score += 0.0 * weights["ram"]

        # --- Storage Capacity Comparison ---
        total_checks += 1
        try:
            new_storage = parse_disk_space(new_resource.get("disk_space", ""))
            existing_storage = normalize_storage_capacity(existing_resource.get("storage", {}).get("capacity", "0"))
            storage_diff_percent = abs(new_storage - existing_storage) / max(new_storage, existing_storage) if max(new_storage, existing_storage) > 0 else 1.0
            storage_score = max(0, 1 - (storage_diff_percent / 0.05)) if storage_diff_percent < 0.1 else 0.0  # 5% tolerance
            score += storage_score * weights["storage_capacity"]
            logger.debug(f"Storage: new={new_storage:.2f}GB, existing={existing_storage:.2f}GB, score={storage_score:.2f}")
        except (ValueError, TypeError) as e:
            logger.error(f"Error comparing storage capacity: {e}")
            score += 0.0 * weights["storage_capacity"]

        # --- Storage Type Comparison ---
        total_checks += 1
        try:
            existing_type = existing_resource.get("storage", {}).get("type", "").lower()
            new_is_nvme = "nvme" in new_resource.get("disk_space", "").lower()
            storage_type_score = 1.0 if existing_type == "ssd" and new_is_nvme else 0.0
            score += storage_type_score * weights["storage_type"]
            logger.debug(f"Storage Type: existing={existing_type}, new_is_nvme={new_is_nvme}, score={storage_type_score:.2f}")
        except Exception as e:
            logger.error(f"Error comparing storage type: {e}")
            score += 0.0 * weights["storage_type"]

        # --- OS Compatibility ---
        total_checks += 1
        try:
            new_os = new_resource.get("system_info", "").lower()
            os_score = 1.0 if "ubuntu" in new_os and existing_resource.get("network", {}).get("username") == "ubuntu" else 0.0
            score += os_score * weights["os_compatibility"]
            logger.debug(f"OS: new_contains_ubuntu={'ubuntu' in new_os}, existing_username=ubuntu, score={os_score:.2f}")
        except Exception as e:
            logger.error(f"Error comparing OS: {e}")
            score += 0.0 * weights["os_compatibility"]

        # --- Write Access ---
        total_checks += 1
        try:
            write_score = 1.0 if "Successfully created test file" in new_resource.get("test_file", "") else 0.0
            score += write_score * weights["write_access"]
            logger.debug(f"Write Access: test_file_success={write_score > 0}, score={write_score:.2f}")
        except Exception as e:
            logger.error(f"Error comparing write access: {e}")
            score += 0.0 * weights["write_access"]

        # --- GPU Comparison ---
        new_gpu = get_gpu_specs(new_resource)
        existing_gpu = get_gpu_specs(existing_resource)
        if existing_gpu:  # Only score GPU if expected
            if not new_gpu:
                # Fallback: Infer GPU capability from system context
                is_high_perf = new_ram > 500 and new_storage > 200  # Heuristic for GPU-capable system
                if is_high_perf:
                    total_checks += 1
                    gpu_score = 0.5  # Partial score for likely GPU presence
                    score += gpu_score * weights["gpu_name"]
                    logger.debug(f"GPU: new=no_data, existing={existing_gpu.get('gpu_name', 'Unknown')}, inferred_score={gpu_score:.2f}")
            else:
                # GPU Name Comparison
                total_checks += 1
                try:
                    new_gpu_name = new_gpu.get("gpu_name", "").lower()
                    existing_gpu_name = existing_gpu.get("gpu_name", "").lower()
                    gpu_name_score = (
                        1.0 if new_gpu_name == existing_gpu_name
                        else 0.5 if ("nvidia" in new_gpu_name and "nvidia" in existing_gpu_name)
                        else 0.0
                    )
                    score += gpu_name_score * weights["gpu_name"]
                    logger.debug(f"GPU Name: new={new_gpu_name}, existing={existing_gpu_name}, score={gpu_name_score:.2f}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error comparing GPU name: {e}")
                    score += 0.0 * weights["gpu_name"]

                # GPU Memory Comparison
                total_checks += 1
                try:
                    new_memory = normalize_memory_value(get_gpu_memory(new_gpu))
                    existing_memory = normalize_memory_value(get_gpu_memory(existing_gpu))
                    memory_diff = abs(new_memory - existing_memory) / max(new_memory, existing_memory) if max(new_memory, existing_memory) > 0 else 1.0
                    gpu_memory_score = max(0, 1 - (memory_diff / 0.05)) if memory_diff < 0.1 else 0.0  # 5% tolerance
                    score += gpu_memory_score * weights["gpu_memory"]
                    logger.debug(f"GPU Memory: new={new_memory:.2f}GB, existing={existing_memory:.2f}GB, score={gpu_memory_score:.2f}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error comparing GPU memory: {e}")
                    score += 0.0 * weights["gpu_memory"]

        # --- CPU Comparison ---
        new_cpu = parse_cpu_info(new_resource.get("cpu_info", "") or new_resource.get("system_info", ""))
        existing_cpu = existing_resource.get("cpu_specs", {}) or {}
        if existing_cpu or new_cpu:
            total_checks += 1
            try:
                new_arch = new_cpu.get("architecture", "").lower()
                existing_arch = existing_cpu.get("architecture", "").lower()
                cpu_score = 1.0 if new_arch == existing_arch and new_arch else 0.5 if new_arch in ["x86_64", "amd64"] else 0.0
                score += cpu_score * weights.get("cpu", 0.1)
                logger.debug(f"CPU: new_arch={new_arch}, existing_arch={existing_arch}, score={cpu_score:.2f}")
            except Exception as e:
                logger.error(f"Error comparing CPU: {e}")
                score += 0.0 * weights.get("cpu", 0.1)

        # Calculate percentage
        total_weight = sum(w for k, w in weights.items() if k in ["ram", "storage_capacity", "storage_type", "os_compatibility", "write_access"] or (k == "cpu" and (existing_cpu or new_cpu)) or (k in ["gpu_name", "gpu_memory"] and existing_gpu))
        percentage = (score / total_weight) * 100 if total_weight > 0 else 0.0
        result = {"percentage": percentage}
        logger.info(f"Comparison complete: percentage={percentage:.2f}%")
        return result

    except Exception as e:
        logger.error(f"Unexpected error in compute resource comparison: {e}")
        return {"percentage": 0.0, "error": str(e)}

def verify_compute_resources(new_resource, existing_resources, min_match_threshold=70.0):
    """
    Verify if a newly detected compute resource matches any in the existing collection.
    
    Args:
        new_resource (dict): The newly detected compute resource specs
        existing_resources (list): List of existing compute resources to compare against
        min_match_threshold (float): Minimum percentage match required to consider resources equivalent
        
    Returns:
        tuple: (is_match, best_match_id, match_score) - match status, ID of best match (if any), and score
    """
    if not new_resource:
        logger.error("Cannot verify empty compute resource")
        return False, None, 0
        
    if not existing_resources:
        logger.info("No existing resources to compare against - treating as new resource")
        return False, None, 0
    
    # Validate the new resource structure
    required_keys = ["resource_type", "cpu_specs"]
    for key in required_keys:
        if key not in new_resource:
            logger.error(f"New resource missing required key: {key}")
            return False, None, 0
    
    # Initialize tracking variables for best match
    best_match = None
    best_score = 0
    best_percentage = 0
    
    # Compare with each existing resource
    for existing in existing_resources:
        resource_id = existing.get("id", "unknown")
        logger.info(f"Comparing with existing resource ID: {resource_id}")
        
        # Run comparison
        try:
            result = compare_compute_resources(new_resource, existing)
            percentage = result.get("percentage", 0)
            
            logger.info(f"Match percentage with {resource_id}: {percentage:.2f}%")
            
            # Check if this is the best match so far
            if percentage > best_percentage:
                best_percentage = percentage
                best_match = resource_id
                best_score = result.get("score", 0)
        except Exception as e:
            logger.error(f"Error comparing with resource {resource_id}: {e}")
            continue
    
    # Determine if we have a match based on threshold
    is_match = best_percentage >= min_match_threshold
    
    if is_match:
        logger.info(f"Found matching resource: {best_match} with {best_percentage:.2f}% match")
    else:
        if best_match:
            logger.info(f"Best match {best_match} with {best_percentage:.2f}% does not meet threshold of {min_match_threshold}%")
        else:
            logger.info("No matching resources found")
    
    return is_match, best_match, best_score

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
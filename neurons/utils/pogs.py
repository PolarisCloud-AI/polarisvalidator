import json
import re
import logging
from datetime import datetime
import requests

logger = logging.getLogger("remote_access")

SERVER_URL = "https://polaris-test-server.onrender.com"
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
                    "task_results": result.get("specifications", {})
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

def compare_compute_resources(new_resource, existing_resource):
    """
    Compare new compute resource specs with existing ones and calculate a score.
    Enhanced with error handling, validation, and detailed logging.
    """
    print(f"Existing resources {existing_resource}")
    logger.info(f"Starting comparison of compute resources")
    
    # Validate inputs
    if not isinstance(new_resource, dict) or not isinstance(existing_resource, dict):
        logger.error(f"Invalid resource types: new={type(new_resource)}, existing={type(existing_resource)}")
        return {"score": 0, "total_checks": 1, "percentage": 0, "error": "Invalid input types"}
    
    score = 0
    total_checks = 0
    matches = {}  # Track which fields matched for debugging
    comparison_details = {}  # More detailed comparison results
    
    try:
        # --- Resource Type Comparison ---
        total_checks += 1
        new_type = new_resource.get("resource_type", "Unknown")
        existing_type = existing_resource.get("resource_type", "Unknown")
        
        # Consider "CPU" with GPU specs as "GPU" for better matching
        if new_type == "CPU" and new_resource.get("gpu_specs"):
            logger.info("Resource labeled as CPU but has GPU specs - treating as GPU")
            new_type = "GPU"
        if existing_type == "CPU" and existing_resource.get("gpu_specs"):
            logger.info("Resource labeled as CPU but has GPU specs - treating as GPU")
            existing_type = "GPU"
            
        if new_type == existing_type:
            score += 1
            matches["resource_type"] = True
            comparison_details["resource_type"] = {"match": True, "values": [new_type, existing_type]}
        else:
            # Special case: If either has GPUs, partial credit for ability to run GPU workloads
            if (new_resource.get("gpu_specs") and existing_resource.get("gpu_specs")):
                score += 0.5
                matches["resource_type"] = "partial"
                comparison_details["resource_type"] = {
                    "match": "partial", 
                    "values": [new_type, existing_type],
                    "note": "Both have GPU capabilities"
                }
            else:
                matches["resource_type"] = False
                comparison_details["resource_type"] = {"match": False, "values": [new_type, existing_type]}
        
        # --- RAM Comparison ---
        total_checks += 1
        try:
            new_ram = normalize_memory_value(new_resource.get("ram", "0"))
            existing_ram = normalize_memory_value(existing_resource.get("ram", "0"))
            
            # RAM comparison with tolerance
            ram_diff_percent = abs(new_ram - existing_ram) / max(new_ram, existing_ram) if max(new_ram, existing_ram) > 0 else 1.0
            
            if ram_diff_percent < 0.05:  # 5% tolerance - exact match
                score += 1
                matches["ram"] = True
                comparison_details["ram"] = {
                    "match": True, 
                    "values": [new_resource.get("ram"), existing_resource.get("ram")],
                    "normalized": [new_ram, existing_ram],
                    "diff_percent": ram_diff_percent * 100
                }
            elif ram_diff_percent < 0.1:  # 10% tolerance - close match
                score += 0.75
                matches["ram"] = "close"
                comparison_details["ram"] = {
                    "match": "close", 
                    "values": [new_resource.get("ram"), existing_resource.get("ram")],
                    "normalized": [new_ram, existing_ram],
                    "diff_percent": ram_diff_percent * 100
                }
            else:
                matches["ram"] = False
                comparison_details["ram"] = {
                    "match": False, 
                    "values": [new_resource.get("ram"), existing_resource.get("ram")],
                    "normalized": [new_ram, existing_ram],
                    "diff_percent": ram_diff_percent * 100
                }
        except Exception as e:
            logger.error(f"Error comparing RAM: {e}")
            matches["ram"] = "error"
            comparison_details["ram"] = {"match": "error", "error": str(e)}
        
        # --- Storage Comparison ---
        total_checks += 1
        try:
            # Extract capacity values from potentially different structures
            new_storage_obj = new_resource.get("storage", {})
            existing_storage_obj = existing_resource.get("storage", {})
            
            new_capacity = new_storage_obj.get("capacity", "0") if isinstance(new_storage_obj, dict) else "0"
            existing_capacity = existing_storage_obj.get("capacity", "0") if isinstance(existing_storage_obj, dict) else "0"
            
            new_storage_gb = normalize_storage_capacity(new_capacity)
            existing_storage_gb = normalize_storage_capacity(existing_capacity)
            
            storage_diff_percent = abs(new_storage_gb - existing_storage_gb) / max(new_storage_gb, existing_storage_gb) if max(new_storage_gb, existing_storage_gb) > 0 else 1.0
            
            if storage_diff_percent < 0.05:  # 5% tolerance
                score += 1
                matches["storage"] = True
                comparison_details["storage"] = {
                    "match": True, 
                    "values": [new_capacity, existing_capacity],
                    "normalized_gb": [new_storage_gb, existing_storage_gb],
                    "diff_percent": storage_diff_percent * 100
                }
            elif storage_diff_percent < 0.1:  # 10% tolerance
                score += 0.75
                matches["storage"] = "close"
                comparison_details["storage"] = {
                    "match": "close", 
                    "values": [new_capacity, existing_capacity],
                    "normalized_gb": [new_storage_gb, existing_storage_gb],
                    "diff_percent": storage_diff_percent * 100
                }
            else:
                matches["storage"] = False
                comparison_details["storage"] = {
                    "match": False, 
                    "values": [new_capacity, existing_capacity],
                    "normalized_gb": [new_storage_gb, existing_storage_gb],
                    "diff_percent": storage_diff_percent * 100
                }
                
            # Check storage type as a bonus (SSD vs HDD, etc.)
            new_storage_type = new_storage_obj.get("type", "").lower() if isinstance(new_storage_obj, dict) else ""
            existing_storage_type = existing_storage_obj.get("type", "").lower() if isinstance(existing_storage_obj, dict) else ""
            
            if new_storage_type and existing_storage_type and new_storage_type == existing_storage_type:
                score += 0.25  # Bonus for matching storage type
                matches["storage_type"] = True
                comparison_details["storage_type"] = {"match": True, "values": [new_storage_type, existing_storage_type]}
            
        except Exception as e:
            logger.error(f"Error comparing storage: {e}")
            matches["storage"] = "error"
            comparison_details["storage"] = {"match": "error", "error": str(e)}
        
        # --- CPU Comparison ---
        # Safely retrieve CPU specs objects with proper null handling
        new_cpu = new_resource.get("cpu_specs", {}) or {}
        existing_cpu = existing_resource.get("cpu_specs", {}) or {}
        
        # Basic CPU specs comparison (string values)
        cpu_string_specs = ["op_modes", "byte_order", "vendor_id"]
        for key in cpu_string_specs:
            total_checks += 1
            # Use empty dict get to avoid None.get() errors
            new_value = str(new_cpu.get(key, "")).lower() if new_cpu is not None and new_cpu.get(key) is not None else ""
            existing_value = str(existing_cpu.get(key, "")).lower() if existing_cpu is not None and existing_cpu.get(key) is not None else ""
            
            if new_value and existing_value:
                # Direct match
                if new_value == existing_value:
                    score += 1
                    matches[f"cpu_{key}"] = True
                    comparison_details[f"cpu_{key}"] = {"match": True, "values": [new_cpu.get(key), existing_cpu.get(key)]}
                # Partial match (e.g. "GenuineIntel" vs "Intel")
                elif (key == "vendor_id" and 
                     ("intel" in new_value and "intel" in existing_value) or 
                     ("amd" in new_value and "amd" in existing_value)):
                    score += 0.75
                    matches[f"cpu_{key}"] = "partial"
                    comparison_details[f"cpu_{key}"] = {
                        "match": "partial", 
                        "values": [new_cpu.get(key), existing_cpu.get(key)],
                        "note": "Same vendor family"
                    }
                else:
                    matches[f"cpu_{key}"] = False
                    comparison_details[f"cpu_{key}"] = {"match": False, "values": [new_cpu.get(key), existing_cpu.get(key)]}
        
        # CPU name comparison - special handling
        total_checks += 1
        new_cpu_name = str(new_cpu.get("cpu_name", "")).lower() if new_cpu is not None else ""
        existing_cpu_name = str(existing_cpu.get("cpu_name", "")).lower() if existing_cpu is not None else ""
        
        if new_cpu_name and existing_cpu_name:
            # Direct match
            if new_cpu_name == existing_cpu_name:
                score += 1
                matches["cpu_name"] = True
                comparison_details["cpu_name"] = {"match": True, "values": [new_cpu.get("cpu_name"), existing_cpu.get("cpu_name")]}
            # Partial match - same processor family
            elif (("xeon" in new_cpu_name and "xeon" in existing_cpu_name) or
                 ("ryzen" in new_cpu_name and "ryzen" in existing_cpu_name) or
                 ("epyc" in new_cpu_name and "epyc" in existing_cpu_name)):
                score += 0.5
                matches["cpu_name"] = "partial"
                comparison_details["cpu_name"] = {
                    "match": "partial", 
                    "values": [new_cpu.get("cpu_name"), existing_cpu.get("cpu_name")],
                    "note": "Same processor family"
                }
            else:
                matches["cpu_name"] = False
                comparison_details["cpu_name"] = {"match": False, "values": [new_cpu.get("cpu_name"), existing_cpu.get("cpu_name")]}
        
        # CPU numeric specs
        cpu_numeric_specs = {
            "threads_per_core": 0.1,  # Small tolerance - mostly 1 or 2
            "cores_per_socket": 0.3,  # Medium tolerance - can vary somewhat
            "sockets": 0.1,           # Small tolerance - usually 1, 2, or 4
            "total_cpus": 0.5,        # Large tolerance - can vary significantly
            "cpu_max_mhz": 0.2        # Medium tolerance - can vary by generation
        }
        
        for key, tolerance in cpu_numeric_specs.items():
            total_checks += 1
            try:
                # Add null checks to prevent attribute errors
                new_value = None
                existing_value = None
                
                if new_cpu is not None:
                    new_value = new_cpu.get(key)
                if existing_cpu is not None:
                    existing_value = existing_cpu.get(key)
                
                if new_value is not None and existing_value is not None:
                    new_num = float(new_value)
                    existing_num = float(existing_value)
                    
                    # Special case for total_cpus - check if multiples or proportion
                    if key == "total_cpus":
                        # Check if one is a multiple of the other (e.g., dual system)
                        if (new_num > 0 and existing_num > 0 and 
                            (new_num % existing_num < 0.1 or existing_num % new_num < 0.1)):
                            score += 0.75
                            matches[f"cpu_{key}"] = "related"
                            comparison_details[f"cpu_{key}"] = {
                                "match": "related", 
                                "values": [new_value, existing_value],
                                "note": "Proportional CPU counts"
                            }
                        # Check if within tolerance
                        elif abs(new_num - existing_num) / max(new_num, existing_num) < tolerance:
                            score += 1
                            matches[f"cpu_{key}"] = True
                            comparison_details[f"cpu_{key}"] = {"match": True, "values": [new_value, existing_value]}
                        else:
                            matches[f"cpu_{key}"] = False
                            comparison_details[f"cpu_{key}"] = {"match": False, "values": [new_value, existing_value]}
                    else:
                        # For other numeric specs, use standard tolerance comparison
                        if abs(new_num - existing_num) / max(new_num, existing_num) < tolerance:
                            score += 1
                            matches[f"cpu_{key}"] = True
                            comparison_details[f"cpu_{key}"] = {"match": True, "values": [new_value, existing_value]}
                        else:
                            matches[f"cpu_{key}"] = False
                            comparison_details[f"cpu_{key}"] = {"match": False, "values": [new_value, existing_value]}
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.error(f"Error comparing CPU {key}: {e}")
                matches[f"cpu_{key}"] = "error"
                comparison_details[f"cpu_{key}"] = {"match": "error", "error": str(e)}
        
        # --- GPU Comparison ---
        # Use safe helper functions that handle None values
        new_gpu = get_gpu_specs(new_resource) or {}
        existing_gpu = get_gpu_specs(existing_resource) or {}
        
        if new_gpu and existing_gpu:
            # GPU name comparison
            total_checks += 2  # More weight for GPU detection
            
            new_gpu_name = str(new_gpu.get("gpu_name", "")).lower() if new_gpu is not None else ""
            existing_gpu_name = str(existing_gpu.get("gpu_name", "")).lower() if existing_gpu is not None else ""
            
            if new_gpu_name and existing_gpu_name:
                # Exact match
                if new_gpu_name == existing_gpu_name:
                    score += 2  # Double points for exact GPU match
                    matches["gpu_name"] = True
                    comparison_details["gpu_name"] = {"match": True, "values": [new_gpu.get("gpu_name"), existing_gpu.get("gpu_name")]}
                # Same GPU family (RTX, GTX, etc.)
                elif any(gpu_family in new_gpu_name and gpu_family in existing_gpu_name 
                        for gpu_family in ["rtx", "gtx", "tesla", "quadro", "radeon", "vega"]):
                    score += 1
                    matches["gpu_name"] = "family"
                    comparison_details["gpu_name"] = {
                        "match": "family", 
                        "values": [new_gpu.get("gpu_name"), existing_gpu.get("gpu_name")],
                        "note": "Same GPU family"
                    }
                # Same manufacturer
                elif (("nvidia" in new_gpu_name and "nvidia" in existing_gpu_name) or 
                      ("amd" in new_gpu_name and "amd" in existing_gpu_name)):
                    score += 0.5
                    matches["gpu_name"] = "vendor"
                    comparison_details["gpu_name"] = {
                        "match": "vendor", 
                        "values": [new_gpu.get("gpu_name"), existing_gpu.get("gpu_name")],
                        "note": "Same GPU manufacturer"
                    }
                else:
                    matches["gpu_name"] = False
                    comparison_details["gpu_name"] = {"match": False, "values": [new_gpu.get("gpu_name"), existing_gpu.get("gpu_name")]}
            
            # GPU memory comparison
            total_checks += 1
            # Use safe helper function for get_gpu_memory
            try:
                new_memory = normalize_memory_value(get_gpu_memory(new_gpu))
                existing_memory = normalize_memory_value(get_gpu_memory(existing_gpu))
                
                if new_memory > 0 and existing_memory > 0:
                    memory_diff = abs(new_memory - existing_memory) / max(new_memory, existing_memory)
                    
                    if memory_diff < 0.05:  # 5% tolerance
                        score += 1
                        matches["gpu_memory"] = True
                        comparison_details["gpu_memory"] = {
                            "match": True,
                            "values": [get_gpu_memory(new_gpu), get_gpu_memory(existing_gpu)],
                            "normalized": [new_memory, existing_memory]
                        }
                    elif memory_diff < 0.2:  # 20% tolerance
                        score += 0.5
                        matches["gpu_memory"] = "close"
                        comparison_details["gpu_memory"] = {
                            "match": "close",
                            "values": [get_gpu_memory(new_gpu), get_gpu_memory(existing_gpu)],
                            "normalized": [new_memory, existing_memory],
                            "diff_percent": memory_diff * 100
                        }
                    else:
                        matches["gpu_memory"] = False
                        comparison_details["gpu_memory"] = {
                            "match": False,
                            "values": [get_gpu_memory(new_gpu), get_gpu_memory(existing_gpu)],
                            "normalized": [new_memory, existing_memory],
                            "diff_percent": memory_diff * 100
                        }
            except Exception as e:
                logger.error(f"Error comparing GPU memory: {e}")
                matches["gpu_memory"] = "error"
                comparison_details["gpu_memory"] = {"match": "error", "error": str(e)}
        
        # Calculate final weighted score
        raw_score = score
        max_score = total_checks
        percentage = (raw_score / total_checks) * 100 if total_checks > 0 else 0
        
        # Generate detailed summary
        summary = {
            "raw_score": raw_score,
            "total_checks": total_checks,
            "percentage": percentage,
            "matches": matches,
            "details": comparison_details,
            "timestamp": datetime.now().isoformat()
        }
        
        # Log detailed results at debug level
        logger.debug(f"Comparison details: {summary}")
        
        # Return simplified result for general usage
        comparison_result = {
            "score": raw_score,
            "total_checks": total_checks,
            "percentage": percentage
        }
        
        return comparison_result
    
    except Exception as e:
        logger.error(f"Unexpected error in compute resource comparison: {e}", exc_info=True)
        return {
            "score": 0,
            "total_checks": 1,
            "percentage": 0,
            "error": str(e)
        }

def normalize_memory_value(memory_str):
    """
    Convert memory string to GB as float for comparison.
    Handles various formats like '16GB', '16G', '16 GB', '16Gi', '16384MB', 
    '49140 MiB', etc.
    """
    if not memory_str:
        return 0.0
    
    try:
        memory_str = str(memory_str).strip()
        
        # Extract numeric part and convert to float
        numeric_match = re.search(r'(\d+\.?\d*)', memory_str)
        if not numeric_match:
            return 0.0
        
        value = float(numeric_match.group(1))
        
        # Convert to GB based on unit
        unit = memory_str.lower()
        if any(x in unit for x in ['pb', 'pi']):
            return value * 1024 * 1024  # PB to GB
        elif any(x in unit for x in ['tb', 'ti', 't']):
            return value * 1024  # TB to GB
        elif any(x in unit for x in ['gb', 'gi', 'g']):
            return value  # Already in GB
        elif any(x in unit for x in ['mib']):
            return value / 1024 * 1.048576  # MiB to GB (1 MiB = 1.048576 MB)
        elif any(x in unit for x in ['mb', 'mi', 'm']):
            return value / 1024  # MB to GB
        elif any(x in unit for x in ['kb', 'ki', 'k']):
            return value / (1024 * 1024)  # KB to GB
        else:
            # If no unit, assume bytes and convert to GB
            return value / (1024 * 1024 * 1024)
    except Exception as e:
        logger.error(f"Error normalizing memory value '{memory_str}': {e}")
        return 0.0


def normalize_storage_capacity(capacity_str):
    """
    Convert storage capacity string to GB as float for comparison.
    Handles various formats like '500GB', '1TB', '1.8T', etc.
    """
    if not capacity_str:
        return 0.0
    
    try:
        capacity_str = str(capacity_str).strip()
        
        # Extract numeric part and convert to float
        numeric_match = re.search(r'(\d+\.?\d*)', capacity_str)
        if not numeric_match:
            return 0.0
        
        value = float(numeric_match.group(1))
        
        # Convert to GB based on unit
        unit = capacity_str.lower()
        if any(x in unit for x in ['pb', 'pi']):
            return value * 1024 * 1024  # PB to GB
        elif any(x in unit for x in ['tb', 'ti', 't']):
            return value * 1024  # TB to GB
        elif any(x in unit for x in ['gb', 'gi', 'g']):
            return value  # Already in GB
        elif any(x in unit for x in ['mb', 'mi', 'm']):
            return value / 1024  # MB to GB
        else:
            return value  # Assume GB if no unit specified
    except Exception as e:
        logger.error(f"Error normalizing storage capacity '{capacity_str}': {e}")
        return 0.0


def get_gpu_specs(resource_dict):
    """
    Extract GPU specs from resource dictionary, handling different formats.
    Returns standardized GPU spec dictionary or None if no GPU specs found.
    """
    if not resource_dict:
        return None
    
    gpu_specs = resource_dict.get("gpu_specs")
    
    # No GPU specs
    if not gpu_specs:
        return None
        
    # Handle list of GPU specs (take first one for comparison)
    if isinstance(gpu_specs, list):
        if len(gpu_specs) > 0:
            return gpu_specs[0]
        return None
    
    # If already a dictionary, return as is
    if isinstance(gpu_specs, dict):
        return gpu_specs
    
    # Unexpected format
    logger.warning(f"Unexpected GPU specs format: {type(gpu_specs)}")
    return None


def get_gpu_memory(gpu_specs):
    """
    Extract GPU memory from GPU specs, handling different key naming conventions.
    Returns memory as string or empty string if not found.
    """
    if not gpu_specs or not isinstance(gpu_specs, dict):
        return ""
    
    # Try different possible keys for GPU memory
    memory_keys = ["memory_total", "memory_size", "vram", "memory"]
    
    for key in memory_keys:
        if key in gpu_specs and gpu_specs[key]:
            return str(gpu_specs[key])
    
    return ""

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

def compute_resource_score(resource):
    """
    Calculate a score for a compute resource (CPU or GPU) based on its specifications.
    Robust to different key naming conventions in input data.

    Parameters:
    resource (dict or list): A dictionary containing compute resource details, or a list of such dictionaries.

    Returns:
    float or list: A score representing the performance of the resource, or a list of scores if a list is provided.
    """

    if isinstance(resource, list):
        # If the input is a list, calculate the score for each resource
        return [compute_resource_score(item) for item in resource]

    if not isinstance(resource, dict):
        raise TypeError("Expected 'resource' to be a dictionary or a list of dictionaries, but got type: {}".format(type(resource)))

    if "resource_type" not in resource:
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
        cpu_specs = resource.get("cpu_specs", {})
        ram = resource.get("ram", "0GB")
        storage = resource.get("storage", {})

        # Convert RAM and storage speed to numeric values
        try:
            ram = float(ram.replace("GB", ""))
        except (ValueError, AttributeError):
            # Handle if ram is already a number or None
            if isinstance(ram, (int, float)):
                pass  # Keep as is
            else:
                ram = 0  # Default to 0 if RAM is invalid

        storage_speed = storage.get("read_speed", "0MB/s")
        try:
            storage_speed = float(storage_speed.replace("MB/s", ""))
        except (ValueError, AttributeError):
            # Handle if storage_speed is already a number or None
            if isinstance(storage_speed, (int, float)):
                pass  # Keep as is
            else:
                storage_speed = 0  # Default to 0 if storage speed is invalid

        # Normalize CPU values for scoring
        cores_score = cpu_specs.get("total_cpus", cpu_specs.get("cores", 0)) / 64  # Assuming max 64 cores
        threads_score = cpu_specs.get("threads_per_core", 0) / 2  # Assuming max 2 threads/core
        clock_speed_score = cpu_specs.get("cpu_max_mhz", cpu_specs.get("clock_speed", 0)) / 5000  # Assuming max 5 GHz
        ram_score = ram / 128  # Assuming max 128GB RAM
        storage_score = storage_speed / 1000  # Assuming max 1000MB/s

        # Weighted score for CPU
        score += (
            cores_score * weights["cpu"]["cores"] +
            threads_score * weights["cpu"]["threads_per_core"] +
            clock_speed_score * weights["cpu"]["max_clock_speed"] +
            ram_score * weights["cpu"]["ram"] +
            storage_score * weights["cpu"]["storage_speed"] 
        )

    elif resource["resource_type"] == "GPU":
        gpu_specs = resource.get("gpu_specs", {})
        if isinstance(gpu_specs, list) and len(gpu_specs) > 0:
            gpu_specs = gpu_specs[0]  # Take the first GPU if there are multiple

        # Handle different possible VRAM key names
        vram = gpu_specs.get("memory_total", 
                    gpu_specs.get("memory_size", 
                        gpu_specs.get("vram", "0GB")))
        
        # Handle as string with unit or as direct number
        try:
            if isinstance(vram, str):
                # Handle different unit formats (GB, GiB, etc.)
                vram_str = vram.upper()
                if "GB" in vram_str:
                    vram = float(vram_str.replace("GB", ""))
                elif "GIB" in vram_str:
                    vram = float(vram_str.replace("GIB", ""))
                else:
                    # Try to extract the numeric part
                    vram = float(''.join(c for c in vram_str if c.isdigit() or c == '.'))
            elif not isinstance(vram, (int, float)):
                vram = 0
        except (ValueError, AttributeError):
            vram = 0  # Default to 0 if VRAM is invalid

        # Handle different possible compute cores key names
        compute_cores = gpu_specs.get("compute_cores", 
                           gpu_specs.get("cuda_cores", 
                               gpu_specs.get("cores", 0)))

        # Handle different possible bandwidth key names
        bandwidth = gpu_specs.get("bandwidth", 
                      gpu_specs.get("memory_bandwidth", "0GB/s"))
        
        # Handle bandwidth as string with unit or as direct number
        try:
            if isinstance(bandwidth, str):
                bandwidth_str = bandwidth.upper()
                if "GB/S" in bandwidth_str:
                    bandwidth = float(bandwidth_str.replace("GB/S", ""))
                else:
                    # Try to extract the numeric part
                    bandwidth = float(''.join(c for c in bandwidth_str if c.isdigit() or c == '.'))
            elif not isinstance(bandwidth, (int, float)):
                bandwidth = 0
        except (ValueError, AttributeError):
            bandwidth = 0  # Default to 0 if bandwidth is invalid

        # Normalize GPU values for scoring
        vram_score = vram / 48  # Assuming max 48GB VRAM
        compute_cores_score = compute_cores / 10000  # Assuming max 10k cores
        bandwidth_score = bandwidth / 1000  # Assuming max 1 TB/s

        # Weighted score for GPU
        score += (
            vram_score * weights["gpu"]["vram"] +
            compute_cores_score * weights["gpu"]["compute_cores"] +
            bandwidth_score * weights["gpu"]["bandwidth"]
        )

    else:
        raise ValueError(f"Unknown resource type: {resource['resource_type']}")

    return round(score, 3)


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
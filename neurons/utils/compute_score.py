from typing import List, Callable, Dict, Any,Tuple
from loguru import logger
import math 
from constant import get_gpu_weight
from pogs import execute_ssh_tasks


MAX_CPU_ONLY_SCORE = 100.0  # Maximum score for CPU-only systems
CPU_ONLY_SPEED_REFERENCE = 4.0  # Reference CPU speed in GHz
DEFAULT_CPU_SPEED_GHZ = 2.5  # Fallback speed for missing clock data

# Configuration constants for GPU pipeline
MAX_COMPUTE_SCORE = 150.0  # Maximum score for GPU systems (higher to reflect greater value)
CPU_SCORE_WEIGHT = 0.3     # CPU contributes 30% to GPU system score
GPU_SCORE_WEIGHT = 0.7     # GPU contributes 70% to GPU system score
MAX_CPU_SCORE = 45.0       # Maximum raw CPU score for GPU systems
MAX_GPU_SCORE = 105.0      # Maximum raw GPU score for GPU systems
GPU_MEMORY_REFERENCE = 16.0  # Reference GPU memory in GB

def calculate_cpu_only_score(specs: Dict[str, Any]) -> float:
    """
    Calculate compute score for a CPU-only system based on CPU specifications.

    Scores based on core count, threads per core, and clock speed, normalized to 0-100.
    Handles missing or zero clock speeds with model-specific or default estimates.

    Args:
        specs (Dict[str, Any]): System specifications with 'cpu_specs'.
            Expected: cpu_specs with 'total_cpus' (int), 'threads_per_core' (int),
                      'cpu_max_mhz' (int), 'cpu_name' (str).

    Returns:
        float: Compute score between 0 and 100, or 0.0 if calculation fails.
    """
    try:
        cpu_specs = specs.get("cpu_specs", {})
        if not cpu_specs:
            logger.warning("No CPU specs provided, returning 0")
            return 0.0

        try:
            cpu_count = int(cpu_specs.get("total_cpus", 0))
            threads_per_core = int(cpu_specs.get("threads_per_core", 1))
            cpu_speed_mhz = float(cpu_specs.get("cpu_max_mhz", 0))
            cpu_name = cpu_specs.get("cpu_name", "").lower()

            # Handle missing or zero clock speed
            if cpu_speed_mhz <= 0:
                if "broadwell" in cpu_name:
                    cpu_speed_ghz = 3.0  # Typical for Broadwell server CPUs
                    logger.info(f"Estimated CPU speed for Broadwell: {cpu_speed_ghz} GHz")
                elif "ryzen" in cpu_name:
                    cpu_speed_ghz = 3.6  # Typical for Ryzen
                    logger.info(f"Estimated CPU speed for Ryzen: {cpu_speed_ghz} GHz")
                else:
                    cpu_speed_ghz = DEFAULT_CPU_SPEED_GHZ
                    logger.info(f"Using default CPU speed: {cpu_speed_ghz} GHz")
            else:
                cpu_speed_ghz = cpu_speed_mhz / 1000.0

            # Logarithmic scaling for CPU cores with thread adjustment
            log_cpu_count = math.log2(max(cpu_count, 1)) * max(threads_per_core, 1)
            
            # CPU score: Combine core count, threads, and speed
            cpu_score = log_cpu_count * (cpu_speed_ghz / CPU_ONLY_SPEED_REFERENCE)
            cpu_score = min(MAX_CPU_ONLY_SCORE, cpu_score * 20.0)  # Scale and cap
            logger.debug(f"CPU-only score: {cpu_score:.2f} (cores={cpu_count}, threads/core={threads_per_core}, speed={cpu_speed_ghz:.2f} GHz)")
            return cpu_score

        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating CPU-only score: {e}")
            return 0.0

    except Exception as e:
        logger.error(f"Error in CPU-only pipeline: {e}")
        return 0.0

def calculate_gpu_only_score(specs: Dict[str, Any]) -> float:
    """
    Calculate the GPU-only score for a system based on GPU specifications.

    Scores based on GPU memory and weight from gpu_specs.py, normalized to 0-105.
    Used in GPU pipeline to avoid double-counting CPU contributions.

    Args:
        specs (Dict[str, Any]): System specifications with 'gpu_specs'.
            Expected: gpu_specs as list with 'gpu_name', 'memory_total' (str, in MiB).

    Returns:
        float: GPU score between 0 and 105, or 0.0 if calculation fails.
    """
    try:
        gpu_specs = specs.get("gpu_specs", [])
        if not gpu_specs or gpu_specs is None:
            logger.warning("No GPU specs provided, GPU score will be 0")
            return 0.0

        try:
            total_gpu_score = 0.0
            for gpu in gpu_specs:
                gpu_name = gpu.get("gpu_name", "")
                memory_mib = gpu.get("memory_total", "0 MiB")
                
                # Parse memory
                try:
                    memory_value = float(memory_mib.split()[0])
                    memory_unit = memory_mib.split()[1].lower() if len(memory_mib.split()) > 1 else "mib"
                    memory_gb = memory_value / 1024.0 if memory_unit == "mib" else memory_value
                except (ValueError, IndexError):
                    logger.warning(f"Invalid GPU memory format for {gpu_name}: {memory_mib}")
                    memory_gb = 0.0

                # Get GPU weight
                gpu_weight = get_gpu_weight(gpu_name)
                if gpu_weight == 0.0:
                    logger.warning(f"No weight found for GPU: {gpu_name}")
                    continue

                # GPU score
                gpu_score_single = (memory_gb / GPU_MEMORY_REFERENCE) * gpu_weight * 150.0
                total_gpu_score += gpu_score_single
                logger.debug(f"GPU score for {gpu_name}: {gpu_score_single:.2f} (memory={memory_gb:.2f} GB, weight={gpu_weight:.2f})")

            gpu_score = min(MAX_GPU_SCORE, total_gpu_score)
            logger.debug(f"Total GPU score: {gpu_score:.2f}")
            return gpu_score

        except Exception as e:
            logger.error(f"Error calculating GPU-only score: {e}")
            return 0.0

    except Exception as e:
        logger.error(f"Error in GPU-only pipeline: {e}")
        return 0.0

def calculate_compute_score(specs: Dict[str, Any]) -> float:
    """
    Calculate compute score by directing to the appropriate pipeline based on resource_type.

    - For 'CPU': Uses calculate_cpu_only_score, GPU score is 0.
    - For 'GPU': Combines calculate_cpu_only_score and calculate_gpu_only_score with 30% CPU and 70% GPU weighting.
    - For invalid/empty/None specs or resource_type: Returns 0.

    Args:
        specs (Dict[str, Any]): System specifications with 'resource_type', 'cpu_specs', 'gpu_specs'.

    Returns:
        float: Compute score (0-100 for CPU-only, 0-150 for GPU systems), or 0.0 if invalid.
    """
    try:
        if not specs or specs is None:
            logger.error("Empty or None specs provided")
            return 0.0

        resource_type = specs.get("resource_type", "").upper()
        if not resource_type:
            logger.error("No resource_type specified")
            return 0.0

        if resource_type == "CPU":
            logger.info("Using CPU-only pipeline with GPU score set to 0")
            cpu_score = calculate_cpu_only_score(specs)
            logger.info(f"Final compute score: {cpu_score:.2f} (CPU: {cpu_score:.2f}, GPU: 0.00)")
            return float(cpu_score)
        elif resource_type == "GPU":
            logger.info("Using both CPU and GPU pipelines for GPU system")
            cpu_score = calculate_cpu_only_score(specs)
            gpu_score = calculate_gpu_only_score(specs)
            
            # Scale CPU score to GPU pipeline max and apply weighting
            scaled_cpu_score = min(MAX_CPU_SCORE, cpu_score * (MAX_CPU_SCORE / MAX_CPU_ONLY_SCORE))
            weighted_cpu_score = scaled_cpu_score * CPU_SCORE_WEIGHT
            weighted_gpu_score = gpu_score * GPU_SCORE_WEIGHT
            
            total_score = weighted_cpu_score + weighted_gpu_score
            total_score = min(MAX_COMPUTE_SCORE, max(0.0, total_score))
            logger.info(f"Final compute score: {total_score:.2f} (CPU: {weighted_cpu_score:.2f}, GPU: {weighted_gpu_score:.2f})")
            return float(total_score)
        else:
            logger.error(f"Invalid resource_type: {resource_type}")
            return 0.0

    except Exception as e:
        logger.error(f"Error determining pipeline: {e}")
        return 0.0
    

# miner_id= "0sy5sozr8YlBQGYU0OuV"
# # miner_id = "3APsdH6RIYoiyd9JYbTS"
# # miner_id="1wEnm0ZcnWF3JuW355NT"

# result = execute_ssh_tasks(miner_id)
# specs = result.get("task_results", {})
# score = calculate_compute_score(specs=specs)

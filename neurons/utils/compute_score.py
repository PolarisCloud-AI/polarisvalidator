from typing import List, Callable, Dict, Any,Tuple
from neurons.utils.gpu_specs import get_gpu_weight
from loguru import logger
import math
import re
    
MAX_CPU_ONLY_SCORE = 60.0
CPU_ONLY_SPEED_REFERENCE = 4.0
DEFAULT_CPU_SPEED_GHZ = 2.5
GPU_MEMORY_REFERENCE = 8.0  # Reference memory in GB
MAX_GPU_SCORE = 105  # Maximum GPU score
MAX_COMPUTE_SCORE = 150.0
CPU_SCORE_WEIGHT = 0.4
GPU_SCORE_WEIGHT = 0.6
MAX_CPU_SCORE = 60.0


def parse_cpu_specs(specs: Dict[str, Any]) -> Dict[str, Any]:
    cpu_specs = {
        "total_cpus": 0,
        "threads_per_core": 1,
        "cpu_max_mhz": 0,
        "cpu_name": ""
    }
    try:
        cpu_specs["cpu_name"] = specs.get("cpu_model", specs.get("system_info", "").strip().split()[-1] or "unknown")
        cpu_specs["total_cpus"] = specs.get("cpu_cores", 0)
        cpu_specs["cpu_max_mhz"] = specs.get("cpu_speed_mhz", 0)
        cpu_specs["threads_per_core"] = specs.get("threads_per_core", 1)
        if cpu_specs["total_cpus"] == 0:
            memory_usage = specs.get("memory_usage", "").strip()
            mem_match = re.search(r"Mem:\s+(\d+)", memory_usage)
            if mem_match:
                total_memory_mb = int(mem_match.group(1))
                cpu_specs["total_cpus"] = max(1, total_memory_mb // 4096)
                logger.debug(f"Estimated CPU cores: {cpu_specs['total_cpus']} based on {total_memory_mb} MB RAM")
        if cpu_specs["cpu_max_mhz"] == 0:
            cpu_name_lower = cpu_specs["cpu_name"].lower()
            if "broadwell" in cpu_name_lower:
                cpu_specs["cpu_max_mhz"] = 3000
            elif "ryzen" in cpu_name_lower:
                cpu_specs["cpu_max_mhz"] = 3600
            elif "intel" in cpu_name_lower:
                cpu_specs["cpu_max_mhz"] = 4000  # Generic modern Intel
            else:
                cpu_specs["cpu_max_mhz"] = DEFAULT_CPU_SPEED_GHZ * 1000
        logger.debug(f"Parsed CPU specs: {cpu_specs}")
        return cpu_specs
    except Exception as e:
        logger.error(f"Error parsing CPU specs: {e}")
        return cpu_specs

def calculate_cpu_only_score(specs: Dict[str, Any]) -> float:
    try:
        cpu_specs = parse_cpu_specs(specs)
        if not cpu_specs or not cpu_specs.get("total_cpus"):
            logger.warning("No valid CPU specs parsed, returning 0")
            return 0.0
        cpu_count = int(cpu_specs.get("total_cpus", 0))
        threads_per_core = int(cpu_specs.get("threads_per_core", 1))
        cpu_speed_mhz = float(cpu_specs.get("cpu_max_mhz", 0))
        cpu_name = (cpu_specs.get("cpu_name") or "unknown").lower()
        cpu_speed_ghz = cpu_speed_mhz / 1000.0 if cpu_speed_mhz > 0 else DEFAULT_CPU_SPEED_GHZ
        log_cpu_count = math.log2(max(cpu_count, 1)) * max(threads_per_core, 1)
        cpu_score = log_cpu_count * (cpu_speed_ghz / CPU_ONLY_SPEED_REFERENCE) * 25.0
        cpu_score = min(MAX_CPU_ONLY_SCORE, cpu_score)
        logger.debug(f"CPU-only score: {cpu_score:.2f} (cores={cpu_count}, threads/core={threads_per_core}, speed={cpu_speed_ghz:.2f} GHz)")
        return cpu_score
    except Exception as e:
        logger.error(f"Error in CPU-only pipeline: {e}")
        return 0.0


def calculate_gpu_only_score(specs: Dict[str, Any]) -> float:
    try:
        is_gpu_present = specs.get("is_gpu_present", False)
        if not is_gpu_present:
            logger.warning("No GPU present, GPU score will be 0")
            return 0.0
        gpu_name = specs.get("gpu_name", "")
        gpu_count = specs.get("gpu_count", 0)
        if not gpu_name or gpu_count == 0:
            logger.warning("GPU name or count missing, GPU score will be 0")
            return 0.0
        gpu_weight = get_gpu_weight(gpu_name)
        if gpu_weight == 0.0:
            logger.warning(f"No weight found for GPU: {gpu_name}")
            return 0.0
        memory_mib_str = specs.get("memory_total", "8192 MiB")
        try:
            memory_value = float(memory_mib_str.split()[0])
            memory_unit = memory_mib_str.split()[1].lower() if len(memory_mib_str.split()) > 1 else "mib"
            memory_gb = memory_value / 1024.0 if memory_unit == "mib" else memory_value
        except (ValueError, IndexError):
            logger.warning(f"Invalid GPU memory format: {memory_mib_str}")
            memory_gb = 8.0
        gpu_score_single = (memory_gb / GPU_MEMORY_REFERENCE) * gpu_weight * 150.0
        logger.debug(f"GPU score for {gpu_name}: {gpu_score_single:.2f} (memory={memory_gb:.2f} GB, weight={gpu_weight:.2f})")
        total_gpu_score = gpu_score_single * gpu_count
        gpu_score = min(MAX_GPU_SCORE, total_gpu_score)
        logger.debug(f"Total GPU score: {gpu_score:.2f}")
        return gpu_score
    except Exception as e:
        logger.error(f"Error in GPU-only pipeline: {e}")
        return 0.0

def calculate_compute_score(resource_type: str, specs: Dict[str, Any]) -> float:
    try:
        if not specs or specs is None:
            logger.error("Empty or None specs provided")
            return 0.0
        is_gpu_present = specs.get("is_gpu_present", False) and specs.get("gpu_name") and specs.get("gpu_count", 0) > 0
        resource_type = "GPU" if is_gpu_present else "CPU"
        if resource_type == "CPU":
            logger.info("Using CPU-only pipeline with GPU score set to 0")
            cpu_score = calculate_cpu_only_score(specs)
            logger.info(f"Final compute score: {cpu_score:.2f} (CPU: {cpu_score:.2f}, GPU: 0.00)")
            return float(cpu_score)
        elif resource_type == "GPU":
            logger.info("Using both CPU and GPU pipelines for GPU system")
            cpu_score = calculate_cpu_only_score(specs)
            gpu_score = calculate_gpu_only_score(specs)
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
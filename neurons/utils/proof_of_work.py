import os
import paramiko
from fastapi import HTTPException
import asyncio
import logging
import re
from typing import Dict, Any
import json
logger = logging.getLogger(__name__)
logging.getLogger("websockets.client").setLevel(logging.WARNING)

CPU_BENCHMARKS = {
    "intel": {
        "i9": 95, "i9-14900k": 99, "i9-13900k": 98, "i9-12900k": 96, "i9-11900k": 90, "i9-10900k": 85,
        "i7": 85, "i7-14700k": 92, "i7-13700k": 90, "i7-12700k": 88, "i7-11700k": 84, "i7-10700k": 80,
        "i5": 70, "i5-14600k": 78, "i5-13600k": 76, "i5-12600k": 74, "i5-12400f": 72, "i5-13400f": 75,
        "i3": 50, "i3-13100f": 58, "i3-12100f": 55, "i3-10100f": 50,
        "xeon": 90, "xeon w-3375": 94, "xeon w-3175x": 92, "xeon silver 4310": 80, "xeon gold 6338": 88, "xeon platinum 8380": 95,
        "core ultra 7 165h": 82, "core ultra 5 125h": 70, "i7-9750h": 65, "i5-1135g7": 60,
        "celeron": 30, "celeron g6900": 35, "pentium": 35, "pentium gold g7400": 40,
        "core 2 duo": 20, "core 2 quad": 25
    },
    "amd": {
        "ryzen 9": 90, "ryzen 9 9950x": 99, "ryzen 9 9900x": 97, "ryzen 9 7950x3d": 98, "ryzen 9 7950x": 96, "ryzen 9 5950x": 94, "ryzen 9 5900x": 92,
        "ryzen 7": 80, "ryzen 7 9800x3d": 93, "ryzen 7 9700x": 88, "ryzen 7 7700x": 85, "ryzen 7 5800x3d": 87, "ryzen 7 5800x": 84, "ryzen 7 2700x": 60,
        "ryzen 5": 65, "ryzen 5 9600x": 75, "ryzen 5 7600x": 72, "ryzen 5 5600x": 70, "ryzen 5 3600": 65, "ryzen 5 2600": 55,
        "ryzen 3": 45, "ryzen 3 5300g": 50, "ryzen 3 3300x": 48,
        "epyc": 95, "epyc 7763": 98, "epyc 7542": 65, "epyc 7313": 85,
        "threadripper": 100, "threadripper 7970x": 99, "threadripper 5975wx": 97,
        "ryzen ai 9 hx 370": 90, "ryzen ai max+ 395": 92, "ryzen 7 7840hs": 80, "ryzen 5 7640u": 68,
        "athlon": 30, "fx-8350": 40
    },
    "arm": {
        "cortex-a78": 40, "cortex-a76": 35, "cortex-a55": 25, "cortex-x4": 50, "cortex-x3": 45, "cortex-a720": 42,
        "apple m": 85, "apple m1": 85, "apple m1 pro": 87, "apple m1 max": 88, "apple m2": 88, "apple m2 pro": 90, "apple m2 max": 91, "apple m3": 90, "apple m3 pro": 92, "apple m3 max": 93, "apple m4": 94,
        "snapdragon x elite": 87, "snapdragon x plus": 84, "snapdragon 8 gen 3": 83, "snapdragon 8 gen 2": 80, "snapdragon 7 gen 1": 60,
        "mediatek dimensity 9300": 82, "samsung exynos 2400": 80
    }
}

GPU_BENCHMARKS = {
    "nvidia": {
        "rtx 5090": 510, "rtx 5080": 460, "rtx 5070 ti": 400, "rtx 5070": 360, "rtx 5060 ti": 300, "rtx 5060": 260,
        "rtx 4090": 480, "rtx 4080": 380, "rtx 4070 ti super": 340, "rtx 4070": 300, "rtx 4060 ti": 260, "rtx 4060": 240,
        "rtx 3090 ti": 410, "rtx 3090": 400, "rtx 3080 ti": 360, "rtx 3080": 340, "rtx 3070 ti": 290, "rtx 3070": 280, "rtx 3060 ti": 250, "rtx 3060": 200,
        "rtx 2060": 160, "gtx 1660 super": 140, "gtx 1650": 130, "gtx 1080 ti": 190, "gtx 1080": 180, "gtx 1070": 140, "gtx 980 ti": 120, "gtx 970": 100,
        "tesla": 350, "tesla t4": 120, "a100": 500, "h100": 510, "v100": 450,
        "quadro": 250, "quadro rtx 8000": 350, "quadro rtx 6000": 320, "quadro t1000": 150,
        "rtx 4080 mobile": 320, "rtx 4070 mobile": 280, "rtx 4060 mobile": 220
    },
    "amd": {
        "rx 9070 xt": 400, "rx 9070": 360, "rx 9060 xt": 300, "rx 9060": 260,
        "rx 7900 xtx": 400, "rx 7900 xt": 380, "rx 7900 gre": 350, "rx 7800 xt": 320, "rx 7700 xt": 260, "rx 7600 xt": 220, "rx 7600": 200,
        "rx 6950 xt": 360, "rx 6900 xt": 350, "rx 6800 xt": 320, "rx 6800": 300, "rx 6700 xt": 260, "rx 6700": 240, "rx 6600 xt": 200, "rx 6600": 180,
        "rx 5700 xt": 170, "rx 580": 120, "vega 64": 150, "vega 56": 140, "r9 390": 110, "r9 290": 100,
        "radeon pro": 200, "radeon pro w7900": 360, "radeon pro w6800": 280,
        "radeon 890m": 160, "radeon 880m": 150, "radeon 780m": 140, "radeon 760m": 120, "radeon vega 8": 100
    },
    "intel": {
        "arc a770": 200, "arc a750": 170, "arc a580": 130, "arc a380": 100, "arc b580": 180, "arc b570": 160,
        "iris xe": 90, "iris plus": 70, "uhd graphics 770": 60, "uhd graphics 630": 50,
        "arc pro a60": 150, "arc pro a40": 120
    },
    "apple": {
        "m1 gpu": 120, "m1 pro gpu": 140, "m1 max gpu": 160, "m2 gpu": 140, "m2 pro gpu": 160, "m2 max gpu": 180,
        "m3 gpu": 160, "m3 pro gpu": 180, "m3 max gpu": 200, "m4 gpu": 200
    },
    "qualcomm": {
        "adreno x1": 130, "adreno 740": 110, "adreno 730": 100, "adreno 660": 90
    }
}

async def execute_ssh_task(hostname: str, port: int, username: str, key_path: str, command: str, timeout: int = 60) -> str:
    """Execute SSH command with reduced timeout for speed."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            key_filename=key_path,
            timeout=3,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        return output if output else f"No output. Stderr: {error}"
    except Exception as e:
        logger.warning(f"SSH task failed: {str(e)[:100]}")
        return f"Error: {type(e).__name__}"
    finally:
        try:
            client.close()
        except:
            pass

def calculate_cpu_score(cpu_model: str, cores: int, threads_per_core: int, speed_mhz: float, ram_mb: int) -> float:
    """Calculate CPU score normalized to 0-1 range."""
    if not cpu_model:
        logger.debug("No CPU model provided, returning default score")
        return 0.0

    cpu_lower = cpu_model.lower()
    base_score = 50  # Default baseline

    # Match against known CPU families
    for vendor, models in CPU_BENCHMARKS.items():
        if vendor in cpu_lower:
            for model, score in models.items():
                if model in cpu_lower:
                    base_score = score
                    logger.debug(f"Matched CPU: vendor={vendor}, model={model}, score={score}")
                    break
            break

    # Apply multipliers
    core_multiplier = min(cores * threads_per_core / 8, 2.0)  # Cap at 2x for diminishing returns
    frequency_multiplier = min((speed_mhz if speed_mhz > 0 else 2000) / 3000, 1.5)  # Fallback to 2000 MHz
    ram_multiplier = min(ram_mb / 16000, 1.3)  # Normalize to 16GB base

    final_score = base_score * core_multiplier * frequency_multiplier * ram_multiplier
    capped_score = min(final_score, 1000)  # Cap at 1000
    logger.debug(f"CPU score calculation: base={base_score}, core_mult={core_multiplier}, freq_mult={frequency_multiplier}, ram_mult={ram_multiplier}, final={capped_score}")

    # Normalize to 0-1 range
    return round(capped_score / 1000, 3)

def calculate_gpu_score(gpu_name: str, gpu_memory_mb: int = None) -> float:
    """Calculate GPU score normalized to 0-1 range."""
    if not gpu_name:
        logger.debug("No GPU name provided, returning default score")
        return 0.0

    gpu_lower = gpu_name.lower()
    base_score = 50  # Default baseline

    # Match against known GPU families
    for vendor, models in GPU_BENCHMARKS.items():
        if vendor in gpu_lower:
            for model, score in models.items():
                if model in gpu_lower:
                    base_score = score
                    logger.debug(f"Matched GPU: vendor={vendor}, model={model}, score={score}")
                    break
            break

    # Apply memory multiplier
    memory_multiplier = 1.0
    if gpu_memory_mb and gpu_memory_mb > 4000:
        memory_multiplier = min(1 + (gpu_memory_mb - 8000) / 16000, 1.25)  # Max 25% boost

    final_score = base_score * memory_multiplier
    capped_score = min(final_score, 500)  # Cap at 500
    logger.debug(f"GPU score calculation: base={base_score}, mem_mult={memory_multiplier}, final={capped_score}")

    # Normalize to 0-1 range
    return round(capped_score / 500, 3)

async def quick_cpu_benchmark(hostname: str, port: int, username: str, key_path: str) -> float:
    """Fast CPU benchmark normalized to 0-1 range."""
    benchmark_cmd = """
    timeout 10s bash -c '
    start=$(date +%s.%N)
    count=0
    while true; do
        result=$((count * count + count / 2))
        count=$((count + 1))
        if [ $count -gt 1000000 ]; then break; fi
    done
    end=$(date +%s.%N)
    echo "ops:$count time:$(echo "$end - $start" | bc -l)"
    ' 2>/dev/null || echo "ops:0 time:10"
    """
    
    result = await execute_ssh_task(hostname, port, username, key_path, benchmark_cmd)
    
    try:
        ops_match = re.search(r'ops:(\d+)', result)
        time_match = re.search(r'time:([\d.]+)', result)
        
        if ops_match and time_match:
            ops = int(ops_match.group(1))
            time_taken = float(time_match.group(1))
            ops_per_second = ops / time_taken if time_taken > 0 else 0
            normalized_score = min(ops_per_second / 1000000, 1.0)
            logger.debug(f"Benchmark: ops={ops}, time={time_taken}, ops/sec={ops_per_second}, score={normalized_score}")
            return round(normalized_score, 3)
    except Exception as e:
        logger.warning(f"Benchmark parsing failed: {str(e)}")
    
    return 0.0

async def perform_ssh_tasks(ssh: str) -> Dict[str, Any]:
    """Perform SSH tasks to gather system info and calculate performance scores."""
    try:
        if not isinstance(ssh, str) or not ssh.strip():
            logger.error("Invalid or missing SSH connection string")
            raise HTTPException(status_code=400, detail="SSH connection string is empty")
        # Parse SSH connection string
        ssh_parts = ssh.replace('ssh://', '').split('@')
        if len(ssh_parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid SSH connection string")
        
        username = ssh_parts[0]
        host_port = ssh_parts[1].split(':')
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 22
        key_path = os.path.join(os.path.dirname(__file__), "ssh_host_key")
        
        if not os.path.exists(key_path):
            raise HTTPException(status_code=500, detail="SSH key not found")
        if os.name != 'nt':
            os.chmod(key_path, 0o600)

        # Define commands
        commands = {
            "system": "uname -m && cat /proc/version | head -1",
            "cpu": "lscpu | grep -E 'Model name|^CPU\\(s\\):|Thread\\(s\\) per core|CPU max MHz|CPU MHz' || cat /proc/cpuinfo | grep 'cpu MHz' | head -1",
            "memory": "free -m | grep '^Mem:' | awk '{print $2}'",
            "gpu_pci": "lspci | grep -Ei 'vga|3d|display' | head -3",
            "gpu_nvidia": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'none'",
            "gpu_amd": "rocm-smi --showproductname --showmeminfo 2>/dev/null | head -5 || echo 'none'"
        }

        task_results = {
            "system_info": "",
            "cpu_model": "",
            "cpu_cores": 0,
            "cpu_speed_mhz": 0,
            "threads_per_core": 1,
            "ram_total_mb": 0,
            "is_gpu_present": False,
            "gpu_name": "",
            "gpu_memory_mb": 0,
            "cpu_score": 0.0,
            "gpu_score": 0.0,
            "benchmark_score": 0.0,
            "total_score": 0.0
        }

        # Execute commands concurrently
        results = await asyncio.gather(*[
            execute_ssh_task(host, port, username, key_path, cmd) 
            for cmd in commands.values()
        ], return_exceptions=True)

        # Parse results
        system_info = results[0] if not isinstance(results[0], Exception) else ""
        cpu_info = results[1] if not isinstance(results[1], Exception) else ""
        memory_info = results[2] if not isinstance(results[2], Exception) else ""
        gpu_pci = results[3] if not isinstance(results[3], Exception) else ""
        gpu_nvidia = results[4] if not isinstance(results[4], Exception) else ""
        gpu_amd = results[5] if not isinstance(results[5], Exception) else ""

        task_results["system_info"] = system_info

        # Parse CPU info
        if cpu_info and "Error:" not in cpu_info:
            for line in cpu_info.splitlines():
                line = line.strip()
                if "Model name" in line:
                    task_results["cpu_model"] = line.split(':', 1)[1].strip()
                elif "CPU(s):" in line and "NUMA" not in line:
                    try:
                        task_results["cpu_cores"] = int(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif "Thread(s) per core" in line:
                    try:
                        task_results["threads_per_core"] = int(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif "CPU max MHz" in line or ("CPU MHz" in line and task_results["cpu_speed_mhz"] == 0):
                    try:
                        task_results["cpu_speed_mhz"] = float(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif "cpu MHz" in line:  # Handle /proc/cpuinfo format
                    try:
                        task_results["cpu_speed_mhz"] = float(line.split(':', 1)[1].strip())
                    except:
                        pass

        # Parse memory
        if memory_info and memory_info.isdigit():
            task_results["ram_total_mb"] = int(memory_info)

        # Parse GPU info
        gpu_detected = False
        if gpu_nvidia and "none" not in gpu_nvidia.lower() and "Error:" not in gpu_nvidia:
            try:
                parts = gpu_nvidia.strip().split(',')
                if len(parts) >= 2:
                    task_results["gpu_name"] = parts[0].strip()
                    task_results["gpu_memory_mb"] = int(parts[1].strip())
                    gpu_detected = True
            except:
                pass
        
        if not gpu_detected and gpu_amd and "none" not in gpu_amd.lower():
            for line in gpu_amd.splitlines():
                if any(term in line.lower() for term in ["radeon", "rx ", "vega"]):
                    task_results["gpu_name"] = line.strip()
                    gpu_detected = True
                    break
        
        if not gpu_detected and gpu_pci:
            for line in gpu_pci.splitlines():
                if any(term in line.lower() for term in ["nvidia", "amd", "intel"]) and \
                   not any(term in line.lower() for term in ["audio", "natoma", "qemu"]):
                    task_results["gpu_name"] = line.split(':')[-1].strip()
                    gpu_detected = True
                    break

        task_results["is_gpu_present"] = gpu_detected

        # Calculate scores
        task_results["cpu_score"] = calculate_cpu_score(
            task_results["cpu_model"],
            task_results["cpu_cores"],
            task_results["threads_per_core"],
            task_results["cpu_speed_mhz"],
            task_results["ram_total_mb"]
        )

        task_results["gpu_score"] = calculate_gpu_score(
            task_results["gpu_name"],
            task_results["gpu_memory_mb"] if task_results["gpu_memory_mb"] > 0 else None
        )

        task_results["benchmark_score"] = await quick_cpu_benchmark(host, port, username, key_path)

        # Calculate total score with fallback
        total_score = (task_results["cpu_score"] * 0.6) + (task_results["gpu_score"] * 0.4)
        if total_score == 0 and task_results["benchmark_score"] > 0:
            total_score = task_results["benchmark_score"]
        task_results["total_score"] = round(total_score, 3)

        return {"task_results": task_results}

    except Exception as e:
        logger.error(f"Benchmarking error: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking failed: {str(e)}")

# Example usage
async def main():
    try:
        data = await perform_ssh_tasks("ssh://root@65.109.22.24:22")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
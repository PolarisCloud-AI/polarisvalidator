import os
import paramiko
from fastapi import HTTPException
import asyncio
import logging
import socket

logger = logging.getLogger(__name__)

async def execute_ssh_task(hostname, port, username, key_path, command, timeout=30):
    """
    Execute a single SSH command and return the result or an error message.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"Connecting to {username}@{hostname}:{port} using public key")
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            key_filename=key_path,
            timeout=10
        )

        logger.info(f"Executing command: {command}")
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()

        if error:
            logger.warning(f"Command stderr: {error}")

        return output if output else f"Command executed but no output returned. Stderr: {error}"

    except paramiko.ssh_exception.NoValidConnectionsError as e:
        logger.error(f"No valid connections to {hostname}:{port} - {str(e)}", exc_info=True)
        return f"ERROR: No valid SSH connections: {str(e)}"

    except paramiko.ssh_exception.AuthenticationException as e:
        logger.error(f"SSH Authentication failed for {username}@{hostname}:{port} - {str(e)}", exc_info=True)
        return "ERROR: SSH Authentication failed"

    except paramiko.SSHException as e:
        logger.error(f"General SSH error for {hostname}:{port} - {str(e)}", exc_info=True)
        return f"ERROR: SSHException - {str(e)}"

    except socket.timeout as e:
        logger.error(f"Connection timed out to {hostname}:{port}", exc_info=True)
        return f"ERROR: SSH connection to {hostname}:{port} timed out"

    except Exception as e:
        logger.error(f"Unexpected error executing SSH task: {str(e)}", exc_info=True)
        return f"ERROR: {str(e)}"

    finally:
        try:
            client.close()
        except Exception:
            pass  # If close fails, it’s already broken.

async def perform_ssh_tasks(ssh: str):
    try:
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
        commands = {
            "system_info": "uname -a",
            "disk_space": "df -h",
            "memory_usage": "free -m",
            "file_listing": "ls -la /tmp",
            "network_connections": "ss -tuln | head -10",
            "gpu_check": "lspci | grep -Ei 'vga|3d' || echo 'No GPU detected'",
            "nvidia_gpu_info": "nvidia-smi --query-gpu=name,count --format=csv || echo 'No NVIDIA GPU detected'",
            "nvidia_gpu_memory": "nvidia-smi --query-gpu=memory.total --format=csv || echo 'No NVIDIA GPU detected'",
            "cpu_info": "lscpu | grep -E 'Model name|CPU\\(s\\):|MHz|Thread\\(s\\) per core' || echo 'No CPU info'"
        }
        task_results = {
            "system_info": "",
            "disk_space": "",
            "memory_usage": "",
            "file_listing": "",
            "network_connections": "",
            "is_gpu_present": False,
            "gpu_name": None,
            "gpu_count": 0,
            "memory_total": None,
            "ram_total_mb": 0,
            "cpu_model": None,
            "cpu_cores": 0,
            "cpu_speed_mhz": 0,
            "threads_per_core": 1
        }
        for task_name, command in commands.items():
            output = await execute_ssh_task(host, port, username, key_path, command)
            if task_name == "gpu_check":
                if "No GPU detected" not in output:
                    for line in output.splitlines():
                        if any(x in line.lower() for x in ["nvidia", "amd", "intel"]):
                            if "natoma" not in line.lower() and "qemu" not in line.lower():  # Exclude false positives
                                task_results["gpu_name"] = line.split(':')[-1].strip()
                                task_results["gpu_count"] = 1
                                break
            elif task_name == "nvidia_gpu_info":
                if "No NVIDIA GPU detected" not in output:
                    try:
                        lines = output.splitlines()
                        if len(lines) > 1:
                            gpu_data = lines[1].split(',')
                            task_results["gpu_name"] = gpu_data[0].strip() if len(gpu_data) > 0 else None
                            task_results["gpu_count"] = int(gpu_data[1].strip()) if len(gpu_data) > 1 else 0
                            task_results["is_gpu_present"] = True
                    except Exception as e:
                        logger.warning(f"Error parsing NVIDIA GPU info: {e}")
                else:
                    task_results["is_gpu_present"] = False
            elif task_name == "nvidia_gpu_memory":
                if "No NVIDIA GPU detected" not in output:
                    try:
                        lines = output.splitlines()
                        if len(lines) > 1:
                            task_results["memory_total"] = lines[1].strip()
                    except Exception as e:
                        logger.warning(f"Error parsing NVIDIA GPU memory: {e}")
            elif task_name == "memory_usage":
                task_results[task_name] = output
                try:
                    for line in output.splitlines():
                        if line.startswith("Mem:"):
                            mem_fields = line.split()
                            task_results["ram_total_mb"] = int(mem_fields[1]) if len(mem_fields) > 1 else 0
                            break
                except Exception as e:
                    logger.warning(f"Error parsing RAM info: {e}")
            elif task_name == "cpu_info":
                if "No CPU info" not in output:
                    try:
                        for line in output.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            if "Model name" in line:
                                task_results["cpu_model"] = line.split(':', 1)[1].strip()
                            elif "CPU(s):" in line and "NUMA" not in line and "per" not in line:
                                task_results["cpu_cores"] = int(line.split(':', 1)[1].strip())
                            elif "Thread(s) per core" in line:
                                task_results["threads_per_core"] = int(line.split(':', 1)[1].strip())
                            elif "CPU max MHz" in line:
                                task_results["cpu_speed_mhz"] = float(line.split(':', 1)[1].strip())
                            elif "CPU MHz" in line and task_results["cpu_speed_mhz"] == 0:
                                task_results["cpu_speed_mhz"] = float(line.split(':', 1)[1].strip())
                    except Exception as e:
                        logger.warning(f"Error parsing CPU info: {e}")
            else:
                task_results[task_name] = output
        return {
            "status": "success",
            "message": "SSH tasks executed successfully",
            "task_results": task_results
        }
    except Exception as e:
        logger.error(f"Error executing SSH tasks")
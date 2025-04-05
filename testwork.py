import json
import logging
import os
import sys
import traceback
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

MINER_ID = "WWmHlBdA9KmiNHt3Hz7x"
SERVER_URL = "https://polaris-test-server.onrender.com"
API_PREFIX = "/api/v1"

#ssh://ubuntu@148.76.188.132:26399

def list_all_miners():
    try:
        url = f"{SERVER_URL}{API_PREFIX}/miners/"
        logger.info(f"Trying to list miners from: {url}")

        try:
            response = requests.get(url)
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                miners = response.json()
                logger.info(f"Success! Found {len(miners)} miners")
                
                for i, miner in enumerate(miners):
                    miner_id = miner.get('id', 'unknown')
                    logger.info(f"Miner #{i+1}: ID = {miner_id}")
                
                return miners
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with endpoint {url}: {str(e)}")
        
        logger.error("Failed to list miners")
        return None
    except Exception as e:
        logger.error(f"Error listing miners: {str(e)}")
        return None

def get_miner_ssh_details(miner_id):
    try:
        url = f"{SERVER_URL}{API_PREFIX}/miners/{miner_id}"
        logger.info(f"Trying to get miner details from: {url}")
        
        try:
            response = requests.get(url)
            
            logger.debug(f"Response status code: {response.status_code}")
            if response.status_code == 200:
                logger.debug(f"Response content: {response.text[:200]}...")
                
                miner_data = response.json()
                logger.info(f"Received miner data for ID: {miner_id}")
                
                if not miner_data.get("compute_resources"):
                    logger.error("Miner has no compute resources")
                    return None
                    
                for resource in miner_data.get("compute_resources", []):
                    if resource.get("network") and resource.get("network", {}).get("ssh"):
                        ssh_string = resource["network"]["ssh"]
                        
                        ssh_parts = ssh_string.replace("ssh://", "").split("@")
                        if len(ssh_parts) != 2:
                            logger.error(f"Invalid SSH connection string: {ssh_string}")
                            continue
                            
                        username = ssh_parts[0]
                        host_port = ssh_parts[1].split(":")
                        hostname = host_port[0]
                        port = int(host_port[1]) if len(host_port) > 1 else 22
                        
                        logger.info(f"Found SSH details: {username}@{hostname}:{port}")
                        return {
                            "hostname": hostname,
                            "port": port,
                            "username": username,
                            "resource_id": resource.get("id")
                        }
                
                logger.error("No SSH connection details found in miner resources")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error with endpoint {url}: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {url}: {str(e)}")
    
        logger.error("Failed to get miner details")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving miner details: {str(e)}")
        traceback.print_exc()
        return None

def execute_ssh_tasks(miner_id):
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

def display_results(result):
    if not result or result.get("status") != "success":
        logger.error(f"Error: {result.get('message') if result else 'No results'}")
        return
        
    logger.info("\n==== SSH Command Results ====")
    task_results = result.get("task_results", {})
    
    logger.info("\n📊 SYSTEM INFORMATION:")
    logger.info(task_results.get("system_info", "Not available"))
    
    logger.info("\n💾 DISK SPACE:")
    logger.info(task_results.get("disk_space", "Not available"))
    
    logger.info("\n🧠 MEMORY USAGE:")
    logger.info(task_results.get("memory_usage", "Not available"))
    
    logger.info("\n📄 FILE LISTING:")
    logger.info(task_results.get("file_listing", "Not available"))
    
    logger.info("\n🌐 NETWORK CONNECTIONS:")
    logger.info(task_results.get("network_connections", "Not available"))

def main():
    logger.info(f"Connecting to miner {MINER_ID} to perform SSH tasks")
    
    miners = list_all_miners()
    if not miners:
        logger.warning("No miners found or couldn't retrieve miner list")
    
    ssh_details = get_miner_ssh_details(MINER_ID)
    if not ssh_details:
        logger.error("Failed to get SSH details for miner")
        return
        
    logger.info(f"Using SSH details: {ssh_details['username']}@{ssh_details['hostname']}:{ssh_details['port']}")
    
    result = execute_ssh_tasks(MINER_ID)
    
    display_results(result)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
    finally:
        logger.info("SSH execution complete")
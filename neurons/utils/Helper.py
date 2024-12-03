import asyncio
import json
import os
import websockets
import sys
import time
import aiohttp
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv    


async def fetch_open_jobs() -> List[str]:
    """
    Fetch open jobs via WebSocket connection with proper error handling and timeouts.
    
    Returns:
        List[str]: List of open job IDs
    """
    load_dotenv()
    base_url = os.getenv('BASE_URL')
    if not base_url:
        print("BASE_URL not set in environment")
        return []

    websocket_url = f"{base_url}/ws/jobs/open"
    open_jobs_list = []
    
    try:
        async with websockets.connect(
            websocket_url,
            ping_timeout=30,
            close_timeout=10,
            max_size=10_485_760  # 10MB max message size
        ) as websocket:
            try:
                # Use asyncio.wait_for to set a timeout
                message = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(message)
                
                if "open_jobs" in data:
                    open_jobs = data["open_jobs"]
                    open_jobs_list = [
                        job["job_id"] 
                        for job in open_jobs 
                        if job.get("status") == "open"
                    ]
                elif "error" in data:
                    print(f"Server error: {data['error']}")
                else:
                    print(f"Unexpected message format: {data}")
                        
            except asyncio.TimeoutError:
                print("Timeout waiting for server response")
                
    except websockets.exceptions.InvalidURI:
        print(f"Invalid WebSocket URL: {websocket_url}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection closed: {e}")
    except Exception as e:
        print(f"Connection error: {str(e)}")
        
    return open_jobs_list

def update_job_status(job_id: str):
    """
    Update the status of a job using a REST API call.

    Args:
        job_id (str): The ID of the job to update.

    Returns:
        dict: Response JSON or error details.
    """
    new_status = "Closed"
    base_url_mode = "https://a9labsapi-1048667232204.us-central1.run.app"
    url = f"{base_url_mode}/jobs/update"

    try:
        response = requests.post(url, data={"status": new_status,"job_id":job_id})
        print("Response status code:", response.status_code)
        print("Response text:", response.text)

        response.raise_for_status()  # Raise error for HTTP 4xx/5xx
        print(f"Job {job_id} status updated to '{new_status}' successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to update job status: {str(e)}")
        return {"error": str(e)}
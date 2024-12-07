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


async def fetch_open_jobs()->List[str]:
    open_jobs_list = []
    try:
        base_url = os.getenv('BASE_URL')
        url = f"{base_url_mode}/jobs/open"
        response = requests.post(url)
        data=response.json()
        if "open_jobs" in data:
            open_jobs = data["open_jobs"]
            open_jobs_list = [job["job_id"] for job in open_jobs  if job.get("status") == "open"]
        elif "error" in data:
            print(f"Server error: {data['error']}")
        else:
            print(f"Unexpected message format: {data}")
        return open_jobs_list
    except:
        print(f"Failed to update job status: {str(e)}")
        open_jobs_list = []

def update_job_status(job_id: str):
    """
    Update the status of a job using a REST API call.

    Args:
        job_id (str): The ID of the job to update.

    Returns:
        dict: Response JSON or error details.
    """
    new_status = "Closed"
    base_url = os.getenv('BASE_URL')
    url = f"{base_url}/jobs/update"

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
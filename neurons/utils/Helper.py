import asyncio
import json
import os
import websockets
import sys
import time
import aiohttp
import requests
from dotenv import load_dotenv
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
             
async def fetch_open_jobs():
    """
    Connect to the WebSocket endpoint and fetch open jobs in a list format.

    Args:
        websocket_url (str): The URL of the WebSocket endpoint.

    Returns:
        list: A list of open jobs.
    """
    websocket_url = f"{BASE_URL}/ws/jobs/open"
    open_jobs_list = []

    try:
        async with websockets.connect(websocket_url) as websocket:
            print("Connected to WebSocket")
            while True:
                message = await websocket.recv()  # Receive message from WebSocket
                data = json.loads(message)
                
                if "open_jobs" in data:
                    open_jobs = data["open_jobs"]
                    open_jobs_list = [job["job_id"] for job in open_jobs if job.get("status") == "open"]
                elif "error" in data:
                    print(f"Error from WebSocket: {data['error']}")
                    break  # Exit the loop on error
                else:
                    print("Unexpected message format")
                
                # Break the loop if you only want to fetch once
                break

    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection closed: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")

    return open_jobs_list

def update_job_status(job_id: str):
    new_status ="Closed"
    Base_URL_1="https://a9labsapi-1048667232204.us-central1.run.app"
    url = f"{Base_URL_1}/jobs/{job_id}"
    try:
        response = requests.put(url, data={"status": new_status})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
#from datetime import datetime, timedelta

# Given timestamp
#timestamp_str = "2025-03-06T02:25:49.125325"

# Parse the timestamp into a datetime object
#dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")

# Add an 8-hour gap
#dt_plus_8_hours = dt + timedelta(hours=8)

# Convert the new datetime object back into a string
#new_timestamp_str = dt_plus_8_hours.strftime("%Y-%m-%dT%H:%M:%S.%f")

#print(new_timestamp_str)

#from datetime import datetime

# Given timestamps
#expires_at = "2025-03-06T10:25:49.125325"
#created_at = "2025-03-06T02:25:49.125325"

# Parse the timestamps into datetime objects
#expires_dt = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%f")
#created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f")

# Calculate the difference
#time_diff = expires_dt - created_dt

# Convert the difference to hours
#hours_diff = time_diff.total_seconds() / 3600

#print(f"The difference is {hours_diff} hours.")

import bittensor as bt

def get_uid_from_hotkey(hotkey: str, netuid: int):
    """
    Retrieve the UID for a wallet registered on a subnet using its hotkey.

    Args:
        hotkey (str): The public key (hotkey) of the wallet.
        netuid (int): The subnet ID.

    Returns:
        int: The UID of the wallet, or None if not found.
    """
    # Connect to the subtensor network
    sub = bt.subtensor('test')  # Replace 'finney' with the desired network

    # Get the metagraph for the subnet
    meta = sub.metagraph(netuid)

    # Find the UID for the given hotkey
    uid = next((uid for uid, registered_hotkey in zip(meta.uids, meta.hotkeys) if registered_hotkey == hotkey), None)

    if uid is not None:
        print(f"Miner UID: {uid}")
    else:
        print("Hotkey not found in the subnet")

    return uid

# Example Usage
if __name__ == "__main__":
    # Specify the hotkey and subnet ID
    hotkey = "5F3wi4rawjQkiXiGxYm2GSoLHPZXfafJHJP6yYRF6pK3Wau6"  # Replace with the actual hotkey
    netuid = 100  # Replace with the correct subnet ID

    # Retrieve the UID
    uid = get_uid_from_hotkey(hotkey, netuid)
    print(f"UID: {uid}")
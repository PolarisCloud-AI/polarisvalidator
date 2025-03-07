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
def get_uid_from_signature(signature, message, netuidge: str, netuid: int):
    # Connect to the subtensor network
    sub = bt.subtensor('finney')
    
    # Recover the hotkey from the signature
    recovered_hotkey = bt.Keypair.verify(message, signature)
    print(f"Recovered Hotkey: {recovered_hotkey}")
    
    # Get the metagraph for the subnet
    meta = sub.metagraph(netuid)
    
    # Find the UID for the recovered hotkey
    uid = next((uid for uid, hotkey in zip(meta.uids, meta.hotkeys) if hotkey == recovered_hotkey), None)
    
    if uid is not None:
        print(f"Miner UID: {uid}")
    else:
        print("Hotkey not found in the subnet")
    
    return uid

# Example Usage
message = "Sign this message to verify identity"
signature = "0xabcdef123456789..."  # Replace with actual signature
netuid = 100  # Replace with the correct subnet ID

get_uid_from_signature(signature, message, netuid)
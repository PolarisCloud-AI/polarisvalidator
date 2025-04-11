# import bittensor as bt

# # Replace these values with your specific hotkey and subnet netuid
# hotkey = "5Gxwzb9gKBCE2a4Qb6VDfUSabKMRZt9AKWw4VrPWZnuUWAsw"
# netuid = 49  # Example subnet UID
# network = "finney" 

# # Initialize connection
# sub = bt.subtensor(network=network)
# mg = sub.metagraph(netuid)

# # Check registration
# if hotkey not in mg.hotkeys:
#     print(f"Hotkey {hotkey} is deregistered")
# else:
#     uid = mg.hotkeys.index(hotkey)
#     stake_weight = mg.S[uid].item()  # Stake weight in Tao
#     is_validator = mg.validator_permit[uid]
#     is_active = mg.active[uid]
#     is_consensus = mg.consensus[uid]
    
#     print(f"Node Information:")
#     print(f"  - Hotkey: {hotkey}")
#     print(f"  - UID: {uid}")
#     print(f"  - Stake Weight: {stake_weight:.2f} TAO")
#     print(f"  - Validator: {'Yes' if is_validator else 'No'}")
#     print(f"  - Active: {'Yes' if is_active else 'No'}")
#     print(f"  - Consensus: {'Yes' if is_consensus else 'No'}")

# top_64_stakes = sorted(mg.S.tolist())[-64:]
# threshold = min(top_64_stakes)
# print(f"\nCurrent top 64 threshold: {threshold:.2f} TAO")
# print(f"Above threshold: {'Yes' if stake_weight >= threshold else 'No'}")

# # Additional node info
# try:
#     node_info = sub.get_validator_info(hotkey=hotkey, netuid=netuid)
#     print("\nAdditional Node Information:")
#     for key, value in node_info.items():
#         print(f"  - {key}: {value}")
# except Exception as e:
#     print(f"\nFailed to retrieve additional node info: {e}")


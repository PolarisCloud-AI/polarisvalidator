import bittensor as bt

wallet = bt.wallet(name="validator")  # Replace with your wallet name
print(wallet.hotkey.ss58_address)


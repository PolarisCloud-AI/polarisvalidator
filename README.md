# Polaris Cloud Validator (NETUID 49)


Welcome to the **Polaris Compute Subnet** repository! This project is part of the decentralized AI ecosystem powered by **Bittensor**, where **miners** provide compute resources and **validators** ensure the integrity and reliability of the network.

## About Polaris Cloud Subnet

![subentflow](https://github.com/user-attachments/assets/0f009ad7-2e41-4e0b-ab3c-64d0c146fdc7)

The **Polaris Cloud Subnet** (NetUID 49) is designed to provide an efficient, secure, and decentralized platform for both **miners** and **validators**:
- **Miners** contribute compute resources, which are tracked and scored based on the number of compute hours provided and uptime.
- **Validators** ensure network security and reliability by maintaining ledger integrity and rewarding miners based on their contributions.

> **Note**: This guide assumes basic familiarity with **Bittensor subnets** and blockchain-based systems.

## System Requirements

To run a validator node on the **Polaris Cloud Subnet**, ensure your system meets the following requirements:
- **Operating System**: Windows, macOS, or Linux

- **RAM**: Minimum 8 GB
- **Docker**: Installed and running
- **CPU**: Modern multi-core processor (e.g., Intel i5 or AMD Ryzen 5)
- **Python Version**: Python 3.8 or higher
- **TAO Tokens**: At least **1 TAO token** (0.0005 TAO burned during registration)

## Installation & Setup Guide

Follow the steps below to join and contribute to the **Polaris Cloud Subnet** (NetUID 49) as a **Validator**.

### Step 0: Create Wallets
Create a **coldkey** and **hotkey** for the **subnet validator wallet**:
```bash
# Install bittensor CLI
pip install bittensor-cli

# Create a coldkey for the validator
btcli wallet new_coldkey --wallet.name <your_wallet_name>

# Create a hotkey for the validator
btcli wallet new_hotkey --wallet.name <your_wallet_name> --wallet.hotkey default
```

### Step 1:  Initiate the validator as a component
Register your **subnet validator key** to the subnet:

```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <your_wallet_name> --wallet.hotkey default
```

### Step 2: Verify Wallet Registration

Check that your key has been successfully registered by running:

```bash
btcli wallet overview --wallet.name <your_wallet_name> --subtensor.network finney
```
## Run the Validator
## From the Repo
### **Step 1: Clone the Repository**
Open a terminal and run the following commands:

```bash
# Clone the Polaris Bittensor repository
git clone https://github.com/bigideaafrica/polarisvalidator.git

# Navigate into the project directory
cd polarisvalidator
```

### **Step 2: Install Requirements**
Ensure you have **Python 3.8+** installed, then run:

```bash
pip install -r requirements.txt
```

### Step 3:  Initiate the validator as a component
Ensure you run this 
```bash
pip install -e .
```
## Step 4: Run the validator 
```bash 
python neurons/validator.py --netuid 49 --wallet.name <validator-name> --wallet.hotkey <hot-key> --logging.debug
```
### Alternative: Use the Automated Script

For an easier setup, you can use our automated script that detects your OS and runs the appropriate Docker command:

1. Download the `entry_point.sh` script from this repository
2. Make it executable: `chmod +x entry_point.sh`
3. Run it: `./entry_point.sh`

The script will:
- Detect your operating system
- Ask for your wallet name and hotkey
- Set up the correct path for your Bittensor wallets
- Run the validator Docker image with the appropriate settings

## Run Docker Image 

### Step 1: Pull and Run the Validator Docker Image

Pull the Docker image for the Polaris validator:

```bash
docker pull bateesa/polaris-validator
```

## Step 2: Run the validator using the appropriate command for your operating system:

**For macOS/Linux**:
```bash
docker run --rm -it -v ~/.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default bateesa/polaris-validator
```

**For Windows (Command Prompt)**:
```bash
docker run --rm -it -v C:\Users\YourUsername\.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default bateesa/polaris-validator
```

**For Windows (PowerShell)**:
```powershell
docker run --rm -it -v ${HOME}/.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default bateesa/polaris-validator
```
### Step Stop the Validator Node

To stop your running validator node, press:
```bash
CTRL + C
```
## **Support & Contributions**
We welcome contributions to the **Polaris Compute Subnet**. If you encounter issues or have suggestions for improvements, feel free to open an **Issue** or a **Pull Request** on our [GitHub repository](https://github.com/bigideaafrica/polarisvalidator).


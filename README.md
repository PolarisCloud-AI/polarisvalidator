# **Polaris Cloud Validator (NETUID 49)**

Welcome to the **Polaris Cloud Subnet** repository! This project is part of the decentralized AI ecosystem powered by **Bittensor**, where **miners** provide compute resources and **validators** ensure the integrity and reliability of the network.

---

## **About Polaris Cloud Subnet**
The **Polaris Cloud Subnet** (NetUID 49) is designed to provide an efficient, secure, and decentralized platform for both **miners** and **validators**:
- **Miners** contribute compute resources, which are tracked and scored based on quality and duration.
- **Validators** ensure network security and reliability by maintaining ledger integrity and rewarding miners based on their contributions.

> **Note**: This guide assumes basic familiarity with **Bittensor subnets** and blockchain-based systems.

---

## **System Requirements**
To run a validator node on the **Polaris Cloud Subnet**, ensure your system meets the following requirements:

- **Operating System**: Windows or Linux
- **RAM**: Minimum 8 GB
- **CPU**: Modern multi-core processor (e.g., Intel i5 or AMD Ryzen 5)
- **Python Version**: Python 3.8 or higher
- **TAO Tokens**: At least **1 TAO token** (0.0005 TAO burned during registration)

---

## **Installation & Setup Guide**
Follow the steps below to join and contribute to the **Polaris Cloud Subnet** (NetUID 49) as a **Validator**.

---

### **Step 1: Clone the Repository**
Open a terminal and run the following commands:

```bash
# Clone the Polaris Bittensor repository
git clone https://github.com/bigideaafrica/polarisvalidator.git

# Navigate into the project directory
cd polarisvalidator
```

---

### **Step 2: Install Requirements**
Ensure you have **Python 3.8+** installed, then run:

```bash
pip install -r requirements.txt
```

---

### **Step 3: Install the Package**
Install the Polaris package locally using the following command:

```bash
pip install -e .
```

---

### **Step 4: Create Wallets**
Create a **coldkey** and **hotkey** for the **subnet validator wallet**:

```bash
#Install bittensor cli
pip install bittensor-cli==9.1.0 # Use latest or desired version

# Create a coldkey for the validator
btcli wallet new_coldkey --wallet.name <validator-name>

# Create a hotkey for the validator
btcli wallet new_hotkey --wallet.name <validator-name> --wallet.hotkey default
```

---

### **Step 5: Register Keys**
Register your **subnet validator key** to the subnet:

```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <validator-name> --wallet.hotkey default
```

---

### **Step 6: Verify Wallet Registration**
Check that your key has been successfully registered by running:

```bash
btcli wallet overview --wallet.name <validator-name> --subtensor.network finney
```

---

### **Step 7: Start the Subnet Validator**
Run the **Polaris Compute Subnet validator** using the following command:

```bash
python neurons/validator.py --netuid 49 --wallet.name <validator-name> --wallet.hotkey default --logging.debug
```

---

### **Step 8: Stop the Validator Node**
To stop your running validator node, press:

```bash
CTRL + C
```

---

## **Support & Contributions**
We welcome contributions to the **Polaris Compute Subnet**. If you encounter issues or have suggestions for improvements, feel free to open an **Issue** or a **Pull Request** on our [GitHub repository](https://github.com/tobiusaolo/Polaris_bittensor).

For further inquiries, reach out to the **Polaris Compute Subnet** community.

---
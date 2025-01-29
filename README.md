# **Polaris Bittensor Validator (NETUID 12)**
---
## **Polaris Compute Subnet Repository**
Welcome to the **Polaris Compute Bittensor Subnet** repository. This project contributes to a decentralized AI ecosystem where **miners** provide compute resources to remote users, and **validators** ensure the integrity of the network.

## **About the Polaris Compute Subnet**
The **Polaris Compute Subnet** (NetUID 12) provides an efficient, secure, and decentralized platform for both **miners** and **validators**:
- **Miners** contribute compute resources, which are **tracked and scored** based on quality and duration.
- **Validators** ensure **network security and reliability** by maintaining ledger integrity and rewarding miners based on their contributions.

> **Note**: This guide assumes basic familiarity with **Bittensor subnets**.

---

## **Prerequisites**
Before setting up your validator node, ensure that you meet the following requirements:

✅ A system running **Windows** or **Linux** (no specific hardware requirements).  
✅ Basic familiarity with **command-line operations**.  
✅ **TAO tokens** for registration:  
   - **Validators**: At least **1 TAO token** (0.0001 TAO burned during registration).  

---

## **Installation & Setup Guide**
Follow the steps below to join and contribute to the **Polaris Compute Subnet** (NetUID 12) as a **Validator**.

### **Step 1: Clone the Repository**
Open a terminal and run the following commands:

```bash
# Clone the Polaris Bittensor repository
git clone https://github.com/tobiusaolo/Polaris_bittensor.git

# Navigate into the project directory
cd Polaris_bittensor
```

### **Step 2: Install Requirements**
Ensure you have **Python 3.8+** installed, then run:

```bash
pip install -r requirements.txt
```

---

### **Step 3: Create Wallets**
Create a **coldkey** and **hotkey** for the **subnet validator wallet**:

```bash
btcli wallet new_coldkey --wallet.name validator
```

```bash
btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default
```

---

### **Step 4: Register Keys**
This step registers your **subnet validator key** to the subnet:

```bash
btcli subnet recycle_register --netuid 12 --subtensor.network finney --wallet.name validator --wallet.hotkey default
```

---

### **Step 5: Verify Wallet Registration**
Check that your key has been successfully registered by running:

```bash
btcli wallet overview --wallet.name validator
```

---

### **Step 6: Start the Subnet Validator**
Run the **Polaris Compute Subnet validator** using the following command:

```bash
python neurons/validator.py --netuid 12 --wallet.name validator --wallet.hotkey default --logging.debug
```

---

### **Step 7: Stop the Validator Node**
To stop your running validator node, press:

```bash
CTRL + C
```

---

## **Support & Contributions**
We welcome contributions to the **Polaris Compute Subnet**. If you encounter issues or have suggestions for improvements, feel free to open an **Issue** or a **Pull Request** on our [GitHub repository](https://github.com/tobiusaolo/Polaris_bittensor).

For further inquiries, reach out to the **Polaris Compute Subnet** community.

---
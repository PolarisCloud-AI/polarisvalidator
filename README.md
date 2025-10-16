# 🚀 **Polaris Cloud Subnet (NETUID 49)**

> **Decentralized AI compute network powered by Bittensor** - Miners provide compute resources, validators ensure network integrity through sophisticated reward mechanisms.

![subnetflow](https://github.com/user-attachments/assets/0f009ad7-2e41-4e0b-ab3c-64d0c146fdc7)

---

## 🎯 **What is Polaris Cloud?**

**Polaris Cloud Subnet** is a decentralized compute network where:
- **Miners** contribute GPU/CPU resources and earn rewards based on performance
- **Validators** maintain network security and distribute rewards fairly
- **Quality Control** ensures only high-performance resources participate (PoW ≥ 0.03)

### **Key Features**
- ✅ **Performance-Based Rewards** - Rewards tied to actual compute capability
- ✅ **Penalty System** - 30% reduction for non-compliant resources (Those who did not allow mining)
- ✅ **Multi-Layer Bonuses** - Uptime, container activity, and Alpha stake bonuses
- ✅ **Quality Gates** - Strict PoW thresholds maintain network quality

---

## 🏗️ **System Architecture**

### **Reward Calculation**
```
Final Score = Base Score × Compute Multiplier × Bonus Multipliers
```

**Base Score**: Uptime reliability + Container activity  
**Compute Multiplier**: Raw PoW score (minimum 0.03 required)  
**Bonuses**: Uptime (+5% to +15%), Container (+8% to +20%), Alpha Stake (+10% to +20%)

### **Penalty System**
- **30% reduction** for resources that don't allow minning
- **Penalty accumulation** across all non-compliant resources
- **Penalty burning** - collected penalties redistributed to incentivize compliance

### **Quality Control**
- **PoW ≥ 0.03**: Required for ANY participation
- **PoW < 0.03**: Complete exclusion from rewards
- **No exceptions**: Performance is the gatekeeper

---

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.8+
- Docker (optional)
- TAO tokens (minimum 1 TAO for registration)

### **1. Create Wallets**
```bash
# Install bittensor CLI
pip install bittensor-cli

# Create validator wallet
btcli wallet new_coldkey --wallet.name <your_wallet_name>
btcli wallet new_hotkey --wallet.name <your_wallet_name> --wallet.hotkey default
```

### **2. Register Validator**
```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <your_wallet_name> --wallet.hotkey default
```

### **3. Run Validator**

**Option A: Direct Python**
```bash
git clone https://github.com/bigideaafrica/polarisvalidator.git
cd polarisvalidator
pip install -r requirements.txt
pip install -e .
python neurons/validator.py --netuid 49 --wallet.name <validator-name> --wallet.hotkey <hot-key>
```

**Option B: Docker**
```bash
docker pull bigideaafrica/polaris-validator
docker run --rm -it -v ~/.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default bigideaafrica/polaris-validator
```

**Option C: Automated Script**
```bash
chmod +x entry_point.sh
./entry_point.sh
```

---

## 📊 **Reward System Details**

### **For Miners**
- **PoW ≥ 0.03**: Required for participation
- **Higher Uptime**: Better base scores (95-100% = +15% bonus)
- **Active Containers**: More work = higher scores (5+ containers = +20% bonus)
- **Alpha Stake**: Network participation bonuses (1000+ Alpha = +10% bonus)
- **Compliance**: Ensure you allow mining to avoid 30% penalty off your scores


### **Penalty System**
- **Non-compliant resources** receive 30% score reduction for not allowing mining
- **Penalties are burned** and redistributed to incentivize compliance

---

## 📚 **Documentation**

### **Complete System Documentation**
- **[REWARDING_MECHANISM_COMPREHENSIVE.md](./REWARDING_MECHANISM_COMPREHENSIVE.md)** - Complete rewarding mechanism
  - Penalty system and burning mechanism
  - Bonus calculations and special miner bonuses
  - Monitoring, logging, and configuration

### **Technical Implementation**
- **[REWARD_MECHANISM_README.md](./REWARD_MECHANISM_README.md)** - Technical implementation details
  - API functions and configuration parameters
  - Error handling and performance optimization
  - System architecture and core components

---

## ⚙️ **Configuration**

### **Key Parameters**
```python
SCORE_THRESHOLD = 0.03  # Minimum PoW for participation
ALLOW_MINING_PENALTY = 0.7  # 30% reduction for allow_mining=False
ALPHA_STAKE_HIGH_TIER = 5000  # High tier threshold
ALPHA_STAKE_MEDIUM_TIER = 1000  # Medium tier threshold
```

### **Bonus Multipliers**
- **Uptime**: 1.05x to 1.15x (5% to 15% bonus)
- **Container**: 1.08x to 1.20x (8% to 20% bonus)
- **Alpha Stake**: 1.10x to 1.20x (10% to 20% bonus)

---


## 🤝 **Support & Contributing**

### **Getting Help**
- **Complete System**: [REWARDING_MECHANISM_COMPREHENSIVE.md](./REWARDING_MECHANISM_COMPREHENSIVE.md)


---

## 📄 **License**

This project is licensed under the terms specified in the [LICENSE](./LICENSE) file.

---

## 🏆 **System Status**

**Current Version**: 2.1  
**Last Updated**: 2025-10-15  
**Status**: Production Ready ✅  
**Maintainer**: Polaris Validator Team

**Key Achievements**:
- ✅ Strict PoW threshold for any participation
- ✅ Multiplier-based scoring architecture
- ✅ Penalty system with burning mechanism
- ✅ Calibrated bonus systems
- ✅ Comprehensive monitoring and transparency

---

**🎯 Ready to Deploy**: The Polaris Validator provides a robust, fair, and sustainable reward mechanism that incentivizes quality network participation while maintaining transparency and reliability.

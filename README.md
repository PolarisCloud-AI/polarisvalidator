# 🚀 **Polaris Cloud Validator (NETUID 49)**

Welcome to the **Polaris Cloud Subnet** repository! This project is part of the decentralized AI ecosystem powered by **Bittensor**, where **miners** provide compute resources and **validators** ensure the integrity and reliability of the network through a sophisticated, fair, and transparent reward mechanism.

## 🎯 **About Polaris Cloud Subnet**

![subnetflow](https://github.com/user-attachments/assets/0f009ad7-2e41-4e0b-ab3c-64d0c146fdc7)

The **Polaris Cloud Subnet** (NetUID 49) is designed to provide an efficient, secure, and decentralized platform for both **miners** and **validators**:

- **Miners** contribute compute resources, which are tracked and scored based on:
  - **Compute Performance** (PoW score ≥ 0.03 required for participation)
  - **Uptime Reliability** (availability and consistency)
  - **Container Management** (active work being performed)
  - **Network Contribution** (stake and participation)

- **Validators** ensure network security and reliability by:
  - Maintaining ledger integrity
  - Implementing fair reward distribution
  - Enforcing quality control through performance thresholds
  - Providing transparent scoring and bonus systems

> **🚨 CRITICAL**: The system implements a **strict performance threshold** where only miners with PoW ≥ 0.03 can participate. This ensures network quality while providing fair rewards.

## 🏗️ **System Architecture & Reward Mechanism**

### **🎯 Core Philosophy**
- **Fairness**: Rewards based on actual performance, not arbitrary factors
- **Transparency**: Clear understanding of how rewards are calculated
- **Quality Control**: Strict performance thresholds ensure network reliability
- **Sustainability**: Balanced system that prevents reward inflation

### **🚨 Performance Threshold System**
- **PoW ≥ 0.03**: Required for ANY participation in the network
- **PoW < 0.03**: **Completely excluded** - no rewards, no bonuses
- **No exceptions**: Cannot buy rewards with stake alone
- **Performance is the gatekeeper** for all network participation

### **🔄 Multiplier-Based Scoring Architecture**
The system uses a sophisticated scoring approach where:
- **Base Score**: Uptime + Container management (reliability & activity)
- **Compute Multiplier**: Raw PoW score as multiplier (specs/power)
- **Final Score**: Base Score × Compute Multiplier × Bonuses

### **🎁 Bonus Systems (Only for Qualified Miners)**
- **Uptime Multipliers**: +5% to +15% for high availability
- **Container Bonuses**: +8% to +20% for active work management
- **Alpha Stake Bonuses**: +10% to +20% for network participation

## 📚 **Comprehensive Documentation**

### **📖 Technical Implementation**
- **[REWARD_MECHANISM_README.md](./REWARD_MECHANISM_README.md)** - Complete technical implementation guide
  - System architecture and core components
  - Detailed reward calculation formulas
  - API functions and configuration parameters
  - Error handling and performance optimization

### **👥 User-Friendly Guide**
- **[REWARD_MECHANISM_OVERVIEW.md](./REWARD_MECHANISM_OVERVIEW.md)** - Simple explanation for users
  - How rewards work in plain language
  - Optimization tips and best practices
  - Real-world examples and scenarios
  - Troubleshooting common issues

### **🏗️ System Overview**
- **[REWARD_MECHANISM_SUMMARY.md](./REWARD_MECHANISM_SUMMARY.md)** - High-level system summary
  - Architecture diagrams and flow descriptions
  - Configuration parameters and system behavior
  - Performance metrics and monitoring
  - Future enhancements and extensibility

### **📊 Scoring Improvements**
- **[SCORING_IMPROVEMENTS_SUMMARY.md](./SCORING_IMPROVEMENTS_SUMMARY.md)** - Recent system improvements
  - Threshold system implementation
  - Multiplier-based architecture changes
  - Bonus calibration and optimization
  - Performance and fairness metrics

## 🎯 **Key System Features**

### **✅ Quality Control**
- **Performance Gate**: PoW ≥ 0.03 is the absolute requirement
- **Resource Validation**: Must pass monitoring and authentication checks
- **Hotkey Verification**: Ensures miner authenticity on the network
- **Threshold Filtering**: Excludes resources with PoW < 0.03

### **⚖️ Fair Reward Distribution**
- **Performance-Based**: Rewards directly tied to compute capability
- **Transparent Calculation**: Clear relationship between PoW and rewards
- **Balanced Bonuses**: Enhancements that don't overwhelm base performance
- **Sustainable System**: Prevents inflation while maintaining incentives

### **🔍 Comprehensive Monitoring**
- **Real-time Logging**: Detailed calculation breakdown and transparency
- **Performance Metrics**: Processing time and resource statistics
- **Score Distribution**: Raw and normalized score ranges
- **Bonus Impact**: Applied bonus multiplier statistics

## 💻 **System Requirements**

To run a validator node on the **Polaris Cloud Subnet**, ensure your system meets the following requirements:

- **Operating System**: Windows, macOS, or Linux
- **RAM**: Minimum 8 GB
- **CPU**: Modern multi-core processor (e.g., Intel i5 or AMD Ryzen 5)
- **Python Version**: Python 3.8 or higher
- **Docker**: Installed and running
- **TAO Tokens**: At least **1 TAO token** (0.0005 TAO burned during registration)

## 🚀 **Installation & Setup Guide**

### **Step 1: Create Wallets**

Create a **coldkey** and **hotkey** for the **subnet validator wallet**:
```bash
# Install bittensor CLI
pip install bittensor-cli

# Create a coldkey for the validator
btcli wallet new_coldkey --wallet.name <your_wallet_name>

# Create a hotkey for the validator
btcli wallet new_hotkey --wallet.name <your_wallet_name> --wallet.hotkey default
```

### **Step 2: Register Your Validator to the Subnet**

Register your **subnet validator key** to the subnet:
```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <your_wallet_name> --wallet.hotkey default
```

### **Step 3: Verify Wallet Registration**

Check that your key has been successfully registered:
```bash
btcli wallet overview --wallet.name <your_wallet_name> --subtensor.network finney
```

## 🏃 **Running the Validator**

Choose one of the following methods to run your validator:

### **Method 1: From the Repository**

#### **Step 1: Clone the Repository**
```bash
# Clone the Polaris Bittensor repository
git clone https://github.com/bigideaafrica/polarisvalidator.git

# Navigate into the project directory
cd polarisvalidator
```

#### **Step 2: Install Requirements**
Ensure you have **Python 3.8+** installed, then run:
```bash
pip install -r requirements.txt
```

#### **Step 3: Install the Package**
```bash
pip install -e .
```

#### **Step 4: Run the Validator**
```bash 
python neurons/validator.py --netuid 49 --wallet.name <validator-name> --wallet.hotkey <hot-key> --logging.debug
```

### **Method 2: Using Docker**

#### **Step 1: Pull the Validator Docker Image**
```bash
docker pull bigideaafrica/polaris-validator
```

#### **Step 2: Run the Validator Docker Container**

**For macOS/Linux**:
```bash
docker run --rm -it -v ~/.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default  bigideaafrica/polaris-validator
```

**For Windows (Command Prompt)**:
```bash
docker run --rm -it -v C:\Users\YourUsername\.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default bigideaafrica/polaris-validator
```

**For Windows (PowerShell)**:
```powershell
docker run --rm -it -v ${HOME}/.bittensor:/root/.bittensor -e WALLET_NAME=<your_wallet_name> -e WALLET_HOTKEY=default   bigideaafrica/polaris-validator
```

### **Method 3: Using the Automated Script**

For an easier setup, you can use our automated script:

1. Download the `entry_point.sh` script from this repository
2. Make it executable: `chmod +x entry_point.sh`
3. Run it: `./entry_point.sh`

The script will:
- Detect your operating system
- Ask for your wallet name and hotkey
- Set up the correct path for your Bittensor wallets
- Run the validator Docker image with the appropriate settings

## 🛑 **Stopping the Validator**

To stop your running validator node, press:
```bash
CTRL + C
```

## 📊 **Understanding the Reward System**

### **🔍 How Rewards Are Calculated**

1. **Performance Check**: Only miners with PoW ≥ 0.03 are considered
2. **Base Scoring**: Uptime reliability + Container management
3. **Compute Multiplication**: Raw PoW score acts as multiplier
4. **Bonus Application**: Uptime, container, and stake bonuses
5. **Score Normalization**: Scaling to 0-500 range with fair distribution

### **🎯 What Miners Need to Know**

- **PoW ≥ 0.03**: Required for any participation
- **Uptime**: Higher availability = higher base scores
- **Containers**: More active work = higher base scores
- **Compute Power**: Higher specs = higher multipliers
- **Stake**: Alpha tokens provide additional bonuses

### **📈 Expected Score Ranges**

- **High-Performance Miners**: 2.5-4.0 × normalization factor
- **Medium-Performance Miners**: 0.6-1.5 × normalization factor
- **Low-Performance Miners**: **0 - completely excluded**

## 🔧 **Configuration & Customization**


### **Bonus Calibration**
- **Uptime Multipliers**: 1.05x to 1.15x (calibrated to prevent excessive bonuses)
- **Container Bonuses**: 1.08x to 1.20x (balanced for fair distribution)
- **Stake Bonuses**: 1.10x to 1.20x (enhancement without replacement)

## 🚀 **Performance & Monitoring**

### **Key Metrics**
- **Processing Time**: Per-miner and total execution time
- **Resource Counts**: Verified and filtered resource statistics
- **Score Distribution**: Raw and normalized score ranges
- **Bonus Impact**: Applied bonus multiplier statistics

### **Debug Information**
- **Calculation Steps**: Detailed scoring breakdown
- **Error Context**: Comprehensive error information
- **Data Validation**: Input parameter verification
- **Fallback Usage**: Alternative calculation tracking

## 🔮 **Future Enhancements**

### **Planned Improvements**
- **Dynamic Weighting**: Adaptive scoring based on network conditions
- **Machine Learning**: Predictive performance modeling
- **Advanced Analytics**: Real-time fairness metrics
- **Performance Optimization**: Enhanced async processing

### **Extensibility Features**
- **Plugin Architecture**: Modular bonus system
- **Configuration API**: Runtime parameter adjustment
- **Custom Metrics**: User-defined scoring factors
- **Integration Hooks**: External system connectivity

## 🆘 **Troubleshooting**

### **Common Issues**
1. **Score Compression**: Check normalization parameters
2. **Bonus Overwhelming**: Verify bonus multiplier calibration
3. **Threshold Filtering**: Review SCORE_THRESHOLD setting
4. **Performance Degradation**: Monitor async processing efficiency

### **Debug Commands**
```python
# Enable debug logging
logger.setLevel(logging.DEBUG)

# Monitor specific components
logger.debug(f"Resource score calculation: uptime={uptime_percent:.1f}%, "
            f"compute={compute_score:.2f}, containers={active_container_count}")
```

## 🤝 **Support & Contributions**

We welcome contributions to the **Polaris Cloud Subnet**! If you encounter issues or have suggestions for improvements, feel free to:

- **Open an Issue** on our [GitHub repository](https://github.com/bigideaafrica/polarisvalidator)
- **Submit a Pull Request** with your improvements
- **Join our community** discussions
- **Report bugs** or performance issues

### **Getting Help**
- **Technical Issues**: Check the [REWARD_MECHANISM_README.md](./REWARD_MECHANISM_README.md)
- **User Questions**: Refer to [REWARD_MECHANISM_OVERVIEW.md](./REWARD_MECHANISM_OVERVIEW.md)
- **System Overview**: See [REWARD_MECHANISM_SUMMARY.md](./REWARD_MECHANISM_SUMMARY.md)
- **Recent Changes**: Review [SCORING_IMPROVEMENTS_SUMMARY.md](./SCORING_IMPROVEMENTS_SUMMARY.md)

## 📄 **License**

This project is licensed under the terms specified in the [LICENSE](./LICENSE) file.

## 🏆 **System Status**

**Current Version**: 2.1  
**Last Updated**: 2025-08-12  
**Status**: Production Ready ✅  
**Maintainer**: Polaris Validator Team

**Key Achievements**:
- ✅ Strict PoW threshold for any participation
- ✅ Multiplier-based scoring architecture
- ✅ Calibrated bonus systems
- ✅ Improved score normalization
- ✅ Enhanced logging and transparency
- ✅ Robust error handling
- ✅ Quality control mechanisms

---

**🎯 Quick Start**: For technical implementation, see [REWARD_MECHANISM_README.md](./REWARD_MECHANISM_README.md). For user understanding, see [REWARD_MECHANISM_OVERVIEW.md](./REWARD_MECHANISM_OVERVIEW.md).

**🚀 Ready to Deploy**: The Polaris Validator provides a robust, fair, and sustainable reward mechanism that incentivizes quality network participation while maintaining transparency and reliability.

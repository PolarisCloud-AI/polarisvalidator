# 🎯 **Polaris Validator Reward System - User Guide**

## 📖 **What is the Polaris Validator Reward System?**

The Polaris Validator Reward System is a smart way to fairly reward miners (computers that help run the network) based on how well they perform. Think of it like a sophisticated grading system that evaluates miners on multiple factors and gives them rewards accordingly.

## 🎯 **How Does It Work? (Simple Explanation)**

### **The Basic Idea**
Imagine you're running a restaurant and want to reward your staff. You wouldn't just pay everyone the same amount - you'd consider:
- **How reliable they are** (uptime - always showing up for work)
- **How many customers they serve** (containers - active work being done)
- **How skilled they are** (compute power - their natural abilities)
- **How long they've been with you** (stake in the network)

The Polaris system works the same way - it looks at multiple factors to determine fair rewards, with **compute power acting as a multiplier** for base reliability scores.

## 🚨 **IMPORTANT: Performance Threshold Requirement**

### **The Golden Rule: PoW ≥ 0.03**
- **PoW ≥ 0.03**: You can participate and earn rewards + bonuses
- **PoW < 0.03**: You get **NOTHING** - completely excluded from the system
- **No exceptions**: You cannot buy rewards with stake alone

### **What This Means**
- **Performance is the gatekeeper** - you must meet the minimum compute requirement
- **Stake bonuses only work** if you already meet the performance threshold
- **Quality control** ensures only good performers participate in the network

## 🏆 **What Factors Determine Rewards?**

### **1. 🖥️ Compute Performance (REQUIRED + Multiplier)**
- **What it is**: How powerful and efficient your computer is
- **How it's measured**: Proof of Work (PoW) score
- **Why it matters**: Better computers get a higher multiplier, meaning they earn more for the same reliability
- **Example**: A high-end gaming PC gets a 0.15x multiplier, while an old laptop gets a 0.05x multiplier
- **⚠️ CRITICAL**: You must have PoW ≥ 0.03 to participate at all!

### **2. ⏰ Uptime Reliability (Base Score)**
- **What it is**: How often your computer is available and working
- **How it's measured**: Percentage of time your computer is online
- **Why it matters**: The network needs reliable computers that are always available
- **Example**: A computer that's online 95% of the time gets 9.5 points, while one that's only online 70% of the time gets 7.0 points
- **⚠️ NOTE**: Only applies if you meet the PoW threshold!

### **3. 📦 Container Management (Base Score)**
- **What it is**: How many active programs (containers) your computer is running
- **How it's measured**: Number of running containers
- **Why it matters**: More containers mean your computer is doing more work for the network
- **Example**: A computer running 5 containers gets 2.5 points, while one running 1 container gets 0.5 points
- **⚠️ NOTE**: Only applies if you meet the PoW threshold!

## 🎁 **Bonus Systems - Extra Rewards for Excellence**

### **⚠️ IMPORTANT: All Bonuses Only Apply to Qualified Miners (PoW ≥ 0.03)**

### **🏅 Uptime Bonuses**
- **95%+ uptime**: +15% bonus (Excellent)
- **85%+ uptime**: +10% bonus (Good)  
- **70%+ uptime**: +5% bonus (Average)
- **Below 70%**: No bonus (Poor)

### **🏠 Rented Machine Bonuses**
- **Having containers**: +8% base bonus
- **Additional containers**: +1% per extra container
- **Maximum bonus**: +20% total

### **💰 Alpha Stake Bonuses**
- **5000+ Alpha tokens**: +20% bonus (High tier)
- **1000+ Alpha tokens**: +10% bonus (Medium tier)
- **Below 1000 Alpha**: No bonus (Low tier)

## 📊 **How Scores Are Calculated (New System)**

### **Step-by-Step Process**

1. **🔍 Discovery**: The system finds all miners on the network
2. **✅ Verification**: Checks that miners are legitimate and verified
3. **🚨 THRESHOLD CHECK**: **Excludes miners with PoW < 0.03**
4. **🧮 Base Scoring**: Calculates reliability score (uptime + containers) for qualified miners only
5. **🚀 Compute Multiplication**: Applies PoW score as a multiplier for qualified miners only
6. **🎁 Bonuses**: Adds uptime, container, and stake bonuses for qualified miners only
7. **📈 Normalization**: Scales all scores to a fair range (0-500)
8. **🏆 Ranking**: Orders miners by their final scores

### **New Scoring Formula**
```
IF PoW < 0.03:
    Result: NOTHING - completely excluded

IF PoW ≥ 0.03:
    Base Score = Uptime Score + Container Score
    Compute Multiplier = Raw PoW Score
    Final Score = Base Score × Compute Multiplier × Bonuses
```

### **Example Calculation**

**Miner A (Qualified - High Performance)**:
- PoW Score: 0.15 (≥ 0.03 ✅)
- Uptime: 95% → 9.5 points
- Containers: 8 running → 4.0 points
- Base Score: 13.5 points
- Alpha Stake: 2000 tokens → 10% bonus
- **Result**: 13.5 × 0.15 × 1.10 = 2.23 × other bonuses

**Miner B (Qualified - Medium Performance)**:
- PoW Score: 0.06 (≥ 0.03 ✅)
- Uptime: 85% → 8.5 points
- Containers: 3 running → 1.5 points
- Base Score: 10.0 points
- Alpha Stake: 500 tokens → 0% bonus
- **Result**: 10.0 × 0.06 = 0.6 × other bonuses

**Miner C (Disqualified - Low Performance)**:
- PoW Score: 0.02 (< 0.03 ❌)
- Uptime: 98% → Irrelevant
- Containers: 10 running → Irrelevant
- Alpha Stake: 10000 tokens → Irrelevant
- **Result**: NOTHING - completely excluded

### **Quality Control**
- **Minimum Threshold**: Only miners with PoW scores ≥ 0.03 are included
- **Verification Required**: Resources must pass monitoring checks
- **Authenticity Check**: Hotkeys must be verified on the network
- **Performance Gate**: PoW ≥ 0.03 is the absolute requirement

## 🎯 **What This Means for Miners**

### **High-Performance Miners (PoW ≥ 0.03)**
- **Get rewarded** for having powerful computers (higher multiplier)
- **Earn bonuses** for maintaining high uptime
- **Receive incentives** for running multiple containers
- **Benefit from** high Alpha token stakes
- **Result**: Full participation in the reward system

### **Low-Performance Miners (PoW < 0.03)**
- **Get nothing** - completely excluded from rewards
- **Cannot buy rewards** with stake alone
- **Must improve performance** to participate
- **Result**: No participation until PoW ≥ 0.03

## 🔧 **How to Optimize Your Rewards**

### **1. Meet the Performance Threshold (REQUIRED)**
- **PoW Score ≥ 0.03** is mandatory
- Use better hardware (CPU/GPU)
- Optimize your system settings
- Keep software updated
- Monitor performance metrics

### **2. Maximize Uptime (Only if PoW ≥ 0.03)**
- Use reliable internet connections
- Set up automatic restarts
- Monitor system health
- Have backup power sources

### **3. Manage Containers Effectively (Only if PoW ≥ 0.03)**
- Run the recommended number of containers
- Monitor container performance
- Restart failed containers quickly
- Balance resource usage

### **4. Stake Alpha Tokens (Only if PoW ≥ 0.03)**
- Consider staking Alpha tokens for bonuses
- Higher stakes = higher bonus percentages
- Long-term commitment = better rewards

## 📈 **Real-World Example**

### **Scenario: Three Different Miners**

**Miner A (Qualified - High Performance + High Stake)**
- PoW Score: 0.15 (≥ 0.03 ✅)
- Uptime: 98% (excellent)
- Containers: 8 running
- Alpha Stake: 2000 tokens (10% bonus)
- **Calculation**: (9.8 + 4.0) × 0.15 × 1.10 = 2.27 × other bonuses
- **Result**: Full participation with all bonuses

**Miner B (Qualified - Medium Performance + Low Stake)**
- PoW Score: 0.06 (≥ 0.03 ✅)
- Uptime: 88% (good)
- Containers: 3 running
- Alpha Stake: 500 tokens (0% bonus)
- **Calculation**: (8.8 + 1.5) × 0.06 = 0.618 × other bonuses
- **Result**: Full participation without stake bonus

**Miner C (Disqualified - Low Performance + High Stake)**
- PoW Score: 0.02 (< 0.03 ❌)
- Uptime: 60% (poor)
- Containers: 0 running
- Alpha Stake: 10000 tokens (irrelevant)
- **Result**: NOTHING - completely excluded

## 🚀 **Benefits of This New System**

### **For the Network**
- **Quality Control**: Only good performers get rewards
- **Fair Distribution**: Rewards based on actual contribution
- **Incentive Alignment**: Encourages desired behaviors
- **Network Growth**: Attracts and retains quality miners

### **For Miners**
- **Transparent Rewards**: Clear understanding of how rewards work
- **Fair Competition**: Everyone has equal opportunity to succeed
- **Performance Recognition**: Good work is properly rewarded
- **Growth Potential**: Opportunities to improve and earn more

### **For Validators**
- **Reliable Network**: High-quality miners ensure network stability
- **Efficient Operations**: Automated reward distribution
- **Data Insights**: Comprehensive performance metrics
- **Quality Assurance**: Built-in verification and filtering

## 🔍 **Monitoring Your Performance**

### **What You Can Track**
- **Real-time scores**: See your current performance
- **Historical data**: Track improvements over time
- **Bonus breakdown**: Understand which bonuses you're earning
- **Network ranking**: See how you compare to other miners

### **Key Metrics to Watch**
- **PoW Score**: Your compute performance (must be ≥ 0.03)
- **Uptime Percentage**: How reliable you are (base score)
- **Container Count**: How many programs you're running (base score)
- **Bonus Multipliers**: Extra rewards you're earning

## 🛠️ **Getting Help**

### **Common Questions**
- **"Why am I getting no rewards?"** Check if your PoW score ≥ 0.03
- **"How do I earn bonuses?"** First meet PoW ≥ 0.03, then improve uptime, run containers, stake Alpha tokens
- **"What's the minimum to participate?"** PoW score ≥ 0.03 (stake alone is not enough)
- **"How often are rewards calculated?"** Every validation cycle (typically every few hours)

### **Resources Available**
- **Technical Documentation**: Detailed implementation guide
- **Performance Guides**: Tips for optimization
- **Community Support**: Other miners and validators
- **System Logs**: Detailed performance information

## 🎯 **Summary**

The Polaris Validator Reward System is designed to be:
- **Fair**: Rewards based on actual performance
- **Transparent**: Clear understanding of how rewards work
- **Incentivizing**: Encourages good behavior and quality
- **Accessible**: Opportunities for miners of all levels
- **Sustainable**: Balanced rewards that don't inflate over time

### **Key Innovation: Strict Threshold System**
- **Performance Gate**: PoW ≥ 0.03 is required for ANY participation
- **Base Score**: Uptime + Container management (reliability & activity)
- **Compute Multiplier**: Raw PoW score as multiplier (specs/power)
- **Final Score**: Base Score × Compute Multiplier × Bonuses

### **System Behavior**:
- **PoW ≥ 0.03**: Full participation + all bonuses
- **PoW < 0.03**: **Nothing - completely excluded**
- **No exceptions**: Can't buy rewards with stake alone

This approach ensures that:
- **Only qualified miners** participate in the network
- **Performance is the gatekeeper** for all rewards
- **Stake bonuses enhance** but don't replace performance requirements
- **Network quality** is maintained through strict thresholds

By understanding how the system works and optimizing your performance, you can maximize your rewards and contribute to a stronger, more reliable network.

---

**Remember**: The goal is to build a network where quality miners are rewarded for their contributions, creating a win-win situation for everyone involved.

**Need Help?** Check the technical documentation or reach out to the community for support!

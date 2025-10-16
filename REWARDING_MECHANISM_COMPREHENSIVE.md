# 🎯 **Polaris Cloud Subnet - Comprehensive Rewarding Mechanism**

## 📋 **Table of Contents**
1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Reward Calculation Process](#reward-calculation-process)
4. [Penalty System](#penalty-system)
5. [Bonus System](#bonus-system)
6. [Score Reduction Mechanisms](#score-reduction-mechanisms)
7. [Penalty Burning System](#penalty-burning-system)
8. [Alpha Stake Bonuses](#alpha-stake-bonuses)
9. [Special Miner Bonuses](#special-miner-bonuses)
10. [Quality Control](#quality-control)
11. [Monitoring & Logging](#monitoring--logging)
12. [Configuration Parameters](#configuration-parameters)

---

## 🏗️ **System Overview**

The Polaris Cloud Subnet implements a sophisticated, multi-layered rewarding mechanism that ensures fair distribution of rewards while maintaining network quality and incentivizing optimal performance. The system operates on several key principles:

- **Performance-Based Rewards**: Core rewards tied to actual compute capability
- **Quality Control**: Strict thresholds ensure only qualified miners participate
- **Penalty System**: Reduces rewards for non-compliant resources
- **Bonus System**: Rewards additional performance and participation
- **Penalty Burning**: Collected penalties are redistributed to incentivize compliance

---

## 🔧 **Core Components**

### **1. Base Score Calculation**
```
Base Score = (Uptime Score + Container Score) × Tempo Scaling
```
- **Uptime Score**: Reliability component (0-10 points)
- **Container Score**: Activity component (0-10 points)
- **Tempo Scaling**: Time-based normalization factor

### **2. Compute Multiplier**
```
Compute Multiplier = Raw PoW Score
```
- **Minimum Threshold**: PoW ≥ 0.03 required for participation
- **Multiplier Effect**: Higher PoW = higher final scores
- **Quality Gate**: Resources below threshold are completely excluded

### **3. Final Score Formula**
```
Final Score = Base Score × Compute Multiplier × Bonus Multipliers
```

---

## 🎯 **Reward Calculation Process**

### **Step 1: Resource Validation**
1. **Hotkey Verification**: Ensure miner authenticity
2. **PoW Threshold Check**: Verify PoW ≥ 0.03
3. **Resource Authentication**: Validate compute resources
4. **Uptime Calculation**: Measure availability over time

### **Step 2: Base Score Computation**
1. **Uptime Analysis**: Calculate percentage uptime
2. **Container Monitoring**: Count active containers
3. **Tempo Scaling**: Apply time-based normalization
4. **Base Score Generation**: Combine reliability and activity

### **Step 3: Compute Multiplication**
1. **PoW Application**: Use raw PoW as multiplier
2. **Threshold Enforcement**: Exclude resources below 0.03
3. **Score Amplification**: Higher PoW = higher rewards

### **Step 4: Bonus Application**
1. **Uptime Bonuses**: +5% to +15% for high availability
2. **Container Bonuses**: +8% to +20% for active work
3. **Alpha Stake Bonuses**: +10% to +20% for network participation

### **Step 5: Penalty Application**
1. **Allow Mining Check**: Verify resource mining permissions
2. **Penalty Calculation**: Apply 30% reduction for non-compliant resources
3. **Penalty Tracking**: Accumulate penalties for redistribution

---

## ⚠️ **Penalty System**

### **Allow Mining Penalty**
- **Trigger**: Resource has `allow_mining: false`
- **Reduction**: 30% score reduction
- **Formula**: `Penalized Score = Original Score × 0.7`
- **Purpose**: Incentivize proper resource configuration

### **Penalty Calculation**
```python
if not allow_mining:
    original_score = resource_score
    penalty_amount = original_score - (original_score * 0.7)
    resource_score = resource_score * 0.7  # 30% reduction
    total_penalty_amount += penalty_amount
```

### **Penalty Tracking**
- **Accumulation**: All penalties are summed across all resources
- **Logging**: Detailed penalty tracking for transparency
- **Redistribution**: Penalties are burned and redistributed

---

## 🎁 **Bonus System**

### **1. Uptime Bonuses**
- **High Uptime (95-100%)**: +15% bonus
- **Medium Uptime (85-94%)**: +10% bonus
- **Good Uptime (75-84%)**: +5% bonus
- **Low Uptime (<75%)**: No bonus

### **2. Container Bonuses**
- **High Activity (5+ containers)**: +20% bonus
- **Medium Activity (2-4 containers)**: +15% bonus
- **Low Activity (1 container)**: +8% bonus
- **No Activity (0 containers)**: No bonus

### **3. Alpha Stake Bonuses**
- **High Tier (≥5000 Alpha)**: +20% bonus
- **Medium Tier (≥1000 Alpha)**: +10% bonus
- **Low Tier (<1000 Alpha)**: No bonus

### **4. Rented Machine Bonus**
- **Rented Resources**: +0% bonus (neutral)
- **Owned Resources**: +0% bonus (neutral)
- **Purpose**: Equal treatment regardless of ownership

---

## 📉 **Score Reduction Mechanisms**

### **1. Allow Mining Reduction**
- **Reduction**: 30% of original score
- **Reason**: Resource not configured for mining
- **Impact**: Significant score reduction to incentivize compliance

### **2. Threshold Filtering**
- **PoW < 0.03**: Complete exclusion from rewards
- **Purpose**: Maintain network quality standards
- **Effect**: No rewards, no bonuses, no participation

### **3. Fallback Score Reduction**
- **Trigger**: When primary scoring fails
- **Reduction**: Same 30% penalty applies to fallback scores
- **Consistency**: Ensures penalty system works across all scoring methods

---

## 🔥 **Penalty Burning System**

### **Penalty Collection**
- **Source**: All penalties from `allow_mining: false` resources
- **Accumulation**: Sum of all penalty amounts across the network
- **Tracking**: Real-time penalty amount calculation

### **Penalty Redistribution**
- **Method**: Penalties are burned and redistributed
- **Recipient**: Special miner receives penalty summation bonus
- **Purpose**: Incentivize compliance and reward network participation
- **Transparency**: All penalty amounts are logged and tracked

### **Penalty Burning Process**
```python
if total_penalty_amount > 0:
    # Find special miner in results
    for miner_id, result in results.items():
        miner_uid = result.get("miner_uid")
        if miner_uid and str(miner_uid) == "SPECIAL_UID":
            original_score = result.get("total_score", 0.0)
            bonus_score = total_penalty_amount
            result["total_score"] = original_score + bonus_score
            break
```

---

## 💎 **Alpha Stake Bonuses**

### **Stake Tier System**
- **High Tier**: ≥5000 Alpha tokens → +20% bonus
- **Medium Tier**: ≥1000 Alpha tokens → +10% bonus
- **Low Tier**: <1000 Alpha tokens → No bonus

### **Stake Bonus Calculation**
```python
if alpha_stake >= 5000:
    bonus_multiplier = 1.20  # 20% bonus
elif alpha_stake >= 1000:
    bonus_multiplier = 1.10  # 10% bonus
else:
    bonus_multiplier = 1.00  # No bonus
```

### **Stake Bonus Application**
- **Additive**: Bonuses are added to existing scores
- **Transparent**: All stake bonuses are logged
- **Fair**: Bonuses enhance but don't replace performance

---

## 🎯 **Special Miner Bonuses**

### **Special Miner (UID 44)**
- **Base Bonus**: 60% of total rewarded scores
- **Penalty Bonus**: Additional bonus from penalty summation
- **Additive System**: Penalty bonus added to base bonus
- **Purpose**: Reward network participation and compliance


## ✅ **Quality Control**

### **Performance Thresholds**
- **PoW ≥ 0.03**: Required for any participation
- **PoW < 0.03**: Complete exclusion from rewards
- **No Exceptions**: Cannot buy rewards with stake alone

### **Resource Validation**
- **Hotkey Verification**: Ensure miner authenticity
- **Resource Authentication**: Validate compute resources
- **Uptime Monitoring**: Track availability and reliability
- **Container Management**: Monitor active work performance

### **Quality Metrics**
- **Gini Coefficient**: Measures score distribution fairness
- **Coefficient of Variation**: Indicates score spread
- **Performance Tiers**: High, medium, and low performer categories
- **Fairness Assessment**: Overall system fairness evaluation

---

## 📊 **Monitoring & Logging**

### **Detailed Logging**
- **Resource Scoring**: Step-by-step score calculation
- **Penalty Tracking**: Detailed penalty application and accumulation
- **Bonus Application**: All bonus calculations and applications
- **Final Scores**: Complete score breakdown and final values

### **Performance Metrics**
- **Processing Time**: Per-miner and total execution time
- **Resource Counts**: Verified and filtered resource statistics
- **Score Distribution**: Raw and normalized score ranges
- **Bonus Impact**: Applied bonus multiplier statistics

### **Transparency Features**
- **Calculation Steps**: Detailed scoring breakdown
- **Error Context**: Comprehensive error information
- **Data Validation**: Input parameter verification
- **Fallback Usage**: Alternative calculation tracking

---

## ⚙️ **Configuration Parameters**

### **Core Parameters**
```python
SCORE_THRESHOLD = 0.03  # Minimum PoW for participation
ALLOW_MINING_PENALTY = 0.7  # 30% reduction for allow_mining=False
ALPHA_STAKE_HIGH_TIER = 5000  # High tier threshold
ALPHA_STAKE_MEDIUM_TIER = 1000  # Medium tier threshold
```

### **Bonus Multipliers**
```python
UPTIME_BONUS_HIGH = 1.15  # +15% for high uptime
UPTIME_BONUS_MEDIUM = 1.10  # +10% for medium uptime
UPTIME_BONUS_LOW = 1.05  # +5% for low uptime
CONTAINER_BONUS_HIGH = 1.20  # +20% for high activity
CONTAINER_BONUS_MEDIUM = 1.15  # +15% for medium activity
CONTAINER_BONUS_LOW = 1.08  # +8% for low activity
```

### **Special Bonuses**
```python
UID_44_BONUS_PERCENTAGE = 0.60  # 60% bonus for special miner
ALPHA_STAKE_BONUS_HIGH = 1.20  # +20% for high stake
ALPHA_STAKE_BONUS_MEDIUM = 1.10  # +10% for medium stake
```

---

## 🔄 **System Flow**

### **Complete Reward Process**
1. **Resource Discovery**: Identify all available compute resources
2. **Validation**: Verify hotkeys, PoW scores, and resource authenticity
3. **Base Scoring**: Calculate uptime and container scores
4. **Compute Multiplication**: Apply PoW multipliers
5. **Bonus Application**: Add uptime, container, and stake bonuses
6. **Penalty Application**: Reduce scores for non-compliant resources
7. **Penalty Collection**: Accumulate all penalty amounts
8. **Special Bonuses**: Apply special miner bonuses
9. **Penalty Redistribution**: Burn penalties and redistribute to special miner
10. **Final Normalization**: Scale scores to final reward range
11. **Weight Calculation**: Convert scores to network weights

### **Error Handling**
- **Graceful Degradation**: System continues with partial data
- **Fallback Scoring**: Alternative methods when primary fails
- **Silent Failures**: Non-critical errors don't interrupt processing
- **Comprehensive Logging**: All errors and fallbacks are tracked

---

## 🎯 **Key Features Summary**

### **✅ Fairness Mechanisms**
- Performance-based core rewards
- Transparent calculation processes
- Balanced bonus systems
- Penalty redistribution

### **✅ Quality Control**
- Strict PoW thresholds
- Resource validation
- Hotkey verification
- Uptime monitoring

### **✅ Penalty System**
- 30% reduction for non-compliant resources
- Penalty accumulation and tracking
- Penalty burning and redistribution
- Transparent penalty logging

### **✅ Bonus System**
- Uptime-based bonuses
- Container activity bonuses
- Alpha stake bonuses
- Special miner bonuses


---

## 🚀 **System Benefits**

### **For Miners**
- **Clear Performance Metrics**: Understand exactly how rewards are calculated
- **Fair Competition**: Performance-based rewards ensure fair competition
- **Bonus Opportunities**: Multiple ways to earn additional rewards
- **Quality Incentives**: Penalties encourage proper resource configuration

### **For Network**
- **Quality Assurance**: Strict thresholds maintain network quality
- **Penalty Redistribution**: Penalties are burned and redistributed
- **Transparent Operations**: All calculations are logged and verifiable
- **Sustainable Growth**: Balanced system prevents reward inflation

### **For Validators**
- **Comprehensive Monitoring**: Detailed logging and metrics
- **Error Handling**: Robust error handling and fallback mechanisms
- **Performance Optimization**: Efficient processing and resource management
- **Extensibility**: Modular design allows for future enhancements

---

**🎯 The Polaris Cloud Subnet rewarding mechanism represents a sophisticated, fair, and transparent system that incentivizes quality network participation while maintaining sustainability and transparency.**

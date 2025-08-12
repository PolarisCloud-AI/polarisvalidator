# 🎯 **Polaris Validator Reward Mechanism - Technical Documentation**

## 📋 **Table of Contents**
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Reward Calculation](#reward-calculation)
5. [Bonus Systems](#bonus-systems)
6. [Scoring Algorithm](#scoring-algorithm)
7. [Configuration Parameters](#configuration-parameters)
8. [API Functions](#api-functions)
9. [Error Handling](#error-handling)
10. [Performance Considerations](#performance-considerations)
11. [Monitoring & Logging](#monitoring--logging)

## 🚀 **Overview**

The Polaris Validator Reward Mechanism is a sophisticated, multi-layered scoring and reward system designed to fairly evaluate and incentivize miners based on their computational performance, uptime reliability, and network contribution. The system implements a **strict threshold-based approach** where only miners meeting performance requirements can participate, ensuring network quality while providing fair rewards.

### **Key Features**
- **Strict performance threshold**: Only PoW ≥ 0.03 miners can participate
- **Multiplier-based scoring** with compute power as the primary multiplier
- **Base reliability scoring** for uptime and container management
- **Tiered bonus systems** for uptime and container management
- **Alpha stake incentives** for qualified miners only
- **Threshold-based filtering** for quality control
- **Real-time monitoring** and comprehensive logging
- **Graceful error handling** and fallback mechanisms

## 🏗️ **System Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Reward Mechanism Engine                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Miner     │  │  Compute    │  │   Uptime    │            │
│  │  Discovery  │  │  Resources  │  │  Tracking   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Scoring   │  │   Bonus     │  │  Validation │            │
│  │   Engine    │  │   Systems   │  │   & Filter  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Score       │  │  Alpha      │  │  Final      │            │
│  │ Normalize   │  │  Stake      │  │  Aggregat.  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 **Core Components**

### **1. Miner Processing Engine**
- **Function**: `reward_mechanism()`
- **Purpose**: Main orchestrator for the entire reward calculation process
- **Input**: List of allowed UIDs, network parameters, tempo settings
- **Output**: Processed miner results and uptime rewards

### **2. Resource Scoring System**
- **Function**: `calculate_fair_resource_score()`
- **Purpose**: Core scoring algorithm with multiplier-based approach
- **Components**: Base reliability score × Compute multiplier × Bonuses
- **Output**: Normalized resource score

### **3. Bonus Calculation Engines**
- **Uptime Multiplier**: `calculate_uptime_multiplier()`
- **Container Bonus**: `calculate_rented_machine_bonus()`
- **Alpha Stake**: `apply_alpha_stake_bonus()`

### **4. Data Validation & Filtering**
- **Hotkey Verification**: Ensures miner authenticity
- **Resource Validation**: Filters verified compute resources
- **Threshold Filtering**: Excludes resources with PoW < 0.03

## 📊 **Reward Calculation**

### **Strict Threshold System**
```python
# 1. PoW Threshold Check (REQUIRED for any participation)
if pog_score < SCORE_THRESHOLD:  # 0.03
    logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold - SKIPPING ENTIRELY")
    continue  # Skip this resource entirely - no processing, no bonuses

# 2. Only miners above threshold get scored and receive bonuses
```

### **Multiplier-Based Formula (Only for Qualified Miners)**
```python
# Base Score Components (Reliability + Activity)
uptime_score = (uptime_percent / 100) * 10                    # 0-10 scale
container_score = min(containers, MAX_CONTAINERS) * 0.5        # 0-10 scale (max 20 containers)

# Base Score: combination of reliability and activity
base_score = uptime_score + container_score                    # 0-20 scale

# Apply tempo scaling
tempo_scaled_score = base_score * (tempo / 3600) * 10         # Compensate for tempo reduction

# Apply compute multiplier: Raw PoW score represents compute specs/power
compute_multiplier = PoW_score                                 # Direct PoW score as multiplier

# Final Score: Base reliability × Compute power × Bonuses
final_score = tempo_scaled_score * compute_multiplier * uptime_multiplier * rented_machine_bonus
```

### **Key System Behavior**
- **PoW ≥ 0.03**: Full scoring + uptime bonus + container bonus + stake bonus
- **PoW < 0.03**: **Nothing - completely excluded from the system**
- **No exceptions**: Can't buy rewards with stake alone

### **Score Normalization**
```python
# 75th percentile normalization for better distribution
if len(raw_scores) >= 5:
    normalization_reference = np.percentile(raw_scores, 75)
elif len(raw_scores) >= 3:
    normalization_reference = np.percentile(raw_scores, 80)
else:
    normalization_reference = max(raw_scores)

# Logarithmic scaling with soft cap
normalization_factor = MAX_SCORE / (normalization_reference * np.log1p(1))
scaled_score = raw_score * np.log1p(normalization_factor)

# Soft cap application above 80% of MAX_SCORE
if scaled_score > MAX_SCORE * 0.8:
    falloff_factor = 1.0 - ((scaled_score - MAX_SCORE * 0.8) / (MAX_SCORE * 0.2)) * 0.2
    scaled_score = scaled_score * falloff_factor

normalized_score = min(MAX_SCORE, max(0, scaled_score))
```

## 🎁 **Bonus Systems**

### **Important: All Bonuses Only Apply to Qualified Miners (PoW ≥ 0.03)**

### **1. Uptime Multiplier Tiers**
```python
UPTIME_MULTIPLIER_TIERS = {
    "excellent": {"threshold": 95.0, "multiplier": 1.15},  # ≥95% uptime: +15% bonus
    "good": {"threshold": 85.0, "multiplier": 1.10},       # ≥85% uptime: +10% bonus
    "average": {"threshold": 70.0, "multiplier": 1.05},    # ≥70% uptime: +5% bonus
    "poor": {"threshold": 0.0, "multiplier": 1.0}          # <70% uptime: No bonus
}
```

### **2. Rented Machine Bonus**
```python
RENTED_MACHINE_BONUS = {
    "base_multiplier": 1.08,      # +8% base bonus for having containers
    "container_scaling": 0.01,    # +1% per additional container beyond 1
    "max_bonus": 1.20            # Maximum 20% bonus for high container counts
}

# Calculation
if active_container_count == 0:
    bonus_multiplier = 1.0
else:
    bonus_multiplier = base_multiplier
    if active_container_count > 1:
        additional_bonus = min(
            (active_container_count - 1) * container_scaling,
            max_bonus - base_multiplier
        )
        bonus_multiplier += additional_bonus
    return min(bonus_multiplier, max_bonus)
```

### **3. Alpha Stake Bonus**
```python
ALPHA_STAKE_TIERS = {
    "high": {"threshold": 5000, "bonus_percentage": 20},      # ≥5000 Alpha: +20% bonus
    "medium": {"threshold": 1000, "bonus_percentage": 10},    # ≥1000 Alpha: +10% bonus
    "low": {"threshold": 0, "bonus_percentage": 0}            # <1000 Alpha: No bonus
}

# Bonus Application (ONLY for miners with PoW ≥ 0.03)
bonus_multiplier = 1.0 + (bonus_percentage / 100)
final_score = base_score * bonus_multiplier
```

## ⚖️ **Scoring Algorithm**

### **Resource Processing Flow**
1. **Discovery**: Fetch miner data from API endpoints
2. **Validation**: Verify hotkeys and resource authenticity
3. **Threshold Filtering**: **Exclude resources with PoW < 0.03**
4. **Base Scoring**: Calculate reliability score (uptime + containers) for qualified miners only
5. **Compute Multiplication**: Apply PoW score as multiplier for qualified miners only
6. **Bonus Application**: Add tiered bonuses for excellence (qualified miners only)
7. **Normalization**: Scale scores to target range
8. **Final Output**: Generate reward distribution for qualified miners only

### **Quality Control Mechanisms**
- **SCORE_THRESHOLD**: 0.03 minimum PoW score for **any participation**
- **Resource Validation**: Must pass monitoring checks
- **Hotkey Verification**: Ensures miner authenticity
- **Status Filtering**: Only processes verified, active resources
- **Performance Gate**: PoW ≥ 0.03 is the **absolute requirement**

## ⚙️ **Configuration Parameters**

### **Core Scoring Parameters**
```python
SCORE_THRESHOLD = 0.03           # Minimum PoW score for ANY participation
MAX_CONTAINERS = 20              # Maximum containers for scoring
SCORE_WEIGHT = 0.4               # Base score weight multiplier
MAX_SCORE = 500.0                # Maximum normalized score
```

### **Bonus Calibration**
```python
# Uptime bonuses (calibrated to prevent excessive bonuses)
"excellent": 1.15x (+15%)        # Was 1.30x (+30%)
"good": 1.10x (+10%)            # Was 1.20x (+20%)
"average": 1.05x (+5%)          # Was 1.10x (+10%)

# Container bonuses (calibrated to prevent excessive bonuses)
"base_multiplier": 1.08 (+8%)   # Was 1.15 (+15%)
"max_bonus": 1.20 (+20%)        # Was 1.35 (+35%)
```

### **Network Configuration**
```python
SUPPORTED_NETWORKS = ["finney", "mainnet", "test"]
DEFAULT_TEMPO = 4320            # 72 minutes in seconds
DEFAULT_NETUID = 49             # Subnet identifier
```

## 🔌 **API Functions**

### **Main Reward Mechanism**
```python
async def reward_mechanism(
    allowed_uids: List[int],
    netuid: int = 49,
    network: str = "finney",
    tempo: int = 4320,
    max_score: float = 500.0,
    current_block: int = 0
) -> Tuple[Dict[str, MinerResult], Dict[str, UptimeReward]]
```

### **Scoring Functions**
```python
def calculate_fair_resource_score(
    uptime_percent: float,
    scaled_compute_score: float,
    active_container_count: int,
    tempo: int,
    uptime_multiplier: float = 1.0,
    rented_machine_bonus: float = 1.0
) -> float

def calculate_uptime_multiplier(uptime_percent: float) -> float
def calculate_rented_machine_bonus(active_container_count: int) -> float
def apply_alpha_stake_bonus(rewards: Dict, uid_stake_info: Dict) -> Dict
```

### **Utility Functions**
```python
def safe_convert_to_float(value, default=0.0) -> float
def get_miner_uid_by_hotkey(hotkey: str, netuid: int, network: str) -> Optional[int]
def get_uid_alpha_stake_info(uid: int, metagraph, subtensor) -> Dict
```

## 🛡️ **Error Handling**

### **Graceful Degradation**
- **Resource Processing**: Continues on individual failures
- **API Failures**: Falls back to cached data
- **Scoring Errors**: Uses fallback calculations
- **Bonus Failures**: Applies default multipliers

### **Fallback Mechanisms**
```python
try:
    # Primary calculation
    resource_score = calculate_fair_resource_score(...)
except Exception as e:
    logger.warning(f"Error calculating resource score: {e}")
    # Fallback calculation
    fallback_score = (uptime_percent / 100) * 40 + compute_score * 0.4 + container_score * 0.2
    fallback_score = fallback_score * (tempo / 3600) * uptime_multiplier * rented_machine_bonus
```

### **Data Validation**
- **Type Checking**: Safe conversion of Bittensor objects
- **Range Validation**: Ensures parameters within expected bounds
- **Null Handling**: Graceful handling of missing data
- **Format Validation**: Robust parsing of various data formats

## 🚀 **Performance Considerations**

### **Optimization Strategies**
- **Async Processing**: Concurrent resource processing
- **Caching**: Hotkey-to-UID mapping cache
- **Batch Operations**: Aggregated data processing
- **Early Filtering**: Threshold-based resource exclusion

### **Resource Management**
- **Memory Efficiency**: Streaming data processing
- **Network Optimization**: Minimized API calls
- **CPU Utilization**: Balanced scoring calculations
- **I/O Optimization**: Efficient file operations

## 📊 **Monitoring & Logging**

### **Comprehensive Logging**
```python
# Threshold filtering
logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold - SKIPPING ENTIRELY")

# Base score components
logger.info(f"⚖️  BASE SCORE COMPONENTS:")
logger.info(f"  Uptime Score (Reliability): {uptime_score:.2f}")
logger.info(f"  Container Score (Activity): {container_score:.2f}")
logger.info(f"  Base Score: {uptime_score + container_score:.2f}")

# Compute multiplier and bonus calculations
logger.info(f"🚀 COMPUTE & BONUS CALCULATIONS:")
logger.info(f"  Compute Multiplier (PoW): {compute_multiplier:.4f}x")
logger.info(f"  Uptime Multiplier: {uptime_multiplier:.2f}x")
logger.info(f"  Rented Machine Bonus: {rented_machine_bonus:.2f}x")

# Final score breakdown
logger.info(f"🏆 FINAL SCORE BREAKDOWN:")
logger.info(f"  Base Score (Reliability + Activity): {base_score:.2f}")
logger.info(f"  With Compute Multiplier: {tempo_scaled * compute_multiplier:.2f}")
logger.info(f"  Final Score (with bonuses): {final_score:.2f}")
```

### **Performance Metrics**
- **Processing Time**: Per-miner and total execution time
- **Resource Counts**: Verified and filtered resource statistics
- **Score Distribution**: Raw and normalized score ranges
- **Bonus Impact**: Applied bonus multiplier statistics

### **Debug Information**
- **Calculation Steps**: Detailed scoring breakdown
- **Error Context**: Comprehensive error information
- **Data Validation**: Input parameter verification
- **Fallback Usage**: Alternative calculation tracking

## 🔍 **Troubleshooting**

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
            f"compute={scaled_compute_score:.2f}, containers={active_container_count}, "
            f"uptime_mult={uptime_multiplier:.2f}, rented_bonus={rented_machine_bonus:.2f}, "
            f"final_score={final_score:.2f}")
```

## 📈 **Future Enhancements**

### **Planned Improvements**
- **Dynamic Weighting**: Adaptive scoring based on network conditions
- **Machine Learning**: Predictive performance modeling
- **Advanced Analytics**: Real-time fairness metrics
- **Performance Optimization**: Enhanced async processing

### **Extensibility**
- **Plugin Architecture**: Modular bonus system
- **Configuration API**: Runtime parameter adjustment
- **Custom Metrics**: User-defined scoring factors
- **Integration Hooks**: External system connectivity

---

**Documentation Version**: 2.1  
**Last Updated**: 2025-08-12  
**Maintainer**: Polaris Validator Team  
**Key Features**: 
- Strict PoW ≥ 0.03 threshold for any participation
- All bonuses only apply to qualified miners
- No exceptions - performance is the gatekeeper

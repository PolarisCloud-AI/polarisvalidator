# Miner Attributes Used in Validation and Rewarding Mechanism

Based on the analysis of the reward mechanism code, here are all the attributes that are read from each miner for validation and rewarding:

## 📊 **Core Miner Attributes**

### **1. Basic Miner Information**
```python
# From miner object
miner.get("miner_id")                    # Miner identifier
miner.get("resource_details", [])        # List of compute resources
```

### **2. Bittensor Details**
```python
# From miner["bittensor_details"]
miner["bittensor_details"].get("miner_uid")  # Bittensor UID
miner["bittensor_details"].get("hotkey")     # Miner's hotkey
```

## 🔧 **Resource-Level Attributes**

### **3. Resource Basic Information**
```python
# From each resource in resource_details
resource.get("id")                       # Resource identifier
resource.get("validation_status")        # "verified" or other status
```

### **4. Monitoring Status (Critical for Validation)**
```python
# From resource["monitoring_status"]
monitoring_status.get("conn", {}).get("status")      # Connection status ("ok" required)
monitoring_status.get("auth", {}).get("status")      # Authentication status ("ok" required)
monitoring_status.get("docker", {}).get("running")   # Docker running status
monitoring_status.get("docker", {}).get("user_group") # Docker user group
```

### **5. Proof of Work (PoW) Score**
```python
# From resource["monitoring_status"]["pow"]
monitoring_status.get("pow", {}).get("total", 0.0)   # Total PoW score (main scoring metric)
```

## 📈 **Scoring and Rewarding Attributes**

### **6. Container Information**
```python
# From external API call to get_containers_for_resource()
containers.get("running_count", 0)       # Number of running containers
containers.get("total_count", 0)         # Total container count
```

### **7. Historical Data (From Logs)**
```python
# From uptime logs
log.get("status")                        # "active", "inactive", "initial_active"
log.get("block_number")                  # Block number for uptime calculation
log.get("compute_score")                 # Historical compute score
log.get("uptime_reward")                 # Historical uptime reward
```

### **8. Payment History**
```python
# From payment logs
payment_log.get("block_number")           # Last rewarded block
payment_log.get("uptime")                 # Previous uptime value
payment_log.get("reward_amount")          # Previous reward amount
```

## 🎯 **Validation Criteria**

### **Required for Processing:**
1. ✅ **miner_uid** must exist and be in allowed_uids list
2. ✅ **hotkey** must be valid and match subnet UID
3. ✅ **validation_status** must be "verified"
4. ✅ **conn.status** must be "ok"
5. ✅ **auth.status** must be "ok"
6. ✅ **pow.total** must be >= SCORE_THRESHOLD (0.03)
7. ✅ **pow.total** must be <= MAX_POW_SCORE (1.0)

### **Scoring Factors:**
1. **PoW Score**: `monitoring_status.pow.total` (primary metric)
2. **Uptime**: Calculated from historical logs
3. **Container Count**: `running_count` from containers API
4. **Tempo**: Block interval parameter
5. **Historical Uptime**: For uptime multiplier calculation

## 🔄 **Data Flow Summary**

```
Miner Object
├── Basic Info (miner_id, resource_details)
├── Bittensor Details (miner_uid, hotkey)
└── Resource Details
    ├── Resource Info (id, validation_status)
    ├── Monitoring Status (conn, auth, docker, pow)
    ├── Container Info (from external API)
    └── Historical Data (from logs)
```

## 📋 **Key Validation Steps**

1. **UID Validation**: Check if miner_uid is in allowed_uids
2. **Hotkey Verification**: Verify hotkey matches subnet UID
3. **Resource Validation**: Check validation_status = "verified"
4. **Monitoring Checks**: Verify conn.status = "ok" and auth.status = "ok"
5. **Score Thresholds**: Ensure PoW score is within valid range
6. **Container Verification**: Get running container count
7. **Historical Analysis**: Calculate uptime from logs
8. **Reward Calculation**: Apply scoring formula with bonuses

## 🎯 **Final Score Calculation**

The final score combines:
- **Uptime Score**: Based on historical uptime percentage
- **Compute Score**: Raw PoW score as multiplier
- **Container Score**: Based on running container count
- **Uptime Multiplier**: Bonus for high uptime
- **Rented Machine Bonus**: Bonus for active containers
- **Tempo Scaling**: Adjusted for block interval

All these attributes work together to determine each miner's validation status and reward amount.



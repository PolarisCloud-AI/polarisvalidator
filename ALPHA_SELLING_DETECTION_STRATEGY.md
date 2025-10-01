# 🎯 Alpha Token Selling Detection Strategy

## 🚨 Problem with Current System

The current "alpha overselling" penalty system is **incorrectly targeting legitimate miners** who:
- Provide good compute resources
- Earn high scores naturally through performance
- Have high emission/stake ratios due to legitimate mining

**This is NOT detecting actual Alpha token selling behavior.**

## 🎯 What We Should Actually Detect

### **Real Alpha Token Selling Indicators:**

1. **Rapid Stake Decreases**
   - Miners who consistently reduce their Alpha stake
   - Pattern: High stake → Low stake over time
   - Threshold: >20% stake reduction over 24-48 hours

2. **Stake-to-Emission Mismatch**
   - Miners with high emissions but decreasing stake
   - Pattern: Emissions increasing while stake decreasing
   - This indicates they're earning rewards but selling their Alpha tokens

3. **Suspicious Trading Patterns**
   - Miners who maintain low stake despite earning high rewards
   - Pattern: High compute scores but minimal Alpha stake retention
   - Threshold: <100 Alpha tokens despite earning >50% of max rewards

4. **Withdrawal Behavior**
   - Miners who withdraw rewards immediately after earning
   - Pattern: Rewards earned → Immediately withdrawn (not restaked)
   - This suggests they're selling rather than holding/staking

## 🔧 Proposed New Detection System

### **Alpha Selling Detection Algorithm:**

```python
def detect_alpha_selling_violations(metagraph, historical_data):
    violations = []
    
    for uid in active_uids:
        # Get current and historical stake data
        current_stake = metagraph.stake[uid]
        historical_stake = get_historical_stake(uid, 48_hours_ago)
        
        # Calculate stake change
        stake_change = (current_stake - historical_stake) / historical_stake
        
        # Get emission trend
        current_emission = metagraph.emission[uid]
        historical_emission = get_historical_emission(uid, 48_hours_ago)
        emission_change = (current_emission - historical_emission) / historical_emission
        
        # Detection criteria
        if stake_change < -0.20 and current_stake < 100:  # >20% stake decrease + low stake
            violations.append({
                'uid': uid,
                'violation_type': 'alpha_selling',
                'stake_change': stake_change,
                'current_stake': current_stake,
                'severity': 'high' if stake_change < -0.50 else 'moderate'
            })
        
        # Additional check: High emissions with decreasing stake
        if emission_change > 0.10 and stake_change < -0.10:
            violations.append({
                'uid': uid,
                'violation_type': 'emission_stake_mismatch',
                'emission_change': emission_change,
                'stake_change': stake_change,
                'severity': 'moderate'
            })
    
    return violations
```

### **Penalty Structure for Alpha Selling:**

```python
ALPHA_SELLING_PENALTIES = {
    'moderate': {
        'stake_reduction': '20-40%',
        'penalty_duration': '24 hours',
        'score_reduction': '30%'
    },
    'high': {
        'stake_reduction': '40-70%', 
        'penalty_duration': '48 hours',
        'score_reduction': '60%'
    },
    'extreme': {
        'stake_reduction': '>70%',
        'penalty_duration': '96 hours', 
        'score_reduction': '80%'
    }
}
```

## 🎯 Implementation Strategy

### **Phase 1: Remove Current System**
- Disable the current "alpha overselling" penalty system
- This will stop penalizing legitimate high-performance miners

### **Phase 2: Implement Alpha Selling Detection**
- Track historical stake changes over time
- Monitor emission vs stake trends
- Detect actual selling behavior patterns

### **Phase 3: Graduated Penalties**
- Apply penalties only to miners who are actually selling Alpha tokens
- Use stake reduction patterns as primary indicator
- Implement appeal mechanism for false positives

## 📊 Expected Impact

### **Current System Problems:**
- ❌ Penalizes legitimate high-performance miners
- ❌ Doesn't detect actual Alpha token selling
- ❌ Creates false positives for good miners
- ❌ Reduces network performance incentives

### **New System Benefits:**
- ✅ Targets actual Alpha token sellers
- ✅ Protects legitimate high-performance miners
- ✅ Encourages Alpha token retention
- ✅ Maintains network performance incentives

## 🔍 Detection Criteria Summary

**Target These Behaviors:**
1. **Stake Reduction**: >20% stake decrease over 48 hours
2. **Low Stake Retention**: <100 Alpha tokens despite high earnings
3. **Emission-Stake Mismatch**: High emissions with decreasing stake
4. **Withdrawal Patterns**: Immediate reward withdrawal without restaking

**Do NOT Target:**
1. High emission/stake ratios from good performance
2. New miners with low initial stake
3. Miners who earn high scores legitimately
4. Miners who maintain or increase their stake

## 🎯 Recommendation

**Immediately disable the current penalty system** and implement the new Alpha selling detection system that focuses on actual selling behavior rather than performance-based ratios.

This will:
- Stop penalizing legitimate miners like UID 107
- Actually detect and penalize Alpha token sellers
- Maintain network performance incentives
- Encourage Alpha token retention and staking


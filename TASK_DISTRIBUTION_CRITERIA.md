# Task Distribution Criteria

This document outlines all the criteria used for distributing tasks to miners in the Violet subnet.

## 📋 Overview

The task distribution system uses a multi-factor scoring algorithm to select the best miners for each task. The system operates at two levels:

1. **Proxy Server Level** (`TaskDistributor` & `WorkflowOrchestrator`) - For user-submitted tasks
2. **Validator Level** (`MinerTracker`) - For validator scan tasks

---

## 🎯 Core Distribution Criteria

### 1. **Basic Eligibility Requirements**

A miner must meet these basic requirements to be considered for task distribution:

#### ✅ **Serving Status**
- `is_serving = True` - Miner must be actively serving requests
- Miner's axon must be accessible and responding

#### ✅ **Capacity Check**
- `current_load < max_capacity` - Miner must have available capacity
- Default `max_capacity = 5` concurrent tasks per miner
- Prevents overloading miners

#### ✅ **Recency Check**
- Miner must have been seen recently (within timeout period)
- **Miner Timeout**: 900 seconds (15 minutes)
- **Validator Timeout**: 600 seconds (10 minutes)
- Stale miners are automatically excluded

#### ✅ **Stake Requirement**
- Miner must have `stake > 0` (for consensus-based selection)
- Higher stake indicates more network commitment

---

## 📊 Scoring Algorithms

### **Proxy Server: Availability Score** 
*(Used by `MinerStatusManager`)*

The availability score is calculated using a weighted combination:

```python
availability_score = (
    performance_score * 0.4 +    # 40% - Historical performance
    load_factor * 0.3 +          # 30% - Current capacity
    stake_factor * 0.2 +         # 20% - Network stake
    recency_factor * 0.1         # 10% - Last seen time
)
```

#### **Performance Score (40%)**
- Historical performance metric (0.0 to 1.0)
- Based on past task completion rates and quality
- Higher performance = higher priority

#### **Load Factor (30%)**
```python
load_factor = 1.0 - (current_load / max_capacity)
```
- Lower current load = higher score
- Rewards miners with available capacity
- Prevents overloading busy miners

#### **Stake Factor (20%)**
```python
stake_factor = min(1.0, stake / 1000.0)  # Normalized to 0-1
```
- Higher stake = higher score
- Indicates network commitment and trust
- Normalized to 1000 TAO maximum

#### **Recency Factor (10%)**
```python
recency_factor = 1.0 - (seconds_since_last_seen / miner_timeout)
```
- More recently seen = higher score
- Ensures active miners are prioritized
- Decays over time

---

### **Validator: Composite Score**
*(Used by `MinerTracker`)*

The validator uses a more sophisticated scoring system:

```python
composite_score = (
    stake_score * 0.3 +              # 30% - Relative stake
    performance_score * 0.4 +        # 40% - Task-specific performance
    availability_score * 0.2 +      # 20% - Current availability
    specialization_bonus * 0.1      # 10% - Task type specialization
)
```

#### **Stake Score (30%)**
```python
stake_score = miner.stake / max_stake_in_network
```
- Normalized relative to highest stake in network
- Rewards miners with higher network investment

#### **Performance Score (40%)**
- Task-specific performance metric
- Calculated from:
  - Success rate (40% weight)
  - Speed score (30% weight)
  - Recent performance bonus (20% weight)
  - Specialization bonus (10% weight)
  - Load penalty (subtracted)

#### **Availability Score (20%)**
```python
availability_score = 1.0 - (current_load / max_concurrent_tasks)
```
- Based on current load vs. maximum capacity
- More available = higher score

#### **Specialization Bonus (10%)**
```python
if task_type in miner.task_type_performance:
    if task_perf['total'] >= 3:  # Minimum 3 samples
        specialization_bonus = task_perf['success_rate'] * 0.1
```
- Bonus for miners with proven expertise in specific task types
- Requires minimum 3 completed tasks of that type
- Based on success rate for that task type

---

## 🔍 Task Type Specialization

### **Specialization Filtering**

The system prioritizes miners with task type specialization:

1. **Primary Selection**: Miners with matching `task_type_specialization`
2. **Fallback**: If no specialized miners available, all miners are considered
3. **Specialization Types**:
   - `transcription` - Audio transcription tasks
   - `tts` - Text-to-speech synthesis
   - `summarization` - Text summarization
   - `translation` - Text/document translation

### **Specialization Check**
```python
def _can_miner_handle_task(miner, task_type):
    specialization = miner.get('task_type_specialization')
    if not specialization:
        return True  # No specialization = can handle all
    return task_type in specialization
```

---

## 🏆 Multi-Validator Consensus

### **Consensus-Based Selection**

When multiple validators report miner status, the system uses consensus:

#### **Consensus Confidence Threshold**
- Minimum `consensus_confidence >= 0.7` (70%)
- Only miners with high validator agreement are selected
- Reduces risk of selecting unreliable miners

#### **Consensus Boost**
```python
consensus_boost = consensus_confidence * 0.2
availability_score = performance_score * (1 - load/max_capacity) + consensus_boost
```
- Higher consensus confidence = higher availability score
- Rewards miners with consistent validator reports

#### **Consensus Validators**
- Tracks which validators agree on miner status
- More validators = higher confidence
- Used for conflict resolution

---

## 📈 Performance Metrics

### **Performance Score Calculation** *(MinerTracker)*

```python
performance_score = (
    success_rate * 0.4 +           # 40% - Overall success rate
    speed_score * 0.3 +             # 30% - Processing speed
    recent_bonus * 0.2 +            # 20% - Recent performance
    specialization_bonus * 0.1 -   # 10% - Task-specific expertise
    load_penalty                    # Subtracted - Current overload
)
```

#### **Success Rate (40%)**
```python
success_rate = successful_tasks / total_tasks
```
- Overall task completion success rate
- Higher = more reliable miner

#### **Speed Score (30%)**
```python
speed_score = max(0, 1 - (average_processing_time / 30))
```
- Faster processing = higher score
- Baseline: 30 seconds
- Exponential decay for slower miners

#### **Recent Performance Bonus (20%)**
```python
recent_bonus = recent_success_rate * 0.2
```
- Based on last 50 tasks
- Rewards consistent recent performance
- Helps identify improving miners

#### **Load Penalty**
```python
load_penalty = (current_load / max_concurrent_tasks) * 0.1
```
- Subtracted from score
- Penalizes overloaded miners
- Prevents over-assignment

---

## 🎯 Selection Process

### **Step 1: Filter Available Miners**
1. Check `is_serving = True`
2. Verify `current_load < max_capacity`
3. Confirm miner seen within timeout period
4. Filter by task type specialization (if specified)

### **Step 2: Calculate Scores**
1. Calculate availability/composite score for each miner
2. Apply consensus boost (if multi-validator)
3. Apply specialization bonus (if applicable)

### **Step 3: Rank and Select**
1. Sort miners by score (descending)
2. Select top N miners (where N = `required_miner_count`)
3. Default: 3 miners per task
4. Minimum: 1 miner
5. Maximum: 10 miners per task

### **Step 4: Assign Tasks**
1. Create task assignments for selected miners
2. Update miner load counters
3. Track assignment in database
4. Monitor for completion

---

## ⚙️ Configuration Parameters

### **Task Distribution Settings**

```python
# Default miner counts
min_miners_per_task = 1
max_miners_per_task = 10
default_miners_per_task = 3

# Miner capacity
max_concurrent_tasks = 5  # Per miner
max_capacity = 100.0      # Load units

# Timeouts
miner_timeout = 900        # 15 minutes
validator_timeout = 600   # 10 minutes

# Consensus
min_consensus_confidence = 0.7  # 70%

# Distribution intervals
distribution_interval = 30       # 30 seconds
task_check_interval = 5         # 5 seconds
```

---

## 🔄 Load Balancing

### **Dynamic Load Management**

The system continuously monitors and balances miner load:

1. **Load Tracking**: Each miner's `current_load` is updated in real-time
2. **Capacity Limits**: Miners cannot exceed `max_concurrent_tasks`
3. **Automatic Redistribution**: Overloaded miners are deprioritized
4. **Load Decay**: Load decreases as tasks complete

### **Load Factor Impact**

- **Low Load (0-40%)**: Maximum score boost
- **Medium Load (40-70%)**: Moderate score
- **High Load (70-90%)**: Reduced score
- **Overloaded (90-100%)**: Excluded from selection

---

## 🛡️ Duplicate Protection

### **Task Status Checks**

Before distribution, the system verifies:

1. ✅ Task status is `pending` (not `assigned`, `in_progress`, `completed`, `failed`, `cancelled`)
2. ✅ Task not already assigned to miners
3. ✅ No duplicate assignments to same miners

### **Assignment Tracking**

- Each task tracks `assigned_miners` list
- Prevents double-assignment
- Enables retry logic for failed tasks

---

## 📊 Summary

### **Primary Criteria (Weighted)**
1. **Performance** (40%) - Historical success and quality
2. **Load** (30%) - Current capacity and availability
3. **Stake** (20-30%) - Network investment and commitment
4. **Recency** (10%) - Active status and responsiveness
5. **Specialization** (10%) - Task-specific expertise

### **Secondary Factors**
- Consensus confidence (multi-validator)
- Task type matching
- Network health metrics
- Validator agreement

### **Exclusion Criteria**
- Not serving (`is_serving = False`)
- Overloaded (`current_load >= max_capacity`)
- Stale (not seen within timeout)
- Low consensus confidence (< 70%)
- Zero stake (for consensus selection)

---

## 🎯 Best Practices

### **For Miners**
1. Maintain high success rate (> 90%)
2. Keep processing times low (< 10 seconds)
3. Stay within capacity limits
4. Specialize in specific task types
5. Maintain consistent uptime

### **For Validators**
1. Report miner status regularly
2. Provide accurate performance metrics
3. Participate in consensus building
4. Monitor network health

---

**Last Updated**: Based on current codebase analysis
**Version**: 1.0


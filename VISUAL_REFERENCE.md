# LangSmith Dashboard Metrics - Visual Reference Guide

## The Problem Visualized

### What Your Dashboard Saw (Before)

```
LangSmith Dashboard
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Input/Output Tokens Chart              Cost & Tokens Chart      │
│  ┌─────────────────────────┐          ┌─────────────────────────┐│
│  │                         │          │                         ││
│  │      [EMPTY]            │          │      [EMPTY]            ││
│  │                         │          │                         ││
│  │                         │          │                         ││
│  └─────────────────────────┘          └─────────────────────────┘│
│                                                                   │
│  Trace Error Rate Chart                 Evaluator Latency        │
│  ┌─────────────────────────┐          ┌─────────────────────────┐│
│  │                         │          │                         ││
│  │      [EMPTY]            │          │      0.00s ← wrong      ││
│  │                         │          │                         ││
│  │                         │          │                         ││
│  └─────────────────────────┘          └─────────────────────────┘│
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Why empty?** Your metrics were stored in keys the charts don't know how to read.

---

## How LangSmith Reads Dashboard Data

### The Data Flow

```
Your Application
        ↓
    [Calculate Metrics]
    input_tokens = 1844
    output_tokens = 281
    cost = $0.00062315
    error_rate = 0%
        ↓
    [Store in LangSmith]
    run_tree.metadata["???"] = ???
        ↓
    [LangSmith Dashboard]
    ┌──────────────────────────────────────────┐
    │ Does metadata.usage_metadata exist?      │
    │ Does metadata.estimated_cost_usd exist?  │
    │ Does metadata.error_rate exist?          │
    │ (Looking for specific keys)              │
    └──────────────────────────────────────────┘
        ↓
    [Chart Component Decision]
    If keys found → Render chart with data ✅
    If keys NOT found → Render empty chart ❌
```

### Before: Storing in Wrong Keys

```
Your Code (OLD):
    run_tree.metadata["input_tokens"] = 1844          ❌
    run_tree.metadata["output_tokens"] = 281          ❌
    run_tree.metadata["cost"] = 0.00062315            ❌

Dashboard Looks For:
    metadata.usage_metadata.input_tokens              ✗ Not found
    metadata.estimated_cost_usd                       ✗ Not found
    metadata.error_rate (as percentage)               ✗ Not found

Result:
    All checks fail → Charts stay empty ❌
```

### After: Storing in Correct Keys

```
Your Code (NEW):
    run_tree.metadata["usage_metadata"] = {
        "input_tokens": 1844,                        ✅
        "output_tokens": 281,
    }
    run_tree.metadata["estimated_cost_usd"] = 0.00062315  ✅
    run_tree.metadata["error_rate"] = 0.0            ✅

Dashboard Looks For:
    metadata.usage_metadata.input_tokens             ✓ Found!
    metadata.estimated_cost_usd                      ✓ Found!
    metadata.error_rate (as percentage)              ✓ Found!

Result:
    All checks pass → Charts populate with data ✅
```

---

## Metadata Structure Comparison

### Old Structure (Wrong)

```
run.metadata = {
  "input_tokens": 1844,           ❌ Wrong location
  "output_tokens": 281,           ❌ Wrong location
  "total_tokens": 2125,           ❌ Wrong location
  "cost": 0.00062315,             ❌ Wrong location
  "usage_metadata": {             ❌ Missing tokens here
    "input_tokens": 1844,         ❌ Values in wrong format
    "output_tokens": 281,         ❌ Wrong structure
    "total_tokens": 2125,         ❌ Extra field
    "cost": 0.00062315            ❌ Cost shouldn't be here
  },
  "error_rate": 0.0               ❌ Decimal, not percentage
}

Chart Reading:
  Looking for: metadata.usage_metadata.input_tokens
  Result: Found, but...wait, are these the right types?
          Also found metadata.usage_metadata.cost? That's wrong structure
  Confusion → Falls back to empty chart ❌
```

### New Structure (Correct)

```
run.metadata = {
  "usage_metadata": {
    "input_tokens": 1844,         ✅ Correct location + int type
    "output_tokens": 281,         ✅ Correct location + int type
  },
  "estimated_cost_usd": 0.00062315,  ✅ Correct location + separate
  "error_rate": 0.0,              ✅ Correct format (0-100 percentage)
  "execution_count": 5,           ✅ Supporting data
  "error_count": 0,               ✅ Supporting data
  "latency_ms": 4850.02,          ✅ For latency charts
}

Chart Reading:
  Looking for: metadata.usage_metadata.input_tokens
  Result: Found! It's an int: 1844 ✅
  
  Looking for: metadata.estimated_cost_usd
  Result: Found! It's a float: 0.00062315 ✅
  
  Looking for: metadata.error_rate
  Result: Found! It's a percentage: 0.0 ✅
  
  All checks pass → Render charts with data ✅
```

---

## Key Differences: Before → After

### 1. Token Storage Location

```
BEFORE:                          AFTER:
┌────────────────────┐          ┌────────────────────┐
│ run.metadata       │          │ run.metadata       │
├────────────────────┤          ├────────────────────┤
│ input_tokens: 1844 │ ❌        │ usage_metadata:    │
│ output_tokens: 281 │ ❌        │   input_tokens: 1844│ ✅
└────────────────────┘          │   output_tokens: 281│ ✅
                                 └────────────────────┘
```

### 2. Cost Storage Location

```
BEFORE:                          AFTER:
┌────────────────────┐          ┌────────────────────┐
│ run.metadata       │          │ run.metadata       │
├────────────────────┤          ├────────────────────┤
│ cost: 0.00062315   │ ❌        │ estimated_cost_usd:│
│  (sometimes in     │ ❌        │   0.00062315       │ ✅
│   usage_metadata)  │          └────────────────────┘
└────────────────────┘
```

### 3. Error Rate Format

```
BEFORE:                          AFTER:
Run 5 calls, 1 error:           Run 5 calls, 1 error:
  error_rate = 0.2   ❌           error_rate = 20.0  ✅
  (Decimal 0-1)                    (Percentage 0-100)
  
Chart reads error_rate:         Chart reads error_rate:
  0.2 → Shows as 0.2%? ❌         20.0 → Shows as 20% ✅
  Confusing!                      Clear!
```

---

## The Complete Binding Pattern

### Visualization of the Fix

```
                    START WORKFLOW
                         ↓
                  ┌──────────────┐
                  │ Run LLMs     │
                  │ Calculate:   │
                  │ • Tokens     │
                  │ • Cost       │
                  │ • Errors     │
                  └──────────────┘
                         ↓
                  ┌──────────────┐
                  │ Get run_tree │
                  │ from         │
                  │ LangSmith    │
                  └──────────────┘
                         ↓
            ┌────────────┴────────────┐
            ↓                         ↓
      ┌──────────────┐          ┌──────────────┐
      │ Bind Tokens  │          │ Bind Cost    │
      ├──────────────┤          ├──────────────┤
      │ metadata[    │          │ metadata[    │
      │ "usage_      │          │ "estimated_ │
      │ metadata"]   │          │ cost_usd"] = │
      │ = {          │          │ 0.00062315   │
      │ "input...":  │          │              │
      │ int(1844),   │          │ ✅ Correct! │
      │ "output...": │          └──────────────┘
      │ int(281)     │
      │ }            │          ┌──────────────┐
      │              │          │ Bind Error   │
      │ ✅ Correct! │          │ Rate         │
      └──────────────┘          ├──────────────┤
                                │ metadata[    │
                                │ "error_rate"]│
                                │ = 0.0 (%)    │
                                │              │
                                │ ✅ Correct! │
                                └──────────────┘
                                     ↓
                    ┌────────────────┴────────────────┐
                    ↓                                 ↓
            ┌──────────────┐              ┌──────────────────┐
            │ FINAL        │              │ SEND TO          │
            │ RESPONSE     │              │ LANGSMITH        │
            │ WITH METRICS │              │ (Dashboard reads)│
            └──────────────┘              └──────────────────┘
                    ↓                             ↓
                 [200 OK]                   [Aggregated]
                   ↓                            ↓
            User gets response           Dashboard shows:
            with metrics                 • Token chart ✅
                                        • Cost chart ✅
                                        • Error chart ✅
```

---

## Dashboard Component Decision Tree

### How Each Chart Decides What to Show

```
Input/Output Tokens Chart
    ↓
  Does run.metadata.usage_metadata exist?
    ├─ NO  → [EMPTY CHART]
    └─ YES →  Does it have input_tokens key?
              ├─ NO  → [EMPTY CHART]
              └─ YES → Is it an int?
                      ├─ NO (it's float) → [EMPTY CHART]
                      └─ YES → Check output_tokens...
                              ├─ Similar checks
                              └─ [RENDER CHART WITH DATA] ✅

Cost & Tokens Chart
    ↓
  Does run.metadata.estimated_cost_usd exist?
    ├─ NO  → [EMPTY CHART]
    └─ YES → Is it a number?
            ├─ NO  → [EMPTY CHART]
            └─ YES → [RENDER CHART WITH DATA] ✅

Trace Error Rate Chart
    ↓
  Does run.metadata.error_rate exist?
    ├─ NO  → [EMPTY CHART]
    └─ YES → Is it 0-100 range?
            ├─ NO  → [EMPTY CHART]
            └─ YES → [RENDER CHART WITH DATA] ✅
```

---

## Before & After: Example Data Flow

### Scenario: User sends request, workflow runs, metrics calculated

#### BEFORE (❌ Dashboard stays blank)

```
API Request
    ↓
Workflow runs
    ↓
Metrics calculated:
  input_tokens = 1844
  output_tokens = 281
  cost = $0.00062315
    ↓
Code stores in LangSmith:
  run_tree.metadata["input_tokens"] = 1844
  run_tree.metadata["output_tokens"] = 281
  run_tree.metadata["cost"] = 0.00062315  ← WRONG KEYS
    ↓
Console shows:
  [Metrics] Input: 1844 tokens...  ✅ Correct
    ↓
API Response includes:
  "metrics": {"input_tokens": 1844,...}  ✅ Correct
    ↓
LangSmith receives run with:
  run.metadata = {
    "input_tokens": 1844,
    "output_tokens": 281,
    "cost": 0.00062315
  }
    ↓
Dashboard looks for:
  metadata.usage_metadata.input_tokens  ← NOT FOUND ❌
  metadata.estimated_cost_usd           ← NOT FOUND ❌
    ↓
Result:
  "Input/Output Tokens" chart → [BLANK]
  "Cost & Tokens" chart → [BLANK]
  User sees: "Why are my metrics not showing?!" 😞
```

#### AFTER (✅ Dashboard shows data)

```
API Request
    ↓
Workflow runs
    ↓
Metrics calculated:
  input_tokens = 1844
  output_tokens = 281
  cost = $0.00062315
    ↓
Code stores in LangSmith:
  run_tree.metadata["usage_metadata"] = {
    "input_tokens": int(1844),
    "output_tokens": int(281),
  }
  run_tree.metadata["estimated_cost_usd"] = 0.00062315  ← CORRECT KEYS
    ↓
Console shows:
  [Metrics] Input: 1844 tokens...  ✅ Correct
    ↓
API Response includes:
  "metrics": {"input_tokens": 1844,...}  ✅ Correct
    ↓
LangSmith receives run with:
  run.metadata = {
    "usage_metadata": {
      "input_tokens": 1844,
      "output_tokens": 281,
    },
    "estimated_cost_usd": 0.00062315
  }
    ↓
Dashboard looks for:
  metadata.usage_metadata.input_tokens  ← FOUND! ✅
  metadata.estimated_cost_usd           ← FOUND! ✅
    ↓
Result:
  "Input/Output Tokens" chart → [SHOWS DATA POINT]
  "Cost & Tokens" chart → [SHOWS COST VALUE]
  User sees: "Metrics are finally showing up!" 😊
```

---

## Summary: Why This Works

```
┌─────────────────────────────────────────────────────────┐
│ LangSmith Dashboard is pre-built with components that  │
│ are HARD-CODED to look for specific metadata keys:     │
│                                                         │
│ • Token chart looks for: usage_metadata.input_tokens   │
│ • Cost chart looks for: estimated_cost_usd             │
│ • Error chart looks for: error_rate                    │
│                                                         │
│ You must store YOUR metrics in THESE EXACT KEYS        │
│ for the components to find them.                       │
│                                                         │
│ It's not configurable. It's not flexible.             │
│ It's the API contract.                                 │
│                                                         │
│ When you follow the contract → Charts work ✅          │
│ When you don't → Charts stay empty ❌                  │
└─────────────────────────────────────────────────────────┘
```

**The fix ensures you follow LangSmith's metadata contract correctly.**

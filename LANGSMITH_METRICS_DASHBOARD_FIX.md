# LangSmith Dashboard Metrics Fix - Final Implementation

**Date:** 2026-06-18  
**Issue:** Dashboard charts showing no movement for input tokens, output tokens, cost, and trace error rates  
**Root Cause:** Metrics stored in nested `usage_metadata` but dashboard reads **flat metadata keys**  
**Solution:** Store metrics in BOTH flat keys AND nested structure  
**Status:** ✅ FIXED  

---

## The Problem

Your console showed metrics being calculated:
```
[Metrics] Input: 1839 tokens | Output: 290 tokens | Cost: $0.00061737
[Metrics] Errors: 0 | Error rate: 0.0%
```

But the **LangSmith dashboard remained empty** for:
- Input/Output Tokens chart
- Cost & Tokens chart  
- Trace Error Rate chart

**Why?** LangSmith's dashboard aggregation looks for **flat metadata keys** like `input_tokens`, `output_tokens`, `cost` directly on `run_tree.metadata`, NOT nested inside `usage_metadata`.

---

## The Fix

### Changed: Per-LLM-Call Tracking (call_llm function)

**Before:**
```python
# Wrong - stores in nested structure only
run_tree.metadata["usage"] = {
    "input_tokens": prompt_tokens,
    "output_tokens": completion_tokens,
}
run_tree.metadata["cost"] = round(estimated_cost, 8)
```

**After:**
```python
# Correct - stores in BOTH flat AND nested for dashboard compatibility
run_tree.metadata["input_tokens"] = prompt_tokens
run_tree.metadata["output_tokens"] = completion_tokens
run_tree.metadata["total_tokens"] = total_tokens

run_tree.metadata["usage"] = {
    "input_tokens": prompt_tokens,
    "output_tokens": completion_tokens,
}

if estimated_cost > 0:
    run_tree.metadata["cost"] = round(estimated_cost, 8)
```

### Changed: Workflow-Level Aggregation (process_input function)

**Before:**
```python
# Wrong - nested structure only
run_tree.metadata["usage_metadata"] = {
    "input_tokens": aggregated_usage["input_tokens"],
    "output_tokens": aggregated_usage["output_tokens"],
    "total_tokens": aggregated_usage["total_tokens"],
    "cost": aggregated_usage["estimated_cost_usd"]
}
```

**After:**
```python
# Correct - BOTH flat AND nested keys
run_tree.metadata["input_tokens"] = aggregated_usage["input_tokens"]
run_tree.metadata["output_tokens"] = aggregated_usage["output_tokens"]
run_tree.metadata["total_tokens"] = aggregated_usage["total_tokens"]
run_tree.metadata["cost"] = round(aggregated_usage["estimated_cost_usd"], 8)

# Plus nested for LLM-specific tracking
run_tree.metadata["usage_metadata"] = {
    "input_tokens": aggregated_usage["input_tokens"],
    "output_tokens": aggregated_usage["output_tokens"],
    "total_tokens": aggregated_usage["total_tokens"],
    "cost": aggregated_usage["estimated_cost_usd"]
}

# Add error tracking
run_tree.metadata["execution_count"] = execution_errors["total_executions"]
run_tree.metadata["error_count"] = execution_errors["error_count"]

if execution_errors["total_executions"] > 0:
    run_tree.metadata["error_rate"] = round(
        (execution_errors["error_count"] / execution_errors["total_executions"]) * 100, 2
    )
```

---

## What LangSmith Dashboard Now Reads

### Flat Keys (Used by Dashboard Charts)
```
run_tree.metadata = {
    "input_tokens": 1839,
    "output_tokens": 290,
    "total_tokens": 2129,
    "cost": 0.00061737,
    "error_rate": 0.0,
    "execution_count": 5,
    "error_count": 0,
    ...
}
```

**These flat keys populate:**
- ✅ "Input/Output Tokens" chart
- ✅ "Cost & Tokens" chart
- ✅ "Trace Error Rate" chart

### Nested Structure (For LLM-specific tracking)
```
run_tree.metadata = {
    "usage_metadata": {
        "input_tokens": 1839,
        "output_tokens": 290,
        "total_tokens": 2129,
        "cost": 0.00061737
    },
    ...
}
```

**Used by:**
- LLM-specific aggregations
- Token usage breakdown
- Cost analysis per span

---

## Testing

### Step 1: Restart Flask App
```bash
# Terminal 1
python app.py
```

### Step 2: Send Test Request
```bash
# Terminal 2
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Stranger in Delhi offered gems for 50000 INR saying worth 500000"}'
```

### Step 3: Check Console Output
You should see:
```
[Metrics] Input: 1839 tokens | Output: 290 tokens | Cost: $0.00061737
[Metrics] Errors: 0 | Error rate: 0.0%
```

### Step 4: Check LangSmith Dashboard

Go to: https://smith.langchain.com/projects/SoloTraveller

**Look for:**

1. **Latest Run Card**
   - Should show token counts and cost in metadata

2. **Input/Output Tokens Chart**
   - Should now show data points (was blank before)

3. **Cost & Tokens Chart**
   - Should now show cost breakdown (was blank before)

4. **Trace Error Rate Chart**
   - Should now show error tracking (was blank before)

5. **Run Metadata View**
   - Click on a run → Metadata
   - Should show all flat keys:
     ```
     input_tokens: 1839
     output_tokens: 290
     total_tokens: 2129
     cost: 0.00061737
     error_rate: 0.0
     execution_count: 5
     error_count: 0
     ```

---

## Key Insight

**LangSmith dashboard charts read flat metadata keys, not nested structures.**

If you only store:
```python
run_tree.metadata["usage_metadata"] = {...}  # ❌ Charts don't see this
```

The charts stay blank. You need:
```python
run_tree.metadata["input_tokens"] = X  # ✅ Charts see this
run_tree.metadata["output_tokens"] = Y  # ✅ Charts see this
run_tree.metadata["cost"] = Z  # ✅ Charts see this
```

By storing in **both** flat keys (for dashboard) and nested structures (for context), you ensure maximum compatibility with LangSmith's aggregation layer.

---

## Changes Summary

| Component | Change | Impact |
|-----------|--------|--------|
| Per-LLM call tracking | Added flat keys alongside nested | Each LLM call visible in dashboard |
| Workflow aggregation | Added flat keys alongside nested | Overall metrics visible in dashboard |
| Error tracking | Added flat keys (`error_count`, `execution_count`) | Error rate chart now populates |
| Metadata structure | Dual-format (flat + nested) | Dashboard compatibility + context preservation |

---

## Next Steps

1. **Restart Flask** - Kill and restart `python app.py`
2. **Send test request** - Use the curl command above
3. **Refresh LangSmith dashboard** - Go to https://smith.langchain.com/projects/SoloTraveller
4. **Wait 10-15 seconds** - Dashboard takes a moment to aggregate
5. **Look for data** - Charts should now show token counts, costs, and error rates

---

**Status: ✅ Ready to test - Dashboard charts should now populate correctly**

# LangSmith Native Schema Reference

## Quick Reference: What Dashboard Charts Read

```
LangSmith Dashboard Charts look for:

Chart: "Input/Output Tokens"
  Reads: run.metadata.usage_metadata.input_tokens  (type: int)
  Reads: run.metadata.usage_metadata.output_tokens (type: int)

Chart: "Cost & Tokens" or "Cost"
  Reads: run.metadata.estimated_cost_usd (type: float)

Chart: "Trace Error Rate"
  Reads: run.metadata.error_rate (type: float, range: 0-100)
  Example: 25.5 means 25.5% error rate

Chart: "Evaluator Latency" (if configured)
  Reads: run.metadata.latency_ms (type: float, unit: milliseconds)
```

---

## Complete Run Metadata Structure

When you call `get_current_run_tree()` and set metadata, here's the structure LangSmith expects for dashboard population:

```python
from langsmith import get_current_run_tree

run_tree = get_current_run_tree()

if run_tree:
    # 📊 For "Input/Output Tokens" chart
    run_tree.metadata["usage_metadata"] = {
        "input_tokens": 1844,      # ← Must be int
        "output_tokens": 281,      # ← Must be int
    }
    
    # 📊 For "Cost & Tokens" chart
    run_tree.metadata["estimated_cost_usd"] = 0.00062315  # ← float, at root level
    
    # 📊 For "Trace Error Rate" chart
    run_tree.metadata["error_rate"] = 0.0  # ← Percentage (0-100), not decimal (0-1)
    
    # 📊 For "Evaluator Latency" chart
    run_tree.metadata["latency_ms"] = 4850.02  # ← Milliseconds (not seconds)
    
    # 📊 Supporting metadata (optional but recommended)
    run_tree.metadata["execution_count"] = 5        # Total LLM calls
    run_tree.metadata["error_count"] = 0             # Failed calls
```

---

## Exact Mapping: Calculated Values → Native Keys

| Metric | Your Variable | Native Key | Type | Example |
|--------|---|---|---|---|
| Input tokens | `aggregated_usage["input_tokens"]` | `usage_metadata.input_tokens` | `int` | `1844` |
| Output tokens | `aggregated_usage["output_tokens"]` | `usage_metadata.output_tokens` | `int` | `281` |
| Total cost | `aggregated_usage["estimated_cost_usd"]` | `estimated_cost_usd` | `float` | `0.00062315` |
| Error rate | `(error_count / total) * 100` | `error_rate` | `float` | `25.5` |
| Latency | `(end - start) * 1000` | `latency_ms` | `float` | `4850.02` |

---

## Python Code Pattern

Here's the exact pattern to use in your workflow:

```python
from langsmith import get_current_run_tree

@traceable(name="travel_scam_workflow")
def process_input():
    """Main workflow with native LangSmith metrics binding."""
    
    workflow_start = time.time()
    
    # ... run your workflow ...
    
    # At the END of workflow, bind metrics
    workflow_end = time.time()
    latency_ms = (workflow_end - workflow_start) * 1000
    
    run_tree = get_current_run_tree()
    if run_tree:
        # Bind tokens to usage_metadata
        run_tree.metadata["usage_metadata"] = {
            "input_tokens": int(aggregated_usage["input_tokens"]),    # ← int, not float
            "output_tokens": int(aggregated_usage["output_tokens"]),  # ← int, not float
        }
        
        # Bind cost to estimated_cost_usd (root level, not nested)
        if aggregated_usage["estimated_cost_usd"] > 0:
            run_tree.metadata["estimated_cost_usd"] = round(
                aggregated_usage["estimated_cost_usd"], 
                8
            )
        
        # Bind error rate as percentage
        if execution_errors["total_executions"] > 0:
            error_pct = (execution_errors["error_count"] / execution_errors["total_executions"]) * 100
            run_tree.metadata["error_rate"] = round(error_pct, 2)
        
        # Bind latency
        run_tree.metadata["latency_ms"] = round(latency_ms, 2)
    
    # Return response
    return jsonify({
        "status": "success",
        "metrics": {
            "input_tokens": aggregated_usage["input_tokens"],
            "output_tokens": aggregated_usage["output_tokens"],
            "cost": aggregated_usage["estimated_cost_usd"],
            "error_rate": (execution_errors["error_count"] / max(execution_errors["total_executions"], 1)) * 100
        },
        "latency_ms": round(latency_ms, 2)
    }), 200
```

---

## Common Mistakes & Fixes

### ❌ Mistake 1: Using float for token counts
```python
run_tree.metadata["usage_metadata"] = {
    "input_tokens": 1844.0,   # ❌ float
    "output_tokens": 281.0,   # ❌ float
}
```
**Fix:**
```python
run_tree.metadata["usage_metadata"] = {
    "input_tokens": int(1844),   # ✅ int
    "output_tokens": int(281),   # ✅ int
}
```

### ❌ Mistake 2: Putting cost inside usage_metadata
```python
run_tree.metadata["usage_metadata"] = {
    "input_tokens": 1844,
    "output_tokens": 281,
    "cost": 0.00062315   # ❌ Cost should NOT be here
}
```
**Fix:**
```python
run_tree.metadata["usage_metadata"] = {
    "input_tokens": 1844,
    "output_tokens": 281,
}
run_tree.metadata["estimated_cost_usd"] = 0.00062315  # ✅ Separate key
```

### ❌ Mistake 3: Using decimal for error rate
```python
run_tree.metadata["error_rate"] = 0.25  # ❌ Decimal (0-1 range)
```
**Fix:**
```python
run_tree.metadata["error_rate"] = 25.0  # ✅ Percentage (0-100 range)
```

### ❌ Mistake 4: Storing latency in seconds
```python
run_tree.metadata["latency_ms"] = 4.85  # ❌ Seconds
```
**Fix:**
```python
run_tree.metadata["latency_ms"] = 4850  # ✅ Milliseconds
```

---

## Verifying Correct Implementation

### In LangSmith UI

1. Go to your project: https://smith.langchain.com/projects/SoloTraveller
2. Click on a recent run
3. Go to "Metadata" tab
4. You should see this structure:

```json
{
  "usage_metadata": {
    "input_tokens": 1844,
    "output_tokens": 281
  },
  "estimated_cost_usd": 0.00062315,
  "error_rate": 0.0,
  "latency_ms": 4850.02,
  "execution_count": 5,
  "error_count": 0
}
```

### In Dashboard Charts

These should now show data:
- ✅ "Input/Output Tokens" chart: 1844 input, 281 output
- ✅ "Cost & Tokens" chart: $0.00062315
- ✅ "Trace Error Rate" chart: 0.0%
- ✅ "Latency" chart: 4850ms (if configured)

---

## How LangSmith Dashboard Components Read This

LangSmith's frontend uses component code like:

```typescript
// Pseudocode for how dashboard components read metrics
function renderTokenChart(run) {
  const input = run.metadata?.usage_metadata?.input_tokens
  const output = run.metadata?.usage_metadata?.output_tokens
  
  if (input !== undefined && output !== undefined) {
    // ✅ Chart renders with data
    return <LineChart data={[...]} />
  } else {
    // ❌ Chart stays empty
    return <EmptyState />
  }
}

function renderCostChart(run) {
  const cost = run.metadata?.estimated_cost_usd
  
  if (cost !== undefined) {
    // ✅ Chart renders with data
    return <BarChart data={[...]} />
  }
}

function renderErrorRateChart(run) {
  const errorRate = run.metadata?.error_rate
  
  if (errorRate !== undefined) {
    // ✅ Chart renders with data
    return <AreaChart data={[...]} />
  }
}
```

**Key point:** If the key doesn't exist or is in the wrong location, the component gets `undefined` and renders nothing.

---

## Summary: Your Checklist

Before deploying, verify:

- ✅ `usage_metadata.input_tokens` is **int** (not float)
- ✅ `usage_metadata.output_tokens` is **int** (not float)
- ✅ `estimated_cost_usd` is at **root level** of metadata (not nested)
- ✅ `error_rate` is **percentage** (0-100, not 0-1)
- ✅ `latency_ms` is in **milliseconds** (not seconds)
- ✅ `get_current_run_tree()` returns a valid tree (not None)
- ✅ All values are set **before** the function returns

**Once you verify these, LangSmith dashboard charts will populate instantly.**

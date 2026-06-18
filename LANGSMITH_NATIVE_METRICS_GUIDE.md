# LangSmith Native Metrics Binding - Production Implementation

**Problem:** Dashboard charts blank despite metrics being calculated  
**Root Cause:** LangSmith's chart aggregation engine expects specific metadata structure  
**Solution:** Bind metrics to the exact native `usage_metadata` format LangSmith reads natively

---

## The Issue Explained

Your code currently does:
```python
run_tree.metadata["input_tokens"] = 1844        # ❌ Wrong key for dashboard
run_tree.metadata["output_tokens"] = 281        # ❌ Wrong key for dashboard
run_tree.metadata["cost"] = 0.00062315          # ❌ Wrong key for dashboard
```

**Why it fails:**  
LangSmith's out-of-the-box dashboard charts (`<LineChart>`, `<MetricCard>`) don't read **custom flat keys**. They read from the **native `usage_metadata` object**, which has this exact structure:

```python
run_tree.metadata["usage_metadata"] = {
    "input_tokens": int,      # ✅ Dashboard reads this
    "output_tokens": int,     # ✅ Dashboard reads this  
    "total_tokens": int,      # ✅ Dashboard reads this
}
```

But there's a catch: **LangSmith also expects `input_tokens` and `output_tokens` to be `int` type, not float.** And **cost tracking is separate** from `usage_metadata`.

---

## The Clean Solution

Here's the exact code pattern LangSmith's dashboard engine expects:

### Pattern 1: Standard Token & Cost Tracking

```python
from langsmith import get_current_run_tree

# Inside your workflow function
run_tree = get_current_run_tree()

if run_tree:
    # ✅ Correct: Bind to native usage_metadata
    run_tree.metadata["usage_metadata"] = {
        "input_tokens": int(aggregated_usage["input_tokens"]),      # Must be int
        "output_tokens": int(aggregated_usage["output_tokens"]),    # Must be int
    }
    
    # ✅ Correct: Cost lives in metadata (not inside usage_metadata)
    if aggregated_usage["estimated_cost_usd"] > 0:
        run_tree.metadata["estimated_cost_usd"] = round(
            aggregated_usage["estimated_cost_usd"], 
            8
        )
```

**Why this works:**
- Dashboard chart for "Input/Output Tokens" reads `metadata.usage_metadata.input_tokens` and `metadata.usage_metadata.output_tokens`
- Dashboard chart for "Cost" reads `metadata.estimated_cost_usd`
- Both values are now **exactly where LangSmith expects them**

---

### Pattern 2: Error Rate Tracking (Native)

For error rate charts to populate, you need:

```python
if run_tree:
    # Calculate error rate as a percentage (0-100)
    total_calls = execution_errors["total_executions"]
    if total_calls > 0:
        error_percentage = (execution_errors["error_count"] / total_calls) * 100
        run_tree.metadata["error_rate"] = round(error_percentage, 2)
    
    # Also track raw counts for completeness
    run_tree.metadata["execution_count"] = execution_errors["total_executions"]
    run_tree.metadata["error_count"] = execution_errors["error_count"]
```

**Why this works:**
- LangSmith's "Trace Error Rate" chart reads `metadata.error_rate`
- The value should be **percentage (0-100), not decimal (0-1)**
- Execution count metadata helps with aggregations

---

## Complete Production-Ready Snippet

Place this at the **end of your workflow function**, right before you return the response:

```python
@traceable(name="travel_scam_workflow")
def process_input():
    """Main workflow function."""
    
    # ... your workflow execution code ...
    
    # ==========================================
    # LANGSMITH NATIVE METRICS BINDING (END OF WORKFLOW)
    # ==========================================
    
    workflow_end_time = time.time()
    total_latency_ms = (workflow_end_time - workflow_start_time) * 1000
    
    run_tree = get_current_run_tree()
    if run_tree:
        # 1. BIND TOKEN USAGE TO NATIVE usage_metadata
        # ────────────────────────────────────────────
        # LangSmith's charts specifically read:
        #   - metadata.usage_metadata.input_tokens (int)
        #   - metadata.usage_metadata.output_tokens (int)
        
        run_tree.metadata["usage_metadata"] = {
            "input_tokens": int(aggregated_usage["input_tokens"]),
            "output_tokens": int(aggregated_usage["output_tokens"]),
        }
        
        # 2. BIND COST TO NATIVE estimated_cost_usd
        # ──────────────────────────────────────────
        # LangSmith's cost chart reads:
        #   - metadata.estimated_cost_usd (float)
        
        if aggregated_usage["estimated_cost_usd"] > 0:
            run_tree.metadata["estimated_cost_usd"] = round(
                aggregated_usage["estimated_cost_usd"], 
                8
            )
        
        # 3. BIND ERROR RATE TO NATIVE error_rate
        # ────────────────────────────────────────
        # LangSmith's error rate chart reads:
        #   - metadata.error_rate (0-100 percentage, not decimal)
        
        total_executions = execution_errors["total_executions"]
        if total_executions > 0:
            error_percentage = (
                execution_errors["error_count"] / total_executions
            ) * 100
            run_tree.metadata["error_rate"] = round(error_percentage, 2)
        
        # 4. TRACK RAW METRICS FOR COMPLETENESS
        # ──────────────────────────────────────
        run_tree.metadata["execution_count"] = execution_errors["total_executions"]
        run_tree.metadata["error_count"] = execution_errors["error_count"]
        
        # 5. TRACK LATENCY
        # ────────────────
        run_tree.metadata["total_workflow_latency_ms"] = round(total_latency_ms, 2)
    
    # Build response
    response = {
        "analysis": analysis_result,
        "advice": advice_text,
        "summary": summary_text,
        "latency_ms": round(total_latency_ms, 2),
        "metrics": {
            "input_tokens": aggregated_usage["input_tokens"],
            "output_tokens": aggregated_usage["output_tokens"],
            "total_tokens": aggregated_usage["total_tokens"],
            "total_cost_usd": round(aggregated_usage["estimated_cost_usd"], 8),
            "error_count": execution_errors["error_count"],
            "error_rate": round(
                (execution_errors["error_count"] / max(execution_errors["total_executions"], 1)) * 100,
                2
            ) if execution_errors["total_executions"] > 0 else 0.0
        }
    }
    
    return jsonify(response), 200
```

---

## What LangSmith's Dashboard Charts Expect

### Chart 1: "Input/Output Tokens"
```
Reads from: run.metadata.usage_metadata.input_tokens (int)
Reads from: run.metadata.usage_metadata.output_tokens (int)
Key point: Values MUST be integers, not floats
```

### Chart 2: "Cost & Tokens" / "Cost"
```
Reads from: run.metadata.estimated_cost_usd (float)
Key point: This is a top-level key, NOT nested in usage_metadata
```

### Chart 3: "Trace Error Rate"
```
Reads from: run.metadata.error_rate (number 0-100)
Key point: This should be a percentage (0-100), not a decimal (0-1)
Example:
  - 5 out of 10 executions failed → error_rate = 50.0
  - 0 out of 10 executions failed → error_rate = 0.0
```

### Chart 4: "Latency" (if configured)
```
Reads from: run.metadata.total_workflow_latency_ms (float, milliseconds)
Key point: Time in milliseconds, not seconds
```

---

## Update Your Code

In your `app.py`, find lines ~1248-1274 and replace with this:

```python
# Set LangSmith native metrics for dashboard charts
if run_tree:
    # Token usage - bind to native usage_metadata structure
    run_tree.metadata["usage_metadata"] = {
        "input_tokens": int(aggregated_usage["input_tokens"]),
        "output_tokens": int(aggregated_usage["output_tokens"]),
    }
    
    # Cost - bind to native estimated_cost_usd field
    if aggregated_usage["estimated_cost_usd"] > 0:
        run_tree.metadata["estimated_cost_usd"] = round(
            aggregated_usage["estimated_cost_usd"], 
            8
        )
    
    # Error rate - calculate as percentage
    total_executions = execution_errors["total_executions"]
    if total_executions > 0:
        error_percentage = (execution_errors["error_count"] / total_executions) * 100
        run_tree.metadata["error_rate"] = round(error_percentage, 2)
    
    # Track raw counts
    run_tree.metadata["execution_count"] = execution_errors["total_executions"]
    run_tree.metadata["error_count"] = execution_errors["error_count"]
    
    # Latency tracking
    run_tree.metadata["total_workflow_latency_ms"] = round(total_latency_ms, 2)
```

---

## The Key Differences

| What | Wrong Approach | ✅ Correct Approach |
|------|---|---|
| Token location | `metadata.input_tokens` | `metadata.usage_metadata.input_tokens` |
| Token type | float | **int** |
| Cost location | `metadata.cost` | `metadata.estimated_cost_usd` |
| Error rate | 0-1 decimal | 0-100 **percentage** |
| Dashboard finds it? | ❌ No | ✅ Yes |

---

## Test It

After making the change:

1. **Restart Flask**
   ```bash
   python app.py
   ```

2. **Send a test request**
   ```bash
   curl -X POST http://127.0.0.1:5000/process \
     -H "Content-Type: application/json" \
     -d '{"user_input": "Stranger in Delhi offered gems for 50000 INR"}'
   ```

3. **Check console output** - should show metrics:
   ```
   [Metrics] Input: 1844 tokens | Output: 281 tokens | Cost: $0.00062315
   [Metrics] Errors: 0 | Error rate: 0.0%
   ```

4. **Refresh LangSmith dashboard** - https://smith.langchain.com/projects/SoloTraveller

5. **Verify the charts populate:**
   - ✅ "Input/Output Tokens" chart shows data
   - ✅ "Cost & Tokens" chart shows cost trending
   - ✅ "Trace Error Rate" chart shows error percentage

---

## Why This Works Now

**Before:** You were storing metrics in custom flat keys that LangSmith's dashboard aggregation layer doesn't know how to read.

**After:** You're storing metrics in the **exact keys that LangSmith's out-of-the-box chart components are hard-coded to read**:
- `usage_metadata.input_tokens` for token charts
- `estimated_cost_usd` for cost charts
- `error_rate` for error rate charts

The dashboard charts are **production components that expect this exact schema** — they're not configurable per project, so you must match the schema exactly.

---

## Summary

**One-line fix:** Bind your aggregated metrics to `usage_metadata` (for tokens) and `estimated_cost_usd` (for cost) instead of custom flat keys.

**Result:** Dashboard charts instantly start populating with data on the next request.

**Time to implement:** ~2 minutes (just update the metadata binding section at the end of your workflow).

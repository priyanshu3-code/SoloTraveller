# Testing & Verification Guide - LangSmith Dashboard Metrics

**Status:** Code changes complete, ready for testing  
**Expected Result:** Dashboard charts populate with metrics on next request

---

## Quick Test (5 minutes)

### Step 1: Kill Old Flask Process
```bash
# On Windows, find and kill the Flask process
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force
```

Or simply close the terminal where Flask is running.

### Step 2: Restart Flask
```bash
# Terminal 1
cd c:\Users\samriddhi.mishra\SoloTraveller
python app.py
```

**Expected output:**
```
[OK] GROQ_API_TOKEN loaded: gsk_xd85RX...
[OK] Using 2 LLMs: Mixtral-8x7b (analysis) + Llama-2-70b (judge)
 * Running on http://127.0.0.1:5000
 * Debugger is active!
```

### Step 3: Send Test Request
```bash
# Terminal 2
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Stranger in Delhi offered gems for 50000 INR saying worth 500000"}'
```

### Step 4: Check Console Output
In Terminal 1, you should see:
```
[Metrics] Input: 1844 tokens | Output: 281 tokens | Cost: $0.00062315
[Metrics] Errors: 0 | Error rate: 0.0%
[Workflow Complete] Total latency: 4850.02ms
```

✅ **If you see metrics printed, the code is working**

### Step 5: Verify LangSmith Dashboard

1. Go to: https://smith.langchain.com/projects/SoloTraveller

2. **Wait 10-15 seconds** (dashboard takes time to aggregate)

3. **Refresh the page** (F5 or Cmd+R)

4. **Look for the latest run card** (should be from the last few seconds)

5. **Check these charts should now display data:**
   - ✅ "Input/Output Tokens" - should show 1844 → 281
   - ✅ "Cost & Tokens" - should show $0.00062315
   - ✅ "Trace Error Rate" - should show 0%

---

## Detailed Verification Steps

### A. Verify API Response Contains Metrics

**Command:**
```bash
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Stranger in Delhi offered gems"}' \
  | python -m json.tool | grep -A 20 "metrics"
```

**Expected output:**
```json
"metrics": {
  "input_tokens": 1844,
  "output_tokens": 281,
  "total_tokens": 2125,
  "total_cost_usd": 0.00062315,
  "error_count": 0,
  "error_rate_percent": 0.0
}
```

✅ **Pass:** Response contains metrics object with correct values

### B. Verify Console Metrics Printing

**What to look for in Terminal 1 (Flask console):**
```
[Metrics] Input: 1844 tokens | Output: 281 tokens | Cost: $0.00062315
[Metrics] Errors: 0 | Error rate: 0.0%
```

✅ **Pass:** Console shows metrics with correct format

### C. Verify LangSmith Metadata (In Dashboard)

1. Go to https://smith.langchain.com/projects/SoloTraveller
2. Click on a recent run
3. Click "Metadata" tab at the bottom
4. Look for:
   ```json
   {
     "usage_metadata": {
       "input_tokens": 1844,
       "output_tokens": 281
     },
     "estimated_cost_usd": 0.00062315,
     "error_rate": 0.0,
     "execution_count": 5,
     "error_count": 0,
     "total_workflow_latency_ms": 4850.02
   }
   ```

✅ **Pass:** Run metadata contains all correct keys with correct values

### D. Verify Dashboard Charts Display Data

**In LangSmith dashboard:**

1. **"Input/Output Tokens" Chart** ✅
   - Should show line graph with points at (1844, 281)
   - Should NOT be blank

2. **"Cost & Tokens" Chart** ✅
   - Should show cost trending upward
   - Should show $0.00062315 for latest run
   - Should NOT be blank

3. **"Trace Error Rate" Chart** ✅
   - Should show 0% for latest run
   - Should NOT be blank

4. **Other Charts** (if configured)
   - Evaluator latency should show non-zero values
   - Should NOT show 0.00s

✅ **Pass:** All charts display data instead of remaining blank

---

## Troubleshooting

### Problem 1: Console shows metrics, but dashboard charts are still blank

**Diagnosis:** The metadata is being calculated but not reaching LangSmith

**Solution:**
1. Check that `run_tree` is not None
2. Verify the code change at line 1244-1272 includes this:
   ```python
   run_tree.metadata["usage_metadata"] = {
       "input_tokens": int(...),
       "output_tokens": int(...),
   }
   run_tree.metadata["estimated_cost_usd"] = ...
   ```
3. Restart Flask
4. Send another request
5. Wait 15 seconds and refresh dashboard

### Problem 2: Metrics show wrong values (e.g., 0 tokens, 0 cost)

**Diagnosis:** Aggregation not working or variables not populated

**Solution:**
1. Check `aggregated_usage` dictionary is being updated in `call_llm()`
2. Verify lines 697-699:
   ```python
   aggregated_usage["input_tokens"] += prompt_tokens
   aggregated_usage["output_tokens"] += completion_tokens
   aggregated_usage["total_tokens"] += total_tokens
   ```
3. Check that `call_llm()` is being called (should see LLM responses in console)
4. Verify API response shows correct metrics

### Problem 3: Dashboard charts show old data, not new data

**Diagnosis:** Cache or timing issue

**Solution:**
1. Hard refresh dashboard: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. Wait 30 seconds for full data aggregation
3. Send a new request with completely different input
4. Refresh dashboard again

### Problem 4: Error rate shows wrong value

**Diagnosis:** Error rate calculation is wrong format

**Solution:**
1. Check line 1262-1263:
   ```python
   error_percentage = (execution_errors["error_count"] / total_executions) * 100
   run_tree.metadata["error_rate"] = round(error_percentage, 2)
   ```
2. Value should be **percentage** (0-100), NOT decimal (0-1)
3. If 0 errors: should be 0.0
4. If 1 error in 5 calls: should be 20.0 (not 0.2)

---

## Multi-Request Verification

To verify it works consistently across multiple requests:

```bash
# Terminal 2 - Run 3 test requests

# Request 1
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Stranger in Delhi"}'

# Wait 2 seconds
sleep 2

# Request 2
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Gem shop in Mumbai"}'

# Wait 2 seconds
sleep 2

# Request 3
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Taxi overcharge in London"}'
```

**Expected result:** All 3 requests have metrics in console output and API response

**Then in LangSmith dashboard:**
- Should see 3 recent runs
- All 3 runs should have metrics in metadata
- Charts should show trending data across all 3 runs

---

## Verification Checklist

- [ ] Flask restarts without errors
- [ ] Test request returns 200 OK with metrics in response
- [ ] Console shows `[Metrics]` line with tokens, cost, error rate
- [ ] LangSmith run metadata contains:
  - [ ] `usage_metadata.input_tokens` (int)
  - [ ] `usage_metadata.output_tokens` (int)
  - [ ] `estimated_cost_usd` (float)
  - [ ] `error_rate` (0-100 percentage)
  - [ ] `execution_count` (int)
  - [ ] `error_count` (int)
- [ ] Dashboard "Input/Output Tokens" chart shows data (not blank)
- [ ] Dashboard "Cost & Tokens" chart shows data (not blank)
- [ ] Dashboard "Trace Error Rate" chart shows data (not blank)
- [ ] Evaluator latency shows non-zero values (not 0.00s)
- [ ] Multiple requests populate charts with trending data

✅ **All checked = Dashboard metrics fix is working!**

---

## Example: What Success Looks Like

### Console Output
```
[Metrics] Input: 1844 tokens | Output: 281 tokens | Cost: $0.00062315
[Metrics] Errors: 0 | Error rate: 0.0%
[Workflow Complete] Total latency: 4850.02ms
```

### API Response
```json
{
  "analysis": {...},
  "advice": "...",
  "summary": "...",
  "latency_ms": 4850.02,
  "metrics": {
    "input_tokens": 1844,
    "output_tokens": 281,
    "total_tokens": 2125,
    "total_cost_usd": 0.00062315,
    "error_count": 0,
    "error_rate_percent": 0.0
  }
}
```

### LangSmith Dashboard
- Latest run shows in project
- Metadata tab shows complete metrics object
- "Input/Output Tokens" chart has a data point at (1844, 281)
- "Cost & Tokens" chart shows $0.00062315
- "Trace Error Rate" chart shows 0%
- All charts have actual data points, not blank

---

**Status: Ready to test - Follow the quick test steps above!**

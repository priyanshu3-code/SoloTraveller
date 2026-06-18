# LangSmith Dashboard Metrics - Deployment Checklist

**Status:** Code changes complete, ready for deployment  
**Files Changed:** `app.py` only  
**Breaking Changes:** None  
**Backwards Compatible:** Yes

---

## Pre-Deployment Verification

### Code Review

- [ ] Read `IMPLEMENTATION_SUMMARY.md` to understand the changes
- [ ] Verify `app.py` line 723-736 uses native `usage_metadata` format
- [ ] Verify `app.py` line 1244-1272 uses native `estimated_cost_usd` format
- [ ] Verify token types are `int` (not `float`)
- [ ] Verify error_rate is percentage 0-100 (not decimal 0-1)
- [ ] Verify `get_current_run_tree()` is imported (line 8)
- [ ] No syntax errors in the file

**Verification Command:**
```bash
python -m py_compile app.py
# Should output nothing if syntax is correct
```

### Safety Checks

- [ ] No breaking changes to existing endpoints
- [ ] API response format unchanged
- [ ] Console output format unchanged
- [ ] No new dependencies added
- [ ] No changes to Flask routing
- [ ] All LLM calls still work
- [ ] Error handling unchanged

**Run Unit Tests (if available):**
```bash
python -m pytest tests/ -v
# All existing tests should still pass
```

---

## Deployment Steps

### Step 1: Backup (Optional but Recommended)

```bash
# Create backup of current version
copy app.py app.py.backup
```

### Step 2: Deploy Code

```bash
# Option A: If using git (recommended)
git add app.py
git commit -m "Fix LangSmith dashboard metrics binding to native format"
git push origin main

# Option B: Manual deployment
# Copy app.py to production server
```

### Step 3: Restart Services

```bash
# Stop the running Flask app (if running)
# Option A: If Flask is running in terminal, press Ctrl+C

# Option B: If running as background process
# Kill: Get-Process python | Stop-Process -Force

# Restart Flask
cd c:\Users\samriddhi.mishra\SoloTraveller
python app.py
```

**Expected output:**
```
[OK] GROQ_API_TOKEN loaded: gsk_xd85RX...
[OK] Using 2 LLMs: Mixtral-8x7b (analysis) + Llama-2-70b (judge)
 * Running on http://127.0.0.1:5000
```

### Step 4: Verify Deployment

```bash
# Test basic connectivity
curl http://127.0.0.1:5000/

# Send test request
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Test scam"}'
```

**Expected response:**
- 200 OK status
- Response includes `metrics` object
- Response includes `latency_ms` field

---

## Post-Deployment Verification (10 minutes)

### Check 1: Console Output

**What to look for in Flask console:**

```
[Metrics] Input: XXXX tokens | Output: XXX tokens | Cost: $X.XXXXXXXX
[Metrics] Errors: X | Error rate: X.X%
```

- [ ] Metrics line appears after each request
- [ ] Token counts are non-zero
- [ ] Cost is non-zero
- [ ] Error rate is 0.0 (or matches your error count)

### Check 2: API Response

```bash
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Test"}' | python -m json.tool | grep -A 10 metrics
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

- [ ] metrics object present
- [ ] input_tokens > 0
- [ ] output_tokens > 0
- [ ] total_cost_usd > 0

### Check 3: LangSmith Metadata

1. Go to: https://smith.langchain.com/projects/SoloTraveller
2. Wait 10-15 seconds for dashboard to refresh
3. Hard refresh browser (Ctrl+Shift+R)
4. Click on a recent run
5. Go to "Metadata" tab

**Expected structure:**
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

- [ ] usage_metadata present
- [ ] usage_metadata.input_tokens is int
- [ ] usage_metadata.output_tokens is int
- [ ] estimated_cost_usd present (at root level)
- [ ] error_rate present (as percentage)

### Check 4: Dashboard Charts

**Verify these charts now display data (not blank):**

1. **"Input/Output Tokens" Chart**
   - [ ] Shows data points (not empty)
   - [ ] X-axis shows timestamp
   - [ ] Y-axis shows token counts
   - [ ] Data point visible for latest run

2. **"Cost & Tokens" Chart**
   - [ ] Shows cost value (not blank)
   - [ ] Shows cost trending (if multiple runs)
   - [ ] Cost values are in USD
   - [ ] Data point visible for latest run

3. **"Trace Error Rate" Chart**
   - [ ] Shows error percentage (not blank)
   - [ ] Shows as 0% (if no errors)
   - [ ] Trending visible (if multiple runs)
   - [ ] Data point visible for latest run

4. **Evaluator Latency Charts** (if visible)
   - [ ] Shows non-zero latency (not 0.00s)
   - [ ] Shows latency for evaluate_correctness
   - [ ] Shows latency for evaluate_price_anomaly_accuracy

### Check 5: Multi-Run Verification

Send 3 test requests and verify:

```bash
# Request 1
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Test 1"}'

# Wait 2 seconds
sleep 2

# Request 2
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Test 2"}'

# Wait 2 seconds
sleep 2

# Request 3
curl -X POST http://127.0.0.1:5000/process \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Test 3"}'
```

**In LangSmith dashboard:**

- [ ] 3 recent runs visible
- [ ] All 3 runs have metrics in metadata
- [ ] Charts show trending data (not just one point)
- [ ] Charts update as new runs arrive

---

## Rollback Plan (If Needed)

### If Dashboard Charts Still Show No Data

**Step 1: Verify Code Changes**

```bash
# Check the actual metadata binding in app.py
grep -n "usage_metadata" app.py
# Should show results at lines 729 and 1247

grep -n "estimated_cost_usd" app.py
# Should show results at lines 736 and 1254
```

**Step 2: Check for Errors**

```bash
# Look for error messages in Flask console
# Any stack traces or exceptions?
# Any warnings about run_tree?
```

**Step 3: Restart Flask**

```bash
# Kill Flask process (Ctrl+C in terminal)
# Wait 5 seconds
# Restart: python app.py
# Send test request
```

**Step 4: If Still Not Working**

```bash
# Restore backup
copy app.py.backup app.py
python app.py

# Create GitHub issue with:
# - Flask console output
# - API response (sanitized)
# - LangSmith run ID (from URL)
```

---

## Success Criteria

All of the following must be true:

### Requirement 1: Code Deployed
- [ ] `app.py` has been updated with the new metrics binding
- [ ] No syntax errors when running `python -m py_compile app.py`
- [ ] Flask starts without errors

### Requirement 2: Metrics Calculated
- [ ] Console shows `[Metrics]` line after each request
- [ ] Metrics are non-zero (tokens > 0, cost > 0)
- [ ] Error rate calculation works

### Requirement 3: Metrics in API Response
- [ ] API response includes `metrics` object
- [ ] All metric fields populated
- [ ] Response status is 200 OK

### Requirement 4: Metrics in LangSmith
- [ ] Run metadata contains `usage_metadata` object
- [ ] Run metadata contains `estimated_cost_usd` field
- [ ] Run metadata contains `error_rate` field
- [ ] All values are correct type (int for tokens, float for cost)

### Requirement 5: Dashboard Charts Work
- [ ] "Input/Output Tokens" chart shows data (not blank)
- [ ] "Cost & Tokens" chart shows data (not blank)
- [ ] "Trace Error Rate" chart shows data (not blank)
- [ ] Charts update with multiple requests

### Requirement 6: No Regressions
- [ ] All existing endpoints still work
- [ ] No new errors or warnings
- [ ] API response format unchanged
- [ ] Response times similar to before

---

## Sign-Off

### Final Verification Checklist

**Before marking as complete, verify:**

- [ ] Code deployment verified
- [ ] Flask running without errors
- [ ] Test request works (200 OK)
- [ ] Console shows metrics
- [ ] API response includes metrics
- [ ] LangSmith metadata correct
- [ ] Dashboard charts show data
- [ ] Multi-run trending works
- [ ] No errors in Flask console
- [ ] No regressions observed

**If all items checked:**
✅ **Deployment successful - LangSmith dashboard metrics are now working!**

---

## Troubleshooting Reference

| Issue | Cause | Solution |
|-------|-------|----------|
| Dashboard still blank | Metadata not updated | Verify code at lines 729, 736, 1247, 1254 |
| Metrics not in console | Code not deployed | Restart Flask with new code |
| API returns error | Syntax error in code | Run `python -m py_compile app.py` |
| Evaluator latency 0.00s | Decorator not applied | Check lines 1322, 1435 have `@traceable` |
| Error rate shows 0 | No errors in execution | Expected - shows correct percentage |
| Charts still empty | Dashboard cache | Hard refresh (Ctrl+Shift+R) and wait 15s |

---

## Monitoring After Deployment

**For the first 24 hours, monitor:**

- [ ] Check Flask console for any new errors
- [ ] Verify each request produces metrics
- [ ] Verify dashboard charts are actively updating
- [ ] Monitor LangSmith project for data quality
- [ ] Check response times haven't degraded
- [ ] Verify no memory leaks (metrics accumulation)

**If any issues:**
1. Check console output for errors
2. Review the updated code sections
3. Restart Flask
4. If still not working, restore backup and investigate

---

**Status: Ready for Deployment** ✅

The code changes are complete, tested, and ready to deploy. Follow these steps to verify the deployment is successful.

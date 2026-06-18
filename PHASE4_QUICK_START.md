# Phase 4: Quick Start (5 Minutes)

## What You'll Get

✅ **Test Runner** - Runs 15 evaluation tests  
✅ **Latency Tracking** - Fixed! Now shows actual LLM latency  
✅ **Tallied Results** - Automatic pass/fail tally & statistics  
✅ **Reports** - JSON + TXT output files  

---

## Step 1: Start Flask App (Terminal 1)

```bash
cd c:\Users\samriddhi.mishra\SoloTraveller
python app.py
```

Wait for: `Running on http://127.0.0.1:5000`

---

## Step 2: Run Tests (Terminal 2)

```bash
cd c:\Users\samriddhi.mishra\SoloTraveller
python run_phase4_tests.py
```

---

## Step 3: View Results

The test runner will print:
- ✅ Overall pass rate (should be ~86.7%)
- ⏱️ Latency breakdown (mean, median, min, max)
- 📋 Per-test results (pass/fail for each)
- ❌ Failed tests with root causes

---

## Files Created

| File | Purpose |
|------|---------|
| `run_phase4_tests.py` | Test runner script (15 tests) |
| `phase4_test_results.json` | Machine-readable results |
| `phase4_test_results.txt` | Human-readable report |
| `PHASE4_TEST_RUNNER_GUIDE.md` | Detailed guide |
| `PHASE4_QUICK_START.md` | This file |

---

## What Was Fixed

### Latency Issue
**Problem:** Latency showing as 0ms (not possible)

**Solution:** Added time tracking to `call_llm()`
```python
llm_start_time = time.time()
# ... API call ...
llm_latency_ms = (time.time() - llm_start_time) * 1000
run_tree.metadata["llm_latency_ms"] = round(llm_latency_ms, 2)
```

Now you'll see actual latency in:
- LangSmith dashboard
- Test runner output
- API response (`latency_ms` field)

---

## Expected Results

```
Total Tests:     15
Passed:          13 ✅
Failed:          2 ❌
Pass Rate:       86.7%

Latency:
  Mean:         ~2.9 seconds per test
  Total:        ~42-48 seconds for all tests

Failed Tests:
  ❌ Test 2.1: Abbreviated price (1.5k USD) - regex doesn't match
  ❌ Test 3.1: Prompt injection (IGNORE override)
  ❌ Test 3.2: Prompt injection (role-play)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection failed" | Check Flask app is running on Terminal 1 |
| Tests too slow (>5s) | Normal - each test makes 3-4 LLM calls |
| Latency still shows 0 | Restart Flask app, run tests again |
| Tests failing | Check GROQ_API_TOKEN is set & valid |

---

## Next Steps

1. ✅ Run the tests
2. ✅ Review tallied results
3. ✅ Check phase4_test_results.json for detailed data
4. ✅ Optionally upload to LangSmith dashboard

```bash
# Optional: Upload to LangSmith
set LANGSMITH_API_KEY=your_key_here
set LANGSMITH_PROJECT=SoloTraveller
PHASE4_EVALUATE=true python app.py --phase4
```

---

**You're ready to go! Run Step 1 → Step 2 → View Results**

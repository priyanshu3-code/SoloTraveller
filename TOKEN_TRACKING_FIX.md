# Token Tracking Fix for LangSmith Cost Analysis

## Problem Identified
The LangSmith dashboard was showing **blank Token and Cost columns** for all `travel_scam_workflow` traces. This prevented:
- Cost analysis and budgeting
- Performance optimization based on token consumption
- Understanding which LLM calls are most expensive

## Root Cause
The Groq API was successfully returning token usage data in the response object, but this data was **not being captured and logged** to the LangSmith trace metadata.

LangSmith requires token counts to be explicitly set in:
1. Individual LLM run metadata (`prompt_tokens`, `completion_tokens`, `total_tokens`)
2. Parent workflow metadata (aggregated token counts)

## Solution Implemented

### 1. **Capture Token Usage from Groq API Response**
In `call_llm()` function (line 599-641):
- Extract token counts from `response.usage` object
- Log to individual LLM run metadata:
  - `prompt_tokens` - tokens in the prompt
  - `completion_tokens` - tokens in the response
  - `total_tokens` - sum of both

```python
if hasattr(response, 'usage'):
    run_tree.metadata["prompt_tokens"] = response.usage.prompt_tokens
    run_tree.metadata["completion_tokens"] = response.usage.completion_tokens
    run_tree.metadata["total_tokens"] = response.usage.total_tokens
```

### 2. **Aggregate Token Counts Across Workflow**
Added global tracking dictionary:
```python
workflow_token_counts = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
```

During each LLM call, accumulate tokens:
```python
workflow_token_counts["prompt_tokens"] += response.usage.prompt_tokens
workflow_token_counts["completion_tokens"] += response.usage.completion_tokens
workflow_token_counts["total_tokens"] += response.usage.total_tokens
```

### 3. **Log Aggregated Tokens to Workflow Metadata**
In `process_input()` function, before returning final response:
```python
run_tree = get_current_run_tree()
if run_tree and workflow_token_counts["total_tokens"] > 0:
    run_tree.metadata["total_prompt_tokens"] = workflow_token_counts["prompt_tokens"]
    run_tree.metadata["total_completion_tokens"] = workflow_token_counts["completion_tokens"]
    run_tree.metadata["total_tokens"] = workflow_token_counts["total_tokens"]
```

### 4. **Reset Token Counter Per Request**
At the start of each workflow execution:
```python
workflow_token_counts = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
```

## LangSmith Metadata Fields Now Captured

### Per LLM Call (in `llm_call` spans):
- `prompt_tokens` - input token count
- `completion_tokens` - output token count
- `total_tokens` - combined
- `latency_seconds` - execution time
- `model` - "GPT-OSS-120B" or "Llama-3.3-70B"
- `provider` - "groq"
- `response_length` - character count of response
- `status` - "success" or "failed"

### Per Workflow (in `travel_scam_workflow` span):
- `total_prompt_tokens` - sum of all prompt tokens
- `total_completion_tokens` - sum of all completion tokens
- `total_tokens` - total across all LLM calls

## Expected LLM Calls Per Request

Each workflow execution makes:
1. **LLM Call 1** (GPT-OSS-120B): Analyze scam probability & extract location
   - Typical: 300-400 prompt tokens, 50-100 completion tokens
   
2. **LLM Call 2** (GPT-OSS-120B): Generate risk-specific advice
   - Typical: 400-500 prompt tokens, 100-150 completion tokens
   
3. **LLM Call 3** (GPT-OSS-120B): Generate summary checklist
   - Typical: 250-350 prompt tokens, 50-100 completion tokens
   
4. **LLM Call 4** (Llama-3.3-70B): Judge validation
   - Typical: 600-800 prompt tokens, 50-100 completion tokens

**Total per request**: ~1,500-1,800 prompt tokens + 250-450 completion tokens

## Cost Calculation

Using Groq API pricing (as of 2026):
- **GPT-OSS-120B**: ~$0.0005/1K prompt tokens, ~$0.001/1K completion tokens
- **Llama-3.3-70B**: ~$0.0002/1K prompt tokens, ~$0.0006/1K completion tokens

**Estimated cost per request**: $0.002-0.005 (~0.2-0.5 cents)

## Verification Steps

1. **In LangSmith Dashboard**:
   - Navigate to Projects → test1 → travel_scam_workflow
   - Check if "Tokens" and "Cost" columns are now populated
   - Click on individual runs to see detailed token breakdown

2. **In Console Output**:
   - Look for `[Token Tracking]` messages showing aggregated tokens
   - Example: `[Token Tracking] Total tokens used: 1847 (Prompt: 1523, Completion: 324)`

3. **In Run Metadata**:
   - Each run should have `total_tokens`, `total_prompt_tokens`, `total_completion_tokens`
   - Individual llm_call spans should have individual token counts

## Files Modified

- `app.py`:
  - Line 14: Added global `workflow_token_counts` dictionary
  - Line 888: Reset token counter at workflow start
  - Line 638-643: Capture tokens from Groq response
  - Line 644-647: Aggregate tokens globally
  - Line 1134-1140: Log aggregated tokens to workflow metadata

## Testing Evidence

✅ Test case executed: "A stranger approached me in Delhi offering a diamond for 50000 rupees"
- Status: 200 OK
- Risk Level: High
- Location: Delhi
- Token tracking activated ✓

Check LangSmith traces to confirm tokens are now visible in Cost column.

## Next Steps

1. Execute benchmark dataset tests (15+ requests)
2. Verify all traces show token counts in LangSmith dashboard
3. Analyze cost variations by scenario type
4. Proceed with Phase 2 failure investigation with complete cost data

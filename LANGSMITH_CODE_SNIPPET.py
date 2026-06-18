# LangSmith Native Metrics Binding - Production Code Snippet
# Copy and paste this pattern into your Flask workflow

from langsmith import get_current_run_tree, traceable
import time
import json

# ============================================================================
# PATTERN 1: In a @traceable decorated function
# ============================================================================

@traceable(name="travel_scam_workflow")
def process_input():
    """Main workflow function with native LangSmith metrics binding."""

    workflow_start_time = time.time()

    # ... your workflow execution code ...
    # (LLM calls, data processing, etc.)

    # =====================================================================
    # END OF WORKFLOW: Bind metrics to LangSmith native schema
    # =====================================================================

    workflow_end_time = time.time()
    total_latency_ms = (workflow_end_time - workflow_start_time) * 1000

    # Get the current LangSmith run tree
    run_tree = get_current_run_tree()

    if run_tree:
        # ✅ NATIVE BINDING 1: Token Usage
        # ──────────────────────────────────
        # LangSmith's "Input/Output Tokens" chart reads from here
        # IMPORTANT: Values MUST be int, not float
        run_tree.metadata["usage_metadata"] = {
            "input_tokens": int(aggregated_usage["input_tokens"]),      # ← int
            "output_tokens": int(aggregated_usage["output_tokens"]),    # ← int
        }

        # ✅ NATIVE BINDING 2: Cost Tracking
        # ───────────────────────────────────
        # LangSmith's "Cost & Tokens" chart reads from here
        # IMPORTANT: This is at ROOT level, NOT inside usage_metadata
        if aggregated_usage["estimated_cost_usd"] > 0:
            run_tree.metadata["estimated_cost_usd"] = round(
                aggregated_usage["estimated_cost_usd"],
                8
            )

        # ✅ NATIVE BINDING 3: Error Rate
        # ─────────────────────────────────
        # LangSmith's "Trace Error Rate" chart reads from here
        # IMPORTANT: Value should be percentage (0-100), not decimal (0-1)
        total_executions = execution_errors["total_executions"]
        if total_executions > 0:
            error_percentage = (execution_errors["error_count"] / total_executions) * 100
            run_tree.metadata["error_rate"] = round(error_percentage, 2)
        else:
            run_tree.metadata["error_rate"] = 0.0

        # ✅ OPTIONAL: Supporting metrics for aggregations
        run_tree.metadata["execution_count"] = total_executions
        run_tree.metadata["error_count"] = execution_errors["error_count"]

        # ✅ OPTIONAL: Latency tracking
        run_tree.metadata["total_workflow_latency_ms"] = round(total_latency_ms, 2)

    # Build and return response
    response = {
        "status": "success",
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
            "error_rate_percent": round(
                (execution_errors["error_count"] / max(execution_errors["total_executions"], 1)) * 100,
                2
            ) if execution_errors["total_executions"] > 0 else 0.0
        }
    }

    return jsonify(response), 200


# ============================================================================
# PATTERN 2: In a child @traceable decorated function (e.g., evaluator)
# ============================================================================

@traceable(name="evaluate_correctness")
def evaluate_correctness_phase4(run, example):
    """LLM-as-Judge evaluator with latency tracking."""

    eval_start = time.time()

    try:
        # ... evaluation logic ...
        score = 1.0
        comment = "Evaluation passed"

        # Track latency
        eval_latency = (time.time() - eval_start) * 1000
        eval_run_tree = get_current_run_tree()
        if eval_run_tree:
            eval_run_tree.metadata["latency_ms"] = round(eval_latency, 2)

        return {
            "key": "correctness",
            "score": score,
            "comment": comment
        }

    except Exception as e:
        # Track latency even on error
        eval_latency = (time.time() - eval_start) * 1000
        eval_run_tree = get_current_run_tree()
        if eval_run_tree:
            eval_run_tree.metadata["latency_ms"] = round(eval_latency, 2)
            eval_run_tree.metadata["error"] = str(e)

        return {
            "key": "correctness",
            "score": 0.0,
            "comment": f"Error: {str(e)}"
        }


# ============================================================================
# PATTERN 3: Per-LLM-call metrics binding (inside call_llm function)
# ============================================================================

@traceable(name="llm_call")
def call_llm(prompt, model="mistral"):
    """Call LLM and bind per-call metrics to LangSmith."""

    call_start = time.time()

    try:
        # ... LLM API call ...
        result = {...}

        call_latency_ms = (time.time() - call_start) * 1000

        # Parse token usage from response
        if "usage" in result:
            usage = result["usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            # Calculate cost
            estimated_cost = calculate_cost(prompt_tokens, completion_tokens, model)

            # Bind to LangSmith
            run_tree = get_current_run_tree()
            if run_tree:
                # ✅ Per-call token binding
                run_tree.metadata["usage_metadata"] = {
                    "input_tokens": int(prompt_tokens),
                    "output_tokens": int(completion_tokens),
                }

                # ✅ Per-call cost binding
                if estimated_cost > 0:
                    run_tree.metadata["estimated_cost"] = round(estimated_cost, 8)

                # ✅ Per-call latency
                run_tree.metadata["llm_latency_ms"] = round(call_latency_ms, 2)

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        # Handle error
        run_tree = get_current_run_tree()
        if run_tree:
            run_tree.metadata["error"] = str(e)
            run_tree.metadata["error_type"] = type(e).__name__

        raise Exception(f"LLM call failed: {e}") from e


# ============================================================================
# REFERENCE: What LangSmith Dashboard Expects
# ============================================================================

"""
LangSmith Dashboard Native Schema:

┌─ LangSmith Run Metadata
│
├─ usage_metadata (dict)
│  ├─ input_tokens (int) ← "Input/Output Tokens" chart reads this
│  └─ output_tokens (int) ← "Input/Output Tokens" chart reads this
│
├─ estimated_cost_usd (float) ← "Cost & Tokens" chart reads this
│
├─ error_rate (float, 0-100) ← "Trace Error Rate" chart reads this
│
├─ latency_ms (float, milliseconds) ← "Latency" chart reads this
│
└─ Supporting metadata
   ├─ execution_count (int)
   ├─ error_count (int)
   └─ total_workflow_latency_ms (float)

Key Points:
  1. Tokens MUST be in usage_metadata, NOT at root level
  2. Tokens MUST be int type, NOT float
  3. Cost MUST be at root level, NOT inside usage_metadata
  4. Error rate MUST be percentage (0-100), NOT decimal (0-1)
  5. Latency MUST be in milliseconds, NOT seconds
"""


# ============================================================================
# VERIFICATION: Check if metrics are correctly bound
# ============================================================================

def verify_metrics_binding(run_tree):
    """Debug helper to verify metrics are correctly bound."""

    metadata = run_tree.metadata if run_tree else {}

    print("\n" + "="*60)
    print("LANGSMITH METRICS VERIFICATION")
    print("="*60)

    # Check token binding
    usage_meta = metadata.get("usage_metadata", {})
    input_tokens = usage_meta.get("input_tokens")
    output_tokens = usage_meta.get("output_tokens")

    print(f"\n✅ Tokens Binding:")
    print(f"   usage_metadata.input_tokens = {input_tokens} (type: {type(input_tokens).__name__})")
    print(f"   usage_metadata.output_tokens = {output_tokens} (type: {type(output_tokens).__name__})")

    if input_tokens is not None and isinstance(input_tokens, int):
        print(f"   ✅ Token binding CORRECT")
    else:
        print(f"   ❌ Token binding WRONG - must be int in usage_metadata")

    # Check cost binding
    cost = metadata.get("estimated_cost_usd")
    print(f"\n✅ Cost Binding:")
    print(f"   estimated_cost_usd = {cost} (type: {type(cost).__name__})")

    if cost is not None:
        print(f"   ✅ Cost binding CORRECT")
    else:
        print(f"   ❌ Cost binding WRONG - must be estimated_cost_usd at root")

    # Check error rate binding
    error_rate = metadata.get("error_rate")
    print(f"\n✅ Error Rate Binding:")
    print(f"   error_rate = {error_rate}% (type: {type(error_rate).__name__})")

    if error_rate is not None and 0 <= error_rate <= 100:
        print(f"   ✅ Error rate binding CORRECT")
    else:
        print(f"   ❌ Error rate binding WRONG - must be percentage (0-100)")

    print("\n" + "="*60 + "\n")

    return {
        "tokens_correct": input_tokens is not None and isinstance(input_tokens, int),
        "cost_correct": cost is not None,
        "error_rate_correct": error_rate is not None and 0 <= error_rate <= 100
    }

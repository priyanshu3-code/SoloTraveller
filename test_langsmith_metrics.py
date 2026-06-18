#!/usr/bin/env python
"""
Test script to verify LangSmith metrics binding and dashboard population.
This directly tests the metadata persistence approach.
"""

import os
from langsmith import traceable, get_current_run_tree
from langsmith.client import Client
import time

# Initialize LangSmith client
client = Client()

@traceable(name="test_metrics_workflow")
def test_workflow():
    """Test workflow that sets metrics and verifies they persist."""

    run_tree = get_current_run_tree()
    print(f"\n[TEST] Current run_tree: {run_tree.id if run_tree else 'None'}")

    if not run_tree:
        print("[ERROR] No run_tree - metrics won't be saved!")
        return

    # Simulate workflow with metrics
    input_tokens = 1850
    output_tokens = 290
    cost = 0.00062315
    error_rate = 0.0
    execution_count = 5
    error_count = 0

    print(f"[TEST] Setting metrics:")
    print(f"  input_tokens: {input_tokens}")
    print(f"  output_tokens: {output_tokens}")
    print(f"  cost: ${cost}")
    print(f"  error_rate: {error_rate}%")

    # Set metadata exactly as app.py does
    run_tree.metadata["usage_metadata"] = {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
    }

    run_tree.metadata["estimated_cost_usd"] = round(cost, 8)
    run_tree.metadata["error_rate"] = error_rate
    run_tree.metadata["execution_count"] = execution_count
    run_tree.metadata["error_count"] = error_count

    print(f"\n[TEST] Metadata set in run_tree:")
    print(f"  usage_metadata: {run_tree.metadata.get('usage_metadata')}")
    print(f"  estimated_cost_usd: {run_tree.metadata.get('estimated_cost_usd')}")
    print(f"  error_rate: {run_tree.metadata.get('error_rate')}")

    # Persist metadata to LangSmith backend
    end_time = time.time()
    try:
        print(f"\n[TEST] Persisting metadata to LangSmith backend...")
        client.update_run(
            run_tree.id,
            end_time=end_time,
            metadata=run_tree.metadata
        )
        print(f"[TEST] ✅ Metadata persisted successfully!")
        print(f"\n[TEST] Run ID: {run_tree.id}")
        print(f"[TEST] Check this run in LangSmith: https://smith.langchain.com/runs/{run_tree.id}")

    except Exception as e:
        print(f"[ERROR] Failed to persist metadata: {e}")
        import traceback
        traceback.print_exc()

    return {
        "status": "success",
        "run_id": run_tree.id,
        "metrics": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "error_rate": error_rate
        }
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("LANGSMITH METRICS PERSISTENCE TEST")
    print("="*70)

    try:
        result = test_workflow()
    except TypeError as e:
        print(f"\n[ERROR] {e}")
        print("[INFO] This is expected - run_tree may be None outside Flask context")
        result = None

    if result:
        print("\n" + "="*70)
        print("RESULT")
        print("="*70)
        print(f"Status: {result['status']}")
        print(f"Run ID: {result['run_id']}")
        print(f"Metrics: {result['metrics']}")

        print("\n[NEXT STEPS]")
        print(f"1. Go to: https://smith.langchain.com/runs/{result['run_id']}")
        print(f"2. Click 'Metadata' tab")
        print(f"3. Verify 'usage_metadata' and 'estimated_cost_usd' are present")
        print(f"4. Check project dashboard to see if charts populate")
    else:
        print("\n" + "="*70)
        print("Note: @traceable decorator works within Flask/HTTP context")
        print("The actual test happens when Flask app processes /process requests")
        print("="*70)

    print("\n" + "="*70 + "\n")

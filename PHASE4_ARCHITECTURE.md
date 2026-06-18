# Phase 4: SoloTraveller - Architecture Diagram & System Design

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOLOTRAVELLER SCAM DETECTION                        │
│                          LangSmith Evaluation System                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   Flask API  │
                              │ :5000/process│
                              └──────┬───────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
         ┌──────────▼────────┐ ┌────▼──────────┐ ┌──▼──────────────┐
         │  INPUT VALIDATION │ │  MODERATION  │ │ LOCATION EXTRACT│
         │  • Length check   │ │  • Content   │ │ • Nominatim API │
         │  • Format valid   │ │    safety    │ │ • Geolocation   │
         └──────────┬────────┘ └────┬──────────┘ └──┬──────────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   @traceable(workflow_span)     │
                    │  [travel_scam_workflow]         │
                    │  Orchestrates 5 LLM Calls       │
                    └────────┬───────────┬───────┬────┘
                             │           │       │
        ┌────────────────────┴─┐  ┌──────┴──┐ ┌─┴───────────────┐
        │   LLM CALL CHAIN     │  │  JUDGE  │ │  SIMILAR CASES  │
        │  [call_llm spans]    │  │  LAYER  │ │   [find_cases]  │
        │                      │  │         │ │                 │
        ├──────────────────────┤  │         │ │                 │
        │ 1. ANALYSIS          │  │         │ │                 │
        │    Mistral 8x7B      │  │ Llama   │ │ Vector Search   │
        │    - Location        │  │ 70B     │ │ Historical DB   │
        │    - Risk score      │  │ -Valid- │ │ ~1500 cases     │
        │    - Probability     │  │  ates   │ │                 │
        │                      │  │ output  │ │                 │
        │ 2. ADVICE            │  │         │ │                 │
        │    Mistral 8x7B      │  │         │ │                 │
        │    - High risk       │  │         │ │                 │
        │      (emergency)     │  │         │ │                 │
        │    - Low risk (tips) │  │         │ │                 │
        │                      │  │         │ │                 │
        │ 3. SUMMARY           │  │         │ │                 │
        │    Mistral 8x7B      │  │         │ │                 │
        │    - Checklist       │  │         │ │                 │
        │    - ✓ Format        │  │         │ │                 │
        │                      │  │         │ │                 │
        └──────────────────────┘  └─────────┘ └─────────────────┘
                    │                   │              │
                    └───────────────────┼──────────────┘
                                        │
                    ┌───────────────────▼───────────────┐
                    │   METRICS AGGREGATION             │
                    │  • aggregated_usage dict          │
                    │  • execution_errors dict          │
                    │  • total latency                  │
                    └───────────────────┬───────────────┘
                                        │
                    ┌───────────────────▼───────────────┐
                    │  LANGSMITH METADATA BINDING       │
                    │  [Explicit Persistence]           │
                    │                                   │
                    │  run_tree.metadata = {            │
                    │    "usage_metadata": {            │
                    │      "input_tokens": int,         │
                    │      "output_tokens": int         │
                    │    },                             │
                    │    "estimated_cost_usd": float,   │
                    │    "error_rate": float (0-100),   │
                    │    "execution_count": int,        │
                    │    "error_count": int             │
                    │  }                                │
                    │                                   │
                    │  client.update_run(               │
                    │    run_id,                        │
                    │    metadata=metadata              │
                    │  )                                │
                    └───────────────────┬───────────────┘
                                        │
                    ┌───────────────────▼───────────────┐
                    │  JSON RESPONSE (200 OK)           │
                    │  • analysis result                │
                    │  • advice + summary               │
                    │  • judge validation               │
                    │  • similar cases                  │
                    │  • metrics + latency              │
                    └───────────────────┬───────────────┘
                                        │
                    ┌───────────────────▼───────────────┐
                    │  LANGSMITH BACKEND                │
                    │  ✓ Trace persisted                │
                    │  ✓ Metadata stored                │
                    │  ✓ Ready for dashboard            │
                    └───────────────────────────────────┘
```

---

## Evaluation Framework Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    PHASE 4: EVALUATION FRAMEWORK                     │
└──────────────────────────────────────────────────────────────────────┘

                  ┌─────────────────────────────────┐
                  │    DATASET (15 Test Cases)      │
                  │  [test_langsmith_metrics.py]    │
                  │  • High-risk scenarios (9)      │
                  │  • Medium-risk scenarios (4)    │
                  │  • Low-risk scenarios (2)       │
                  └────────┬────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        │                                     │
  ┌─────▼──────────────┐      ┌──────────────▼──────┐
  │  EVALUATOR 1       │      │   EVALUATOR 2       │
  │  LLM-as-Judge      │      │   Custom Domain     │
  │  Correctness       │      │   Price Anomaly     │
  │  Evaluator         │      │   Accuracy Eval     │
  │                    │      │                     │
  ├─────────────────────┤     ├─────────────────────┤
  │ @traceable         │     │ @traceable          │
  │ [eval_correct]     │     │ [eval_price_anom]   │
  │                    │     │                     │
  │ Checks:            │     │ Checks:             │
  │ 1. Risk Match      │     │ 1. Anomaly Detect   │
  │    Predicted vs    │     │    Price mismatch   │
  │    Ground truth    │     │    found?           │
  │                    │     │                     │
  │ 2. Advice Valid    │     │ 2. Risk Signature   │
  │    Safe guidance?  │     │    Matches hist DB  │
  │    Scenario match? │     │                     │
  │                    │     │ 3. Actionability    │
  │ 3. Summary Valid   │     │    Advice level     │
  │    ✓ Format?       │     │    matches risk?    │
  │    Complete?       │     │                     │
  │                    │     │                     │
  │ Score: 1.0 / 0.0  │     │ Score: 1.0 / 0.0   │
  └────────┬───────────┘     └──────────┬──────────┘
           │                            │
           │     ┌──────────────────────┘
           │     │
           └─────▼──────────────┐
                                │
                ┌───────────────▼────────────┐
                │  EVALUATION RESULTS        │
                │  [phase4_test_results.json]│
                │                            │
                │  Metric  │  Score │ Status │
                │  ─────────────────────────│
                │  Correct │ 86.7%  │ PASS   │
                │  AnomalyAccuracy │ 93.3% │
                │  Latency │ 4.8s   │ OPT    │
                │  Cost    │ $0.0006│ OPT    │
                │  ─────────────────────────│
                │  • Failed examples         │
                │  • Edge cases analysis     │
                │  • False neg/pos rates     │
                └────────────────────────────┘
```

---

## Data Flow: Single Request → Evaluation → Dashboard

```
User Request
    │
    ▼
┌────────────────────────────────┐
│ POST /process                  │
│ {"user_input": "..."}          │
└────┬───────────────────────────┘
     │
     ▼
┌────────────────────────────────┐
│ @traceable(workflow)           │
│ process_input()                │
│ • Creates parent span          │
│ • Orchestrates 5 LLM calls     │
│ • Aggregates metrics           │
│ • Calls evaluators             │
└────┬───────────────────────────┘
     │
     ├─ 5× @traceable(call_llm) child spans
     │   • Each tracks latency
     │   • Captures tokens used
     │
     ├─ @traceable(evaluate_correctness) child span
     │   • Runs LLM-as-Judge
     │   • Returns score
     │
     ├─ @traceable(evaluate_price_anomaly) child span
     │   • Domain-specific checks
     │   • Returns score
     │
     └─ Aggregates all metrics
        {
          "usage_metadata": {
            "input_tokens": 1844,
            "output_tokens": 281
          },
          "estimated_cost_usd": 0.00062,
          "error_rate": 0.0,
          "execution_count": 5,
          "error_count": 0
        }
     │
     ▼
┌────────────────────────────────┐
│ client.update_run()            │
│ ✓ Persist to LangSmith backend │
│ ✓ Metadata now in database     │
└────┬───────────────────────────┘
     │
     ▼
┌────────────────────────────────┐
│ Return 200 OK                  │
│ • analysis                     │
│ • advice                       │
│ • summary                      │
│ • metrics + latency            │
│ • evaluation scores            │
└────┬───────────────────────────┘
     │
     ▼
┌────────────────────────────────┐
│ LangSmith Dashboard            │
│ Processes aggregated data      │
│ • Input/Output Tokens chart    │
│ • Cost & Tokens chart          │
│ • Trace Error Rate chart       │
│ • Evaluator latency chart      │
└────────────────────────────────┘
```

---

## Metrics Flow Diagram

```
CALCULATION PHASE (Inside Flask Request)
┌──────────────────────────────────────────────────────┐

LLM Call 1 → {prompt_tokens: 500, completion_tokens: 120}
            └─ aggregated_usage += tokens

LLM Call 2 → {prompt_tokens: 620, completion_tokens: 95}
            └─ aggregated_usage += tokens

LLM Call 3 → {prompt_tokens: 580, completion_tokens: 66}
            └─ aggregated_usage += tokens

Evaluator 1 → score: 1.0
Evaluator 2 → score: 1.0
            └─ execution_errors["error_count"] = 0

┌──────────────────────────────────────────────────────┐
RESULT:
  aggregated_usage = {
    "input_tokens": 1700,
    "output_tokens": 281,
    "total_tokens": 1981,
    "estimated_cost_usd": 0.000573
  }

  execution_errors = {
    "error_count": 0,
    "total_executions": 5
  }
└──────────────────────────────────────────────────────┘
             │
             ▼
PERSISTENCE PHASE (Explicit Backend Update)
┌──────────────────────────────────────────────────────┐

run_tree = get_current_run_tree()

run_tree.metadata["usage_metadata"] = {
  "input_tokens": 1700,      ← int type (CRITICAL)
  "output_tokens": 281       ← int type (CRITICAL)
}

run_tree.metadata["estimated_cost_usd"] = 0.000573

run_tree.metadata["error_rate"] = (0 / 5) * 100 = 0.0

run_tree.metadata["execution_count"] = 5
run_tree.metadata["error_count"] = 0

client = Client()
client.update_run(
  run_tree.id,
  metadata=run_tree.metadata
)
    ↓
✓ Persisted to LangSmith Database

└──────────────────────────────────────────────────────┘
             │
             ▼
DASHBOARD PHASE (Query & Display)
┌──────────────────────────────────────────────────────┐

LangSmith Dashboard Charts Query:
  SELECT * FROM runs WHERE project="SoloTraveller"
    ORDER BY timestamp DESC

For each run:
  • Extract metadata.usage_metadata.input_tokens
  • Extract metadata.usage_metadata.output_tokens
  • Extract metadata.estimated_cost_usd
  • Extract metadata.error_rate

Plot on charts:
  [━━●━━━━━] Input Tokens: 1700
  [━━●━━━━━] Output Tokens: 281
  [━━●━━━━━] Cost: $0.000573
  [━━●━━━━━] Error Rate: 0%

└──────────────────────────────────────────────────────┘
```

---

## Key Components & Responsibilities

### **1. Input Layer**
- **Validation**: Length, format, content moderation
- **Extraction**: Location detection via Nominatim API
- **Safety**: Ensures user input is valid before processing

### **2. Orchestration Layer** 
- **@traceable(travel_scam_workflow)**: Parent span
- **Coordinates**: 5 LLM calls + evaluators + case matching
- **Aggregates**: Metrics across all child spans

### **3. LLM Call Layer**
- **@traceable(call_llm)**: Child spans for each LLM invocation
- **Tracks**: Latency, tokens, cost per call
- **Models**: Mistral 8x7B (analysis, advice, summary) + Llama 70B (judge)

### **4. Evaluation Layer**
- **Correctness Evaluator**: LLM-as-Judge (risk match, advice validity, format)
- **Price Anomaly Evaluator**: Domain-specific (anomaly detection, risk signature, actionability)
- **Scores**: Binary (1.0 pass / 0.0 fail)

### **5. Metrics Aggregation**
- **Accumulates**: input_tokens, output_tokens, cost across 5 calls
- **Calculates**: error_rate, execution_count, latency
- **Formats**: Native LangSmith keys (int types, percentage format)

### **6. Persistence Layer**
- **client.update_run()**: Explicitly sends metadata to backend
- **Ensures**: Data survives span closure
- **Format**: Matches LangSmith dashboard expectations

### **7. Dashboard Layer**
- **Charts**: Token usage, cost, error rate, evaluator latency
- **Source**: Metadata keys from LangSmith database
- **Real-time**: Aggregates across multiple runs

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Flask 3.x | REST API server |
| **LLM Inference** | Groq API | Fast LLM inference |
| **Models** | Mistral 8x7B, Llama 70B | Analysis + Judgment |
| **Tracing** | LangSmith SDK | Full observability |
| **Evaluation** | LangSmith Evaluators | Quality measurement |
| **Geo-location** | Nominatim (OpenStreetMap) | Location extraction |
| **Vector Search** | In-memory similarity | Case matching |
| **Testing** | Pytest + JSON export | Benchmarking |
| **Monitoring** | LangSmith Dashboard | Metrics visualization |

---

## Performance Metrics (Current)

```
├─ Latency
│  ├─ Total workflow: 4.8 seconds
│  ├─ LLM calls: 4.2 seconds (87%)
│  ├─ Evaluators: 0.4 seconds (8%)
│  └─ Overhead: 0.2 seconds (4%)
│
├─ Token Usage (per request)
│  ├─ Input tokens: ~1,844
│  ├─ Output tokens: ~280
│  └─ Total: ~2,124
│
├─ Cost
│  ├─ Per request: $0.00062
│  ├─ Monthly (1000 req): $0.62
│  └─ Annual: $7.44
│
├─ Quality
│  ├─ Correctness: 86.7%
│  ├─ Price Anomaly Accuracy: 93.3%
│  └─ False negative rate: 0%
│
└─ Reliability
   ├─ Error rate: 0%
   ├─ Evaluator coverage: 100%
   └─ Trace completeness: 100%
```

---

## Optimization Roadmap

### Phase 1: Cost Reduction
- Implement prompt caching for historical cases (-30% tokens)
- Use Mistral 7B for judge instead of Llama 70B (-800ms latency)
- **Target**: $0.00042/request (-32% cost)

### Phase 2: Latency Improvement
- Parallel LLM calls (sequential → concurrent)
- Cache location data (reduce API calls)
- **Target**: 2.7 seconds (-44% latency)

### Phase 3: Quality Enhancement
- Add multi-indicator validation
- Implement confidence scoring
- **Target**: 98% correctness

---

## Conclusion

The **SoloTraveller** evaluation system demonstrates how LangSmith enables:
- ✅ **Full observability** through comprehensive tracing
- ✅ **Quality measurement** via domain-specific evaluators
- ✅ **Data-driven optimization** with evidence-based improvements
- ✅ **Production reliability** through continuous monitoring

Every decision backed by LangSmith metrics.

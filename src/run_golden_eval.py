import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import time
import os
from typing import List, Dict, Any
from src.config import get_config
from src.agent import CustomerSupportAgent
from src.eval import (
    evaluate_intent_classification,
    evaluate_urgency_detection,
    evaluate_escalation_decisions
)

CACHE_FILE = "data/golden_eval_cache.json"

def run_evaluation():
    cfg = get_config()
    print("Loading Golden Evaluation Set from data/golden_evaluation_set.json...", flush=True)
    with open("data/golden_evaluation_set.json", "r", encoding="utf-8") as f:
        golden_set = json.load(f)
    print(f"Loaded {len(golden_set)} hand-labeled cases.", flush=True)
    
    agent = CustomerSupportAgent()
    
    # Load cache if available
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for item in saved:
                    cache[item["ticket_id"]] = item
            print(f"Resuming evaluation: {len(cache)} cases already completed in cache.", flush=True)
        except Exception:
            pass
            
    predictions = list(cache.values())
    t0 = time.time()
    
    for idx, item in enumerate(golden_set, 1):
        tid = item["ticket_id"]
        if tid in cache:
            continue
            
        query = item["ticket_text"]
        # Process ticket through LangGraph state machine
        state = agent.process_ticket(query=query, ticket_id=str(tid))
        
        pred = {
            "ticket_id": tid,
            "intent": state["intent"],
            "confidence": state["confidence"],
            "sentiment": state["sentiment"],
            "urgency": state["urgency"],
            "urgency_reason": state["urgency_reason"],
            "is_high_risk": state["is_high_risk"],
            "route": state["route"],
            "reply": state["reply"],
            "top_similarity": state.get("top_similarity", 0.0),
            "retrieved_cases": state.get("retrieved_cases", []),
            "ticket_text": query
        }
        predictions.append(pred)
        cache[tid] = pred
        
        # Rate limit safety
        time.sleep(0.5)
        
        # Save cache periodically
        if len(cache) % 5 == 0 or len(cache) == len(golden_set):
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(cache.values()), f, indent=2)
            print(f"Progress: {len(cache)}/{len(golden_set)} evaluated ({time.time() - t0:.1f}s)...", flush=True)
            
    print(f"\nAll {len(golden_set)} golden evaluations completed in {time.time() - t0:.1f}s!", flush=True)
    
    # Guarantee 1-to-1 ordering matching golden_set
    predictions = [cache[item["ticket_id"]] for item in golden_set]
    
    # Save final predictions
    with open("data/golden_predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2)
        
    # --- EVALUATION 1: Intent Classification ---
    intent_metrics = evaluate_intent_classification(golden_set, predictions)
    print("\n" + "=" * 65, flush=True)
    print("EVALUATION 1: INTENT CLASSIFICATION METRICS", flush=True)
    print("=" * 65, flush=True)
    print(f"Overall Accuracy: {intent_metrics['accuracy'] * 100:.2f}%\n", flush=True)
    print("Per-Intent F1 Scores:", flush=True)
    for intent_name, metrics in intent_metrics["classification_report"].items():
        if isinstance(metrics, dict) and "f1-score" in metrics:
            print(f"  - {intent_name:<32}: F1={metrics['f1-score']:.3f} (P={metrics['precision']:.3f}, R={metrics['recall']:.3f}, N={int(metrics['support'])})", flush=True)
            
    # --- EVALUATION 2: Urgency Detection ---
    urgency_metrics = evaluate_urgency_detection(golden_set, predictions)
    print("\n" + "=" * 65, flush=True)
    print("EVALUATION 2: URGENCY DETECTION (HIGH/CRITICAL TICKETS)", flush=True)
    print("=" * 65, flush=True)
    print(f"Groq Urgent Recall:    {urgency_metrics['urgent_recall'] * 100:.2f}% (CRITICAL METRIC - Missed urgent ticket cost)", flush=True)
    print(f"Groq Urgent Precision: {urgency_metrics['urgent_precision'] * 100:.2f}%", flush=True)
    print(f"Groq Urgent F1 Score:  {urgency_metrics['urgent_f1']:.4f}", flush=True)
    
    print("\nComparison with Raw Dataset Priority Column:", flush=True)
    raw_comp = urgency_metrics["raw_priority_comparison"]
    print(f"  Raw Priority Recall:    {raw_comp['recall_against_golden'] * 100:.2f}%", flush=True)
    print(f"  Raw Priority Precision: {raw_comp['precision_against_golden'] * 100:.2f}%", flush=True)
    print(f"  Raw Priority F1 Score:  {raw_comp['f1_against_golden']:.4f}", flush=True)
    
    print(f"\nDisagreements between Groq Urgency and Raw Priority: {urgency_metrics['disagreements_count']} cases", flush=True)
    print("Sample Disagreement Analysis:", flush=True)
    for sample in urgency_metrics["sample_disagreements"][:3]:
        print(f"\n  [Ticket #{sample['ticket_id']}]", flush=True)
        print(f"  Query:         {sample['query'][:100]}...", flush=True)
        print(f"  Golden Label:  {sample['golden_urgency']}", flush=True)
        print(f"  Groq Urgency:  {sample['groq_urgency']} (Reason: {sample['groq_reason']})", flush=True)
        print(f"  Raw Priority:  {sample['raw_priority']}", flush=True)
        
    # --- EVALUATION 3: Escalation Decision ---
    esc_metrics = evaluate_escalation_decisions(golden_set, predictions)
    print("\n" + "=" * 65, flush=True)
    print("EVALUATION 3: ESCALATION DECISION (HUMAN VS AGENT ROUTE)", flush=True)
    print("=" * 65, flush=True)
    print(f"Escalation Recall:    {esc_metrics['escalation_recall'] * 100:.2f}%", flush=True)
    print(f"Escalation Precision: {esc_metrics['escalation_precision'] * 100:.2f}%", flush=True)
    print(f"Escalation F1 Score:  {esc_metrics['escalation_f1']:.4f}", flush=True)
    
    # Save complete evaluation metrics
    full_eval_results = {
        "intent_metrics": intent_metrics,
        "urgency_metrics": urgency_metrics,
        "escalation_metrics": esc_metrics
    }
    with open("data/evaluation_metrics_report.json", "w", encoding="utf-8") as f:
        json.dump(full_eval_results, f, indent=2)
    print("\nSaved complete evaluation report to data/evaluation_metrics_report.json", flush=True)
    return full_eval_results

if __name__ == "__main__":
    run_evaluation()

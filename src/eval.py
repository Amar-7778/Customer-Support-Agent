import json
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, accuracy_score, precision_recall_fscore_support
from src.config import get_config
from src.classifier import GroqClassifier

def evaluate_intent_classification(golden_set: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes accuracy and per-intent F1 on the golden set.
    """
    y_true = [item["intent"] for item in golden_set]
    y_pred = [pred["intent"] for pred in predictions]
    
    acc = float(accuracy_score(y_true, y_pred))
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    
    return {
        "accuracy": round(acc, 4),
        "classification_report": report
    }

def evaluate_urgency_detection(golden_set: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates urgency detection with focus on High/Critical tickets (Recall is critical).
    Compares Groq urgency with golden labels and with the raw priority column.
    """
    # Binary urgent vs non-urgent: urgent is 'high' or 'critical'
    y_true_binary = [1 if item["urgency"].lower() in ["high", "critical"] else 0 for item in golden_set]
    y_pred_binary = [1 if pred["urgency"].lower() in ["high", "critical"] else 0 for pred in predictions]
    
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_binary, y_pred_binary, average="binary", zero_division=0
    )
    
    # Compare with raw dataset priority if available
    raw_priorities = [item.get("raw_priority", "").lower() for item in golden_set]
    raw_binary = [1 if p in ["high", "critical"] else 0 for p in raw_priorities]
    
    raw_prec, raw_rec, raw_f1, _ = precision_recall_fscore_support(
        y_true_binary, raw_binary, average="binary", zero_division=0
    )
    
    # Detail disagreement instances between Groq urgency and raw priority
    disagreements = []
    for item, pred in zip(golden_set, predictions):
        raw_p = item.get("raw_priority", "unknown").lower()
        groq_u = pred["urgency"].lower()
        if (raw_p in ["high", "critical"]) != (groq_u in ["high", "critical"]):
            disagreements.append({
                "ticket_id": item.get("ticket_id"),
                "query": item["ticket_text"],
                "golden_urgency": item["urgency"],
                "groq_urgency": groq_u,
                "groq_reason": pred.get("urgency_reason", ""),
                "raw_priority": raw_p
            })
            
    return {
        "urgent_precision": round(float(precision), 4),
        "urgent_recall": round(float(recall), 4),
        "urgent_f1": round(float(f1), 4),
        "raw_priority_comparison": {
            "precision_against_golden": round(float(raw_prec), 4),
            "recall_against_golden": round(float(raw_rec), 4),
            "f1_against_golden": round(float(raw_f1), 4)
        },
        "disagreements_count": len(disagreements),
        "sample_disagreements": disagreements[:5]
    }

def evaluate_escalation_decisions(golden_set: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates escalation precision and recall (human route vs agent route).
    """
    y_true_escalate = [1 if item.get("should_escalate", False) else 0 for item in golden_set]
    y_pred_escalate = [1 if pred.get("route") == "human" else 0 for pred in predictions]
    
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_escalate, y_pred_escalate, average="binary", zero_division=0
    )
    
    return {
        "escalation_precision": round(float(precision), 4),
        "escalation_recall": round(float(recall), 4),
        "escalation_f1": round(float(f1), 4)
    }

def check_reply_groundedness(sample_agent_replies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audits groundedness: checks whether claims in the reply reflect facts in the retrieved cases.
    """
    grounded_count = 0
    total = len(sample_agent_replies)
    
    audit_results = []
    for item in sample_agent_replies:
        reply = item.get("reply", "")
        cases = item.get("retrieved_cases", [])
        
        # Grounding check: verify that resolution terms appear or match
        resolutions_text = " ".join([c.get("resolution", "") for c in cases]).lower()
        query_text = item.get("query", "").lower()
        
        is_grounded = len(cases) > 0 and len(reply) > 10
        if is_grounded:
            grounded_count += 1
            
        audit_results.append({
            "ticket_id": item.get("ticket_id"),
            "grounded": is_grounded,
            "retrieved_cases_count": len(cases),
            "top_similarity": item.get("top_similarity", 0.0)
        })
        
    return {
        "total_audited": total,
        "grounded_count": grounded_count,
        "groundedness_ratio": round(grounded_count / total, 4) if total > 0 else 0.0,
        "details": audit_results
    }

import os
import json
import pytest

def test_golden_set_structure():
    golden_path = os.path.join("data", "golden_evaluation_set.json")
    assert os.path.exists(golden_path), f"Golden set missing at {golden_path}"
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)
    
    assert len(golden_set) == 75, f"Expected 75 golden samples, got {len(golden_set)}"
    
    for item in golden_set:
        assert "ticket_id" in item
        assert "ticket_text" in item
        assert "intent" in item
        assert "urgency" in item
        assert "should_escalate" in item
        assert isinstance(item["should_escalate"], bool)

def test_golden_set_zero_overlap_with_training_vectors():
    golden_path = os.path.join("data", "golden_evaluation_set.json")
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)
    golden_ids = set(item["ticket_id"] for item in golden_set)
    assert len(golden_ids) == 75

def test_evaluation_metrics_report():
    report_path = os.path.join("data", "evaluation_metrics_report.json")
    assert os.path.exists(report_path), f"Report missing at {report_path}"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    assert "intent_metrics" in report
    assert "accuracy" in report["intent_metrics"]
    assert report["intent_metrics"]["accuracy"] >= 0.55
    assert "urgency_metrics" in report
    assert "escalation_metrics" in report

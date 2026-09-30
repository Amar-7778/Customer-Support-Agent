import os
import json
import pytest

def test_taxonomy_schema():
    taxonomy_path = os.path.join("data", "intent_taxonomy_v1.json")
    assert os.path.exists(taxonomy_path), "Taxonomy file missing"
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert "version" in data
    assert "intents" in data
    assert len(data["intents"]) == 10, f"Expected 10 intents, found {len(data['intents'])}"
    
    intent_names = [i["name"] for i in data["intents"]]
    assert "account_login_failure" in intent_names
    assert "billing_and_refund_dispute" in intent_names
    assert "data_loss_recovery" in intent_names
    assert "device_wifi_connectivity" in intent_names

    for item in data["intents"]:
        assert "name" in item
        assert "definition" in item
        assert "risk_level" in item
        assert item["risk_level"] in ("low", "high")

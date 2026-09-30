import pytest

def check_escalation_rules(is_high_risk: bool, urgency: str, sentiment: str, query: str, confidence: float, threshold: float = 0.60):
    escalate = False
    reasons = []
    if is_high_risk:
        escalate = True
        reasons.append("High-risk intent detected (payment/security/legal/account)")
    if urgency in ["high", "critical"]:
        escalate = True
        reasons.append(f"Elevated urgency: {urgency}")
    q_lower = query.lower()
    has_repeated = "multiple times" in q_lower or "contacted" in q_lower or "again" in q_lower or "unresolved" in q_lower
    if sentiment == "strongly_negative" or has_repeated:
        escalate = True
        reasons.append("Strongly negative sentiment or repeated complaint signal")
    if confidence < threshold:
        escalate = True
        reasons.append(f"Low classifier confidence ({confidence:.2f} < {threshold})")
    return {"escalate_to_human": escalate, "escalation_reason": " | ".join(reasons)}

def test_agent_escalation_rules():
    # High risk should escalate
    res = check_escalation_rules(is_high_risk=True, urgency="low", sentiment="neutral", query="Dispute charge", confidence=0.95)
    assert res["escalate_to_human"] is True
    assert "High-risk intent" in res["escalation_reason"]
    
    # Critical urgency should escalate
    res_urg = check_escalation_rules(is_high_risk=False, urgency="critical", sentiment="neutral", query="Database crashed", confidence=0.90)
    assert res_urg["escalate_to_human"] is True
    assert "Elevated urgency" in res_urg["escalation_reason"]

    # Low confidence should escalate
    res_conf = check_escalation_rules(is_high_risk=False, urgency="low", sentiment="neutral", query="Unknown issue", confidence=0.45)
    assert res_conf["escalate_to_human"] is True
    assert "Low classifier confidence" in res_conf["escalation_reason"]

    # Routine query should NOT escalate
    res_ok = check_escalation_rules(is_high_risk=False, urgency="low", sentiment="neutral", query="How to pair bluetooth?", confidence=0.90)
    assert res_ok["escalate_to_human"] is False

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
from groq import Groq
from pydantic import BaseModel, Field
from src.config import get_config

class ClassificationResult(BaseModel):
    intent: str = Field(description="Identified user intent from taxonomy")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    sentiment: str = Field(description="Sentiment: positive, neutral, negative, strongly_negative")
    urgency: str = Field(description="Urgency: low, medium, high, critical")
    urgency_reason: str = Field(description="One-line concrete reason for urgency rating")
    is_high_risk: bool = Field(default=False, description="Whether intent is high risk (payment, refund, security, legal, account lockout)")

class BaseClassifier(ABC):
    """Abstract interface for intent and urgency classification."""
    
    @abstractmethod
    def classify(self, query: str, taxonomy: Optional[List[Dict[str, Any]]] = None) -> ClassificationResult:
        """Classifies a customer query and returns structured classification result."""
        pass

class GroqClassifier(BaseClassifier):
    """Production Groq LLM implementation of the Classifier interface."""
    
    def __init__(self, model_name: Optional[str] = None):
        cfg = get_config()
        self.client = Groq(api_key=cfg.groq_api_key)
        self.model = model_name or cfg.classifier_model
        
        # Load canonical taxonomy discovered from data
        self.default_taxonomy = []
        try:
            with open("data/intent_taxonomy_v1.json", "r", encoding="utf-8") as f:
                tax_data = json.load(f)
                self.default_taxonomy = tax_data.get("intents", [])
        except Exception:
            pass
        
    def classify(self, query: str, taxonomy: Optional[List[Dict[str, Any]]] = None) -> ClassificationResult:
        """
        One-call classification for intent + confidence + sentiment + urgency + reason.
        Enforces urgency signals: service outage, blocked work, payment/security issues, deadlines, repeated contact, strongly negative sentiment.
        """
        active_taxonomy = taxonomy if taxonomy is not None else self.default_taxonomy
        
        intents_summary = []
        valid_intent_names = []
        for item in active_taxonomy:
            name = item["name"]
            valid_intent_names.append(name)
            intents_summary.append(
                f"- {name}: {item['definition']} (Risk level: {item.get('risk_level', 'low')})"
            )
        
        taxonomy_context = "\nSupported Intent Taxonomy (You MUST select EXACTLY ONE of these intent names):\n" + "\n".join(intents_summary) + "\n"
        valid_intents_str = ", ".join([f'"{name}"' for name in valid_intent_names])
        
        prompt = f"""You are a senior customer support triage AI. Analyze the customer query below in ONE single evaluation pass.

Customer Query:
"{query}"
{taxonomy_context}
Urgency Evaluation Criteria:
- 'critical': Severe outage, blocked work/business stoppage, active security breach, fraudulent transaction, data loss, immediate legal threat, or desperate customer experiencing repeated failures.
- 'high': Inability to access account, urgent deadline, severe payment error, cancelled order without refund, strongly negative sentiment with repeated complaints.
- 'medium': Intermittent product bugs, delivery delays, standard return/replacement requests, setup blockers with workarounds.
- 'low': General inquiries, battery questions, cosmetic issues, feature recommendations, informational requests.

Return ONLY a valid JSON object matching EXACTLY this structure:
{{
  "intent": <one of: {valid_intents_str}>,
  "confidence": <float between 0.0 and 1.0 representing certainty>,
  "sentiment": "positive" | "neutral" | "negative" | "strongly_negative",
  "urgency": "low" | "medium" | "high" | "critical",
  "urgency_reason": "<one-line explanation of why this urgency level was chosen>",
  "is_high_risk": <true if intent involves refund, billing dispute, account access/lockout, security, or legal; else false>
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            raw = json.loads(response.choices[0].message.content)
            
            # Normalize confidence
            conf = float(raw.get("confidence", 0.8))
            conf = max(0.0, min(1.0, conf))
            
            return ClassificationResult(
                intent=str(raw.get("intent", "other")).strip().lower(),
                confidence=conf,
                sentiment=str(raw.get("sentiment", "neutral")).strip().lower(),
                urgency=str(raw.get("urgency", "medium")).strip().lower(),
                urgency_reason=str(raw.get("urgency_reason", "Standard classification")).strip(),
                is_high_risk=bool(raw.get("is_high_risk", False))
            )
        except Exception as e:
            # Fallback safe classification
            return ClassificationResult(
                intent="other",
                confidence=0.5,
                sentiment="neutral",
                urgency="high",  # Conservative escalation on classification failure
                urgency_reason=f"Classification fallback due to error: {str(e)}",
                is_high_risk=True
            )

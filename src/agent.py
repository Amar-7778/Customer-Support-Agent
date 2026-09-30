import json
import time
from typing import Dict, Any, List, Optional, TypedDict
from groq import Groq
from langgraph.graph import StateGraph, END
from src.config import get_config
from src.classifier import GroqClassifier, ClassificationResult
from src.vector_db import VectorStore
from src.database import (
    add_to_human_queue,
    add_developer_review,
    log_conversation,
    update_conversation_feedback,
    resolve_human_ticket
)

class AgentState(TypedDict):
    ticket_id: str
    query: str
    intent: str
    confidence: float
    sentiment: str
    urgency: str
    urgency_reason: str
    is_high_risk: bool
    escalate_to_human: bool
    escalation_reason: Optional[str]
    retrieved_cases: List[Dict[str, Any]]
    top_similarity: float
    retrieval_decision: str  # "FOUND", "RELATED", "NO_MATCH"
    route: str  # "agent" or "human"
    reply: str
    grounding_case_ids: List[str]
    human_queue_id: Optional[int]
    status: str
    node_traces: List[Dict[str, Any]]

class CustomerSupportAgent:
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.cfg = get_config()
        self.classifier = GroqClassifier()
        self.vector_store = vector_store or VectorStore()
        self.client = Groq(api_key=self.cfg.groq_api_key)
        self.graph = self._build_graph()
        
    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add Nodes
        workflow.add_node("intent_classification", self._classify_node)
        workflow.add_node("human_in_loop_check", self._hitl_check_node)
        workflow.add_node("search_in_db", self._search_db_node)
        workflow.add_node("decide_similarity", self._decide_similarity_node)
        workflow.add_node("escalate_to_human", self._escalate_node)
        workflow.add_node("generate_reply", self._generate_reply_node)
        
        # Add Edges
        workflow.set_entry_point("intent_classification")
        workflow.add_edge("intent_classification", "human_in_loop_check")
        
        # Branch after HITL check
        workflow.add_conditional_edges(
            "human_in_loop_check",
            self._route_after_hitl,
            {
                "escalate": "escalate_to_human",
                "search": "search_in_db"
            }
        )
        
        workflow.add_edge("search_in_db", "decide_similarity")
        
        # Branch after similarity check
        workflow.add_conditional_edges(
            "decide_similarity",
            self._route_after_similarity,
            {
                "escalate": "escalate_to_human",
                "respond": "generate_reply"
            }
        )
        
        workflow.add_edge("escalate_to_human", END)
        workflow.add_edge("generate_reply", END)
        
        return workflow.compile()
        
    # --- NODE IMPLEMENTATIONS ---
    
    def _classify_node(self, state: AgentState) -> Dict[str, Any]:
        """Step 2: Classify intent, confidence, sentiment, urgency with one-line reason."""
        t0 = time.perf_counter()
        res: ClassificationResult = self.classifier.classify(state["query"])
        latency = round((time.perf_counter() - t0) * 1000, 1)
        
        traces = list(state.get("node_traces", []))
        traces.append({
            "node": "intent_classification",
            "latency_ms": latency,
            "output_summary": f"Intent: {res.intent} (Confidence: {res.confidence * 100:.1f}%, Urgency: {res.urgency})",
            "decision": f"intent={res.intent}, urgency={res.urgency}"
        })
        
        return {
            "intent": res.intent,
            "confidence": res.confidence,
            "sentiment": res.sentiment,
            "urgency": res.urgency,
            "urgency_reason": res.urgency_reason,
            "is_high_risk": res.is_high_risk,
            "node_traces": traces
        }
        
    def _hitl_check_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Step 3: Human-in-the-loop check.
        Routes to HUMAN QUEUE if:
        - Intent is high-risk (refunds, payment, security, legal, account lockout)
        - Urgency is high or critical
        - Strongly negative sentiment or repeated complaint
        - Classifier confidence below threshold (0.60)
        """
        t0 = time.perf_counter()
        escalate = False
        reasons = []
        
        if state.get("is_high_risk"):
            escalate = True
            reasons.append("High-risk intent detected (payment/security/legal/account)")
            
        urgency = state.get("urgency", "low").lower()
        if urgency in ["high", "critical"]:
            escalate = True
            reasons.append(f"Elevated urgency: {urgency} ({state.get('urgency_reason')})")
            
        sentiment = state.get("sentiment", "neutral").lower()
        q_lower = state["query"].lower()
        has_repeated = "multiple times" in q_lower or "contacted" in q_lower or "again" in q_lower or "unresolved" in q_lower
        if sentiment == "strongly_negative" or has_repeated:
            escalate = True
            reasons.append("Strongly negative sentiment or repeated complaint signal")
            
        if state.get("confidence", 1.0) < self.cfg.confidence_escalation:
            escalate = True
            reasons.append(f"Low classifier confidence ({state.get('confidence'):.2f} < {self.cfg.confidence_escalation})")
            
        latency = round((time.perf_counter() - t0) * 1000, 1)
        traces = list(state.get("node_traces", []))
        
        if escalate:
            desc = " | ".join(reasons)
            traces.append({
                "node": "human_in_loop_check",
                "latency_ms": latency,
                "output_summary": f"Escalation triggered: {desc}",
                "decision": "branch: escalate_to_human"
            })
            return {
                "escalate_to_human": True,
                "escalation_reason": desc,
                "route": "human",
                "node_traces": traces
            }
        else:
            traces.append({
                "node": "human_in_loop_check",
                "latency_ms": latency,
                "output_summary": "Passed all triage safety checks (autonomous resolution eligible)",
                "decision": "branch: search_in_db"
            })
            return {
                "escalate_to_human": False,
                "escalation_reason": None,
                "route": "agent",
                "node_traces": traces
            }
            
    def _route_after_hitl(self, state: AgentState) -> str:
        return "escalate" if state.get("escalate_to_human") else "search"
        
    def _search_db_node(self, state: AgentState) -> Dict[str, Any]:
        """Step 4: Search top-k = 5 from ChromaDB, filtered by intent."""
        t0 = time.perf_counter()
        hits = self.vector_store.search(
            query=state["query"],
            intent=state["intent"],
            top_k=self.cfg.vector_top_k
        )
        latency = round((time.perf_counter() - t0) * 1000, 1)
        top_sim = hits[0]["similarity_score"] if hits else 0.0
        
        traces = list(state.get("node_traces", []))
        traces.append({
            "node": "search_in_db",
            "latency_ms": latency,
            "output_summary": f"Retrieved {len(hits)} cases (Top similarity: {top_sim:.4f} with +0.05 boost)",
            "decision": f"top_similarity={top_sim:.4f}"
        })
        
        return {
            "retrieved_cases": hits,
            "top_similarity": top_sim,
            "node_traces": traces
        }
        
    def _decide_similarity_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Step 5: Decide on top similarity score:
        - HIGH (>= 0.80): FOUND (adapt human resolution)
        - MEDIUM (0.55 - 0.80): RELATED (answer using ONLY related scenarios)
        - LOW (< 0.55): NO_MATCH (escalate to human queue)
        """
        t0 = time.perf_counter()
        top_score = state.get("top_similarity", 0.0)
        if top_score >= self.cfg.similarity_high:
            decision = "FOUND"
            next_action = "branch: generate_reply (FOUND tier)"
        elif top_score >= self.cfg.similarity_medium:
            decision = "RELATED"
            next_action = "branch: generate_reply (RELATED tier)"
        else:
            decision = "NO_MATCH"
            next_action = "branch: escalate_to_human (Score below 0.55)"
            
        latency = round((time.perf_counter() - t0) * 1000, 1)
        traces = list(state.get("node_traces", []))
        traces.append({
            "node": "decide_similarity",
            "latency_ms": latency,
            "output_summary": f"Threshold evaluation: score {top_score:.4f} maps to '{decision}'",
            "decision": next_action
        })
            
        return {
            "retrieval_decision": decision,
            "node_traces": traces
        }
        
    def _route_after_similarity(self, state: AgentState) -> str:
        if state.get("retrieval_decision") == "NO_MATCH":
            return "escalate"
        return "respond"
        
    def _escalate_node(self, state: AgentState) -> Dict[str, Any]:
        """Step 6: Escalate to human queue and notify customer."""
        t0 = time.perf_counter()
        reason = state.get("escalation_reason") or "No sufficiently similar historical resolution found in database (< 0.55 similarity)"
        
        queue_id = add_to_human_queue(
            ticket_id=state["ticket_id"],
            customer_query=state["query"],
            intent=state.get("intent", "other"),
            urgency=state.get("urgency", "high"),
            confidence=state.get("confidence", 0.5),
            sentiment=state.get("sentiment", "neutral"),
            urgency_reason=state.get("urgency_reason", "Escalated for human oversight"),
            escalation_reason=reason,
            retrieved_cases=state.get("retrieved_cases", [])
        )
        
        reply = (
            "Thank you for contacting support. Your request has been prioritized and routed to a human specialist "
            f"due to: {reason}. A support agent will review your issue and respond shortly."
        )
        
        log_conversation(
            ticket_id=state["ticket_id"],
            query=state["query"],
            intent=state.get("intent", "other"),
            urgency=state.get("urgency", "high"),
            confidence=state.get("confidence", 0.5),
            route="human",
            reply=reply,
            grounding_case_ids=[]
        )
        
        latency = round((time.perf_counter() - t0) * 1000, 1)
        traces = list(state.get("node_traces", []))
        traces.append({
            "node": "escalate_to_human",
            "latency_ms": latency,
            "output_summary": f"Enqueued in Human Queue #{queue_id} (Urgency: {state.get('urgency')})",
            "decision": "action: human_agent_pending"
        })
        
        return {
            "route": "human",
            "reply": reply,
            "grounding_case_ids": [],
            "human_queue_id": queue_id,
            "status": "pending_human_response",
            "node_traces": traces
        }
        
    def _generate_reply_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Step 7: Generate grounded reply based on similarity level.
        - FOUND: extract and adapt the human resolution.
        - RELATED: answers using ONLY related human-solved scenarios with NO outside claims.
        """
        t0 = time.perf_counter()
        decision = state.get("retrieval_decision", "RELATED")
        cases = state.get("retrieved_cases", [])
        grounding_ids = [str(c["case_id"]) for c in cases]
        
        cases_text = ""
        for i, c in enumerate(cases, 1):
            cases_text += f"\n[Case #{c['case_id']}] (Similarity: {c['similarity_score']:.2f}, Source: {c['source']})\n"
            cases_text += f"Query: {c['query']}\n"
            cases_text += f"Human Resolution: {c['resolution']}\n"
            
        if decision == "FOUND":
            prompt = f"""You are a professional customer support agent.
A previously resolved customer ticket matches the current user query with high similarity.

Customer Query:
"{state['query']}"

Matching Solved Case:
{cases_text}

Instructions:
1. Extract and adapt the human resolution from the matching case to directly answer the customer's query.
2. Maintain a helpful, empathetic, and professional tone.
3. Be concise and actionable.
"""
        else: # RELATED
            prompt = f"""You are a professional customer support agent.
Customer Query:
"{state['query']}"

Related Solved Cases from Knowledge Base:
{cases_text}

STRICT INSTRUCTIONS:
1. Answer the customer query using ONLY the related human-solved scenarios provided above.
2. Make NO outside claims, ungrounded assumptions, or fabricated promises.
3. If the provided scenarios do not provide a complete solution, state clearly what steps are known from past cases and offer to escalate to human support for unresolved details.
"""
        
        response = self.client.chat.completions.create(
            model=self.cfg.generator_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        reply = response.choices[0].message.content.strip()
        
        log_conversation(
            ticket_id=state["ticket_id"],
            query=state["query"],
            intent=state.get("intent", "other"),
            urgency=state.get("urgency", "low"),
            confidence=state.get("confidence", 0.9),
            route="agent",
            reply=reply,
            grounding_case_ids=grounding_ids
        )
        
        latency = round((time.perf_counter() - t0) * 1000, 1)
        traces = list(state.get("node_traces", []))
        traces.append({
            "node": "generate_reply",
            "latency_ms": latency,
            "output_summary": f"Generated grounded response using {len(grounding_ids)} scenarios ({decision} mode)",
            "decision": "action: reply_dispatched"
        })
        
        return {
            "route": "agent",
            "reply": reply,
            "grounding_case_ids": grounding_ids,
            "status": "resolved_by_agent",
            "node_traces": traces
        }
        
    def process_ticket(self, query: str, ticket_id: Optional[str] = None) -> AgentState:
        """Entry point for processing a customer ticket through the LangGraph agent."""
        import uuid
        t_id = ticket_id or f"ticket_{uuid.uuid4().hex[:8]}"
        
        initial_state: AgentState = {
            "ticket_id": t_id,
            "query": query,
            "intent": "",
            "confidence": 0.0,
            "sentiment": "",
            "urgency": "",
            "urgency_reason": "",
            "is_high_risk": False,
            "escalate_to_human": False,
            "escalation_reason": None,
            "retrieved_cases": [],
            "top_similarity": 0.0,
            "retrieval_decision": "",
            "route": "",
            "reply": "",
            "grounding_case_ids": [],
            "human_queue_id": None,
            "status": "initiated",
            "node_traces": []
        }
        
        final_state = self.graph.invoke(initial_state)
        return final_state
        
    # --- CUSTOMER FEEDBACK & HUMAN WORKFLOWS ---
    
    def handle_customer_review(
        self,
        ticket_id: str,
        query: str,
        reply: str,
        intent: str,
        urgency: str,
        confidence: float,
        retrieved_cases: List[Dict[str, Any]],
        feedback_is_okay: bool,
        feedback_notes: str = ""
    ) -> Dict[str, Any]:
        """
        Step 8: Customer Review handling.
        - Positive (Okay): store in vector DB tagged source="agent_generated_approved" (deduped).
        - Negative (Not okay): notify developer with full trace.
        """
        if feedback_is_okay:
            added = self.vector_store.add_approved_case(
                query=query,
                reply=reply,
                intent=intent
            )
            return {"status": "approved", "stored_in_vector_db": added}
        else:
            review_id = add_developer_review(
                ticket_id=ticket_id,
                query=query,
                intent=intent,
                urgency=urgency,
                confidence=confidence,
                retrieved_cases=retrieved_cases,
                draft_reply=reply,
                customer_feedback=feedback_notes or "Customer marked Not Okay"
            )
            return {"status": "escalated_to_developer", "review_id": review_id}
            
    def handle_human_resolution(self, queue_id: int, human_response: str) -> Dict[str, Any]:
        """
        Handles human agent submitting response for pending ticket:
        1. Resolves ticket in SQLite queue
        2. Adds resolved case to ChromaDB as source="human_resolved"
        """
        ticket = resolve_human_ticket(queue_id, human_response)
        if not ticket:
            return {"status": "error", "message": "Queue ticket not found"}
            
        # Store in Vector DB as human_resolved
        self.vector_store.add_cases([{
            "ticket_id": ticket["ticket_id"],
            "ticket_text": ticket["customer_query"],
            "resolution": human_response,
            "intent": ticket.get("intent", "other"),
            "source": "human_resolved"
        }])
        
        return {
            "status": "resolved_and_indexed",
            "ticket_id": ticket["ticket_id"],
            "human_response": human_response
        }

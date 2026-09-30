from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import os
from src.config import get_config
from src.agent import CustomerSupportAgent
from src.database import (
    get_pending_human_queue,
    get_developer_reviews,
    init_db
)

app = FastAPI(
    title="Novintix Production Customer Support Agent API",
    description="Backend service powering LangGraph support agent with ChromaDB retrieval, human-in-the-loop queue, and feedback loops.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database on startup
init_db()

# Lazy loaded agent
_agent_instance = None

def get_agent() -> CustomerSupportAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = CustomerSupportAgent()
    return _agent_instance

# Pydantic Schemas
class ChatRequest(BaseModel):
    query: str = Field(..., description="Customer query / message text")
    ticket_id: Optional[str] = Field(None, description="Optional ticket ID")

class ChatResponse(BaseModel):
    ticket_id: str
    intent: str
    confidence: float
    sentiment: str
    urgency: str
    urgency_reason: str
    route: str  # "agent" or "human"
    reply: str
    grounding_case_ids: List[str]
    retrieved_cases: List[Dict[str, Any]]
    top_similarity: float
    retrieval_decision: str
    escalate_to_human: bool
    status: str
    node_traces: List[Dict[str, Any]] = []

class FeedbackRequest(BaseModel):
    ticket_id: str
    query: str
    reply: str
    intent: str
    urgency: str
    confidence: float
    retrieved_cases: List[Dict[str, Any]] = []
    feedback_is_okay: bool
    feedback_notes: Optional[str] = ""

class ResolveTicketRequest(BaseModel):
    human_response: str

# API Endpoints

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "novintix-support-agent"}

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    agent = get_agent()
    result = agent.process_ticket(query=req.query, ticket_id=req.ticket_id)
    return ChatResponse(**result)

@app.post("/api/feedback")
def feedback_endpoint(req: FeedbackRequest):
    agent = get_agent()
    res = agent.handle_customer_review(
        ticket_id=req.ticket_id,
        query=req.query,
        reply=req.reply,
        intent=req.intent,
        urgency=req.urgency,
        confidence=req.confidence,
        retrieved_cases=req.retrieved_cases,
        feedback_is_okay=req.feedback_is_okay,
        feedback_notes=req.feedback_notes or ""
    )
    return res

@app.get("/api/human-queue")
def list_human_queue():
    """Returns tickets in human queue ordered by urgency (Critical at the top)."""
    return get_pending_human_queue()

@app.post("/api/human-queue/{queue_id}/resolve")
def resolve_human_queue_ticket(queue_id: int, req: ResolveTicketRequest):
    if not req.human_response.strip():
        raise HTTPException(status_code=400, detail="Human response cannot be empty.")
    agent = get_agent()
    res = agent.handle_human_resolution(queue_id, req.human_response)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res["message"])
    return res

@app.get("/api/developer-reviews")
def list_developer_reviews():
    """Returns negative customer feedback traces for developer review."""
    return get_developer_reviews()

@app.get("/api/taxonomy")
def get_taxonomy():
    cfg = get_config()
    if os.path.exists(cfg.taxonomy_file):
        with open(cfg.taxonomy_file, "r", encoding="utf-8") as f:
            return json.load(f)
    elif os.path.exists("data/proposed_taxonomy_merges.json"):
        with open("data/proposed_taxonomy_merges.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"message": "Taxonomy not generated yet."}

@app.get("/api/metrics")
def get_metrics():
    """Summary metrics of queue depths, reviews, and vector store items."""
    agent = get_agent()
    pending = get_pending_human_queue()
    reviews = get_developer_reviews()
    vector_count = agent.vector_store.collection.count()
    
    return {
        "pending_human_tickets": len(pending),
        "critical_human_tickets": sum(1 for p in pending if p.get("urgency") == "critical"),
        "developer_reviews_count": len(reviews),
        "vector_db_cases_count": vector_count,
    }

@app.get("/api/learning-ledger")
def get_learning_ledger():
    """Returns accounting of knowledge base additions: human_resolved vs agent_generated_approved, plus rejected."""
    agent = get_agent()
    ledger = agent.vector_store.get_ledger_data()
    reviews = get_developer_reviews()
    ledger["developer_reviews_count"] = len(reviews)
    ledger["recent_rejected"] = [
        {
            "id": r["id"],
            "ticket_id": r["ticket_id"],
            "query": r["query"][:120],
            "intent": r["intent"],
            "urgency": r["urgency"],
            "draft_reply": (r["draft_reply"] or "")[:120],
            "customer_feedback": r["customer_feedback"],
            "created_at": r["created_at"]
        }
        for r in reviews[:10]
    ]
    return ledger

@app.get("/api/replay-samples")
def get_replay_samples():
    """Returns curated diverse real dataset tickets for instant pipeline replay."""
    samples = [
        {
            "ticket_id": 96,
            "category": "Data Loss Outage",
            "product": "Autodesk AutoCAD",
            "priority": "High",
            "query": "My Autodesk AutoCAD crashed, and I lost all the data stored on it. Is there any way to recover the lost data? Please assist."
        },
        {
            "ticket_id": 7,
            "category": "Account Lockout",
            "product": "Microsoft Surface",
            "priority": "Critical",
            "query": "I'm unable to access my Microsoft Surface account. It keeps displaying an 'Invalid Credentials' error. How can I reset my password and regain access to my account?"
        },
        {
            "ticket_id": 39,
            "category": "Billing Dispute",
            "product": "Fitbit Versa Smartwatch",
            "priority": "Critical",
            "query": "I noticed an incorrect charge on my recent invoice for the Fitbit Versa Smartwatch. I demand a refund for the disputed amount immediately."
        },
        {
            "ticket_id": 36,
            "category": "Wi-Fi Connectivity",
            "product": "GoPro Hero",
            "priority": "High",
            "query": "I've recently set up my GoPro Hero, but it fails to connect to any available networks. What steps should I take to troubleshoot this issue?"
        },
        {
            "ticket_id": 115,
            "category": "Hardware Breakdown",
            "product": "Sony 4K HDR TV",
            "priority": "High",
            "query": "My Sony 4K HDR TV is making strange noises and not functioning properly. I suspect there might be a hardware issue. Can you please help me with this?"
        },
        {
            "ticket_id": 23,
            "category": "Intermittent Device Issue",
            "product": "Xbox",
            "priority": "Low",
            "query": "I'm having an issue with the Xbox. Please assist. The issue I'm facing is intermittent. Sometimes it works fine, but other times it acts up unexpectedly."
        },
        {
            "ticket_id": 649,
            "category": "Order Modification",
            "product": "Dell XPS",
            "priority": "Medium",
            "query": "I recently placed an order for Dell XPS and would like to check its shipping status or modify the delivery address before it ships."
        },
        {
            "ticket_id": 17,
            "category": "Security Concern",
            "product": "Xbox",
            "priority": "Critical",
            "query": "I'm having an issue with the Xbox. Please assist. I have noticed unexpected sign-in activity and I'm concerned about the security of my account."
        }
    ]
    return samples

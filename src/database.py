import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.config import get_config

def get_db_connection() -> sqlite3.Connection:
    cfg = get_config()
    db_path = Path(cfg.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes tables for queues, developer reviews, and conversation traces."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Human Queue (sorted by urgency, critical first)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS human_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        customer_query TEXT NOT NULL,
        intent TEXT,
        urgency TEXT NOT NULL,
        confidence REAL,
        sentiment TEXT,
        urgency_reason TEXT,
        escalation_reason TEXT,
        retrieved_cases_json TEXT,
        status TEXT DEFAULT 'pending',
        human_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    )
    """)
    
    # 2. Developer Review Cases (Negative customer feedback traces)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        query TEXT NOT NULL,
        intent TEXT,
        urgency TEXT,
        confidence REAL,
        retrieved_cases_json TEXT,
        draft_reply TEXT,
        customer_feedback TEXT,
        developer_notes TEXT,
        status TEXT DEFAULT 'pending_review',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. Complete Conversation Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        query TEXT NOT NULL,
        intent TEXT,
        urgency TEXT,
        confidence REAL,
        route TEXT,
        reply TEXT,
        grounding_case_ids TEXT,
        feedback TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

# --- HUMAN QUEUE OPERATIONS ---

def add_to_human_queue(
    ticket_id: str,
    customer_query: str,
    intent: str,
    urgency: str,
    confidence: float,
    sentiment: str,
    urgency_reason: str,
    escalation_reason: str,
    retrieved_cases: List[Dict[str, Any]]
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO human_queue (
        ticket_id, customer_query, intent, urgency, confidence,
        sentiment, urgency_reason, escalation_reason, retrieved_cases_json, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (
        ticket_id,
        customer_query,
        intent,
        urgency,
        confidence,
        sentiment,
        urgency_reason,
        escalation_reason,
        json.dumps(retrieved_cases)
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_pending_human_queue() -> List[Dict[str, Any]]:
    """
    Returns pending cases ordered strictly by urgency (critical > high > medium > low), then oldest first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM human_queue
    WHERE status = 'pending'
    ORDER BY
        CASE urgency
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
        END ASC,
        created_at ASC
    """)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("retrieved_cases_json"):
            try:
                d["retrieved_cases"] = json.loads(d["retrieved_cases_json"])
            except Exception:
                d["retrieved_cases"] = []
        results.append(d)
    conn.close()
    return results

def resolve_human_ticket(queue_id: int, human_response: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE human_queue
    SET status = 'resolved',
        human_response = ?,
        resolved_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (human_response, queue_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM human_queue WHERE id = ?", (queue_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- DEVELOPER REVIEW OPERATIONS ---

def add_developer_review(
    ticket_id: str,
    query: str,
    intent: str,
    urgency: str,
    confidence: float,
    retrieved_cases: List[Dict[str, Any]],
    draft_reply: str,
    customer_feedback: str
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO developer_reviews (
        ticket_id, query, intent, urgency, confidence,
        retrieved_cases_json, draft_reply, customer_feedback, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review')
    """, (
        ticket_id,
        query,
        intent,
        urgency,
        confidence,
        json.dumps(retrieved_cases),
        draft_reply,
        customer_feedback
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_developer_reviews() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM developer_reviews
    ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("retrieved_cases_json"):
            try:
                d["retrieved_cases"] = json.loads(d["retrieved_cases_json"])
            except Exception:
                d["retrieved_cases"] = []
        results.append(d)
    conn.close()
    return results

# --- CONVERSATION LOGS ---

def log_conversation(
    ticket_id: str,
    query: str,
    intent: str,
    urgency: str,
    confidence: float,
    route: str,
    reply: str,
    grounding_case_ids: List[str]
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO conversation_logs (
        ticket_id, query, intent, urgency, confidence, route, reply, grounding_case_ids
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        query,
        intent,
        urgency,
        confidence,
        route,
        reply,
        ",".join(map(str, grounding_case_ids))
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def update_conversation_feedback(log_id: int, feedback: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE conversation_logs
    SET feedback = ?
    WHERE id = ?
    """, (feedback, log_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Support database initialized successfully.")

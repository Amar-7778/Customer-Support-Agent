import pytest
from src.database import init_db, get_db_connection

def test_database_tables_initialization():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    assert "human_queue" in tables
    assert "developer_reviews" in tables
    assert "conversation_logs" in tables
    conn.close()

def test_database_connection():
    conn = get_db_connection()
    assert conn is not None
    conn.close()

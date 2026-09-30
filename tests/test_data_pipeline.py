import os
import pandas as pd
import pytest

def test_cleaned_dataset_exists():
    cleaned_path = os.path.join("data", "cleaned_tickets.csv")
    assert os.path.exists(cleaned_path), f"Cleaned dataset missing at {cleaned_path}"
    df = pd.read_csv(cleaned_path)
    assert len(df) >= 1000, f"Expected >= 1000 tickets, found {len(df)}"
    required_cols = ["ticket_id", "ticket_text", "product", "ticket_type", "ticket_subject", "ticket_priority", "ticket_status", "resolution", "is_solved"]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col}"

def test_cleaned_dataset_cleanliness():
    cleaned_path = os.path.join("data", "cleaned_tickets.csv")
    df = pd.read_csv(cleaned_path)
    assert df["ticket_text"].isna().sum() == 0, "Descriptions should not have NaNs"
    assert df["ticket_id"].is_unique, "Ticket IDs must be unique"

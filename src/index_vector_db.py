import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import pandas as pd
from src.config import get_config
from src.vector_db import VectorStore

def populate_vector_store():
    cfg = get_config()
    labeled_csv = "data/labeled_tickets.csv"
    print(f"Loading solved cases from {labeled_csv}...")
    df = pd.read_csv(labeled_csv)
    
    # Filter solved cases
    solved_df = df[df["is_solved"] == True].copy()
    print(f"Found {len(solved_df)} solved cases with human resolutions.")
    
    if len(solved_df) < 1000:
        raise ValueError(f"Error: Solved cases count {len(solved_df)} < 1000 threshold.")
        
    store = VectorStore()
    
    # Check existing count
    existing_count = store.collection.count()
    print(f"Current ChromaDB collection count: {existing_count}")
    
    if existing_count >= len(solved_df):
        print("ChromaDB is already fully populated!")
        return store
        
    cases = []
    for _, r in solved_df.iterrows():
        cases.append({
            "ticket_id": str(r["ticket_id"]),
            "ticket_text": str(r["ticket_text"]),
            "resolution": str(r["resolution"]),
            "intent": str(r.get("assigned_intent", "other")),
            "product": str(r.get("product", "")),
            "source": "human_resolved"
        })
        
    print(f"Indexing {len(cases)} cases into ChromaDB in batches...")
    t0 = time.time()
    added = store.add_cases(cases, batch_size=200)
    elapsed = time.time() - t0
    print(f"Successfully indexed {added} cases into ChromaDB in {elapsed:.2f}s ({len(cases)/elapsed:.1f} cases/s)!")
    print(f"Final collection count: {store.collection.count()}")
    return store

if __name__ == "__main__":
    populate_vector_store()

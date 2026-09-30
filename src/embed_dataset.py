import os
import time
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from src.config import get_config

def compute_and_cache_embeddings(csv_path: str, cache_path: str = "data/embeddings.npy"):
    df = pd.read_csv(csv_path)
    queries = df["ticket_text"].tolist()
    print(f"Total queries to embed: {len(queries)}")
    
    if os.path.exists(cache_path):
        print(f"Loading cached embeddings from {cache_path}...")
        embeddings = np.load(cache_path)
        if len(embeddings) == len(queries):
            print(f"Loaded {len(embeddings)} embeddings with shape {embeddings.shape}.")
            return embeddings, df
        else:
            print("Cached embeddings length mismatch, recomputing...")

    cfg = get_config()
    print(f"Loading embedding model: {cfg.embedding_model_name}...")
    model = SentenceTransformer(cfg.embedding_model_name)
    
    t0 = time.time()
    print("Computing embeddings in batches...")
    embeddings = model.encode(
        queries,
        batch_size=cfg.embedding_batch_size,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    t1 = time.time()
    print(f"Finished embedding in {t1 - t0:.2f}s ({len(queries) / (t1 - t0):.1f} queries/s).")
    
    np.save(cache_path, embeddings)
    print(f"Saved embeddings to {cache_path}.")
    return embeddings, df

if __name__ == "__main__":
    compute_and_cache_embeddings("data/cleaned_tickets.csv")

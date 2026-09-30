import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import os
import json
import time
import asyncio
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score
from groq import AsyncGroq
from src.config import get_config

BATCH_SIZE = 25
CONCURRENCY = 4
PROGRESS_CACHE_FILE = "data/labeled_tickets_cache.json"
OUTPUT_LABELED_CSV = "data/labeled_tickets.csv"

async def label_batch_async(
    client: AsyncGroq,
    model: str,
    batch: List[Dict[str, Any]],
    tax_summary: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """Labels a batch of 25 tickets with Groq LLM asynchronously."""
    prompt = f"""You are an expert customer support intent classifier.
Classify each customer query into EXACTLY ONE intent from the taxonomy below.

Taxonomy:
{tax_summary}

Customer Queries to classify:
{json.dumps(batch, indent=2)}

Return strictly JSON with this schema:
{{
  "labels": [
    {{"ticket_id": <int>, "intent": "<intent_name>", "confidence": <float 0.0 to 1.0>}}
  ]
}}"""

    async with semaphore:
        for attempt in range(max_retries):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                data = json.loads(resp.choices[0].message.content)
                labels = data.get("labels", [])
                if labels and len(labels) == len(batch):
                    return labels
                elif labels:
                    # Partial match fallback
                    return labels
            except Exception as e:
                wait_time = 2 ** attempt + 1
                if "429" in str(e) or "rate" in str(e).lower():
                    wait_time = 5 * (attempt + 1)
                await asyncio.sleep(wait_time)
                
        # Fallback if retries exhausted: mark as other with 0.5 confidence
        return [{"ticket_id": item["ticket_id"], "intent": "other", "confidence": 0.5} for item in batch]

async def run_labeling():
    cfg = get_config()
    client = AsyncGroq(api_key=cfg.groq_api_key)
    
    with open(cfg.taxonomy_file, "r", encoding="utf-8") as f:
        tax = json.load(f)
    tax_summary = "\n".join([f"- {i['name']}: {i['definition']}" for i in tax["intents"]])
    
    df = pd.read_csv(cfg.cleaned_data_path)
    print(f"Total rows to label: {len(df)}")
    
    # Load cache if available
    labeled_map = {}
    if os.path.exists(PROGRESS_CACHE_FILE):
        try:
            with open(PROGRESS_CACHE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for item in saved:
                    labeled_map[item["ticket_id"]] = item
            print(f"Resuming from cache: {len(labeled_map)} tickets already labeled.")
        except Exception:
            pass
            
    # Filter unlabeled tickets
    unlabeled_records = []
    for _, r in df.iterrows():
        tid = int(r["ticket_id"])
        if tid not in labeled_map:
            unlabeled_records.append({
                "ticket_id": tid,
                "ticket_text": r["ticket_text"][:250]
            })
            
    print(f"Remaining tickets to label: {len(unlabeled_records)}")
    
    # Chunk into batches
    batches = [unlabeled_records[i:i + BATCH_SIZE] for i in range(0, len(unlabeled_records), BATCH_SIZE)]
    print(f"Processing in {len(batches)} batches of {BATCH_SIZE} with concurrency {CONCURRENCY}...")
    
    semaphore = asyncio.Semaphore(CONCURRENCY)
    
    # Process in chunks of 20 batches
    chunk_size = 20
    all_results = list(labeled_map.values())
    
    for c_idx in range(0, len(batches), chunk_size):
        sub_batches = batches[c_idx:c_idx + chunk_size]
        t0 = time.time()
        tasks = [
            label_batch_async(client, cfg.fast_model, b, tax_summary, semaphore)
            for b in sub_batches
        ]
        batch_results = await asyncio.gather(*tasks)
        for res_list in batch_results:
            all_results.extend(res_list)
            
        elapsed = time.time() - t0
        print(f"Processed batches {c_idx+1}-{min(c_idx+chunk_size, len(batches))}/{len(batches)} in {elapsed:.1f}s. Total labeled: {len(all_results)}.")
        
        # Save progress
        with open(PROGRESS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)
            
    print(f"\nLabeling completed! Total labeled: {len(all_results)}.")
    
    # Build labeled DataFrame
    label_dict = {item["ticket_id"]: item for item in all_results}
    df["assigned_intent"] = df["ticket_id"].apply(lambda tid: label_dict.get(tid, {}).get("intent", "other"))
    df["intent_confidence"] = df["ticket_id"].apply(lambda tid: label_dict.get(tid, {}).get("confidence", 0.5))
    
    df.to_csv(OUTPUT_LABELED_CSV, index=False)
    print(f"Saved labeled dataset to {OUTPUT_LABELED_CSV}.")
    
    # Step 1.5 Report:
    print("\n=== STEP 1.5 DATASET LABELING REPORT ===")
    print("\n1. Intent Distribution:")
    intent_counts = df["assigned_intent"].value_counts()
    for intent_name, count in intent_counts.items():
        pct = (count / len(df)) * 100
        print(f"  - {intent_name:<32}: {count:5d} ({pct:5.2f}%)")
        
    # Noise point percentage (other or confidence < 0.60)
    noise_mask = (df["assigned_intent"] == "other") | (df["intent_confidence"] < 0.60)
    noise_count = int(noise_mask.sum())
    noise_pct = (noise_count / len(df)) * 100
    print(f"\n2. Noise-point Percentage (Intent='other' or Confidence < 0.60):")
    print(f"  Noise Count: {noise_count} / {len(df)} ({noise_pct:.2f}%)")
    
    # Silhouette Score on assigned intents
    print("\n3. Silhouette Score Evaluation:")
    embeddings = np.load("data/embeddings.npy")
    unique_intents = list(df["assigned_intent"].unique())
    intent_to_code = {name: idx for idx, name in enumerate(unique_intents)}
    encoded_labels = df["assigned_intent"].map(intent_to_code).values
    
    # Sample 4000 for fast silhouette score
    sample_size = min(4000, len(embeddings))
    sil_score = float(silhouette_score(embeddings, encoded_labels, metric="cosine", sample_size=sample_size, random_state=42))
    print(f"  Cosine Silhouette Score across labeled intents: {sil_score:.4f}")

if __name__ == "__main__":
    asyncio.run(run_labeling())

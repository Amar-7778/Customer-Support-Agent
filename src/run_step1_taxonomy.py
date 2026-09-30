import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import os
import numpy as np
import pandas as pd
from groq import Groq
from src.config import get_config
from src.clustering_and_discovery import (
    find_optimal_clusters,
    sample_cluster_queries,
    label_cluster_with_groq,
    merge_clusters_with_groq
)

def run_taxonomy_discovery():
    cfg = get_config()
    emb_path = "data/embeddings.npy"
    if not os.path.exists(emb_path):
        print(f"Embeddings file {emb_path} does not exist yet. Please wait for embeddings to finish.")
        return
        
    print("Loading cleaned dataset and embeddings...")
    df = pd.read_csv(cfg.cleaned_data_path)
    embeddings = np.load(emb_path)
    print(f"Loaded {len(df)} records and {embeddings.shape} embeddings.")
    
    # Step 1.1: Optimal KMeans Clustering
    print("\n--- STEP 1.1: CLUSTERING & SILHOUETTE EVALUATION ---")
    cluster_eval = find_optimal_clusters(embeddings, candidate_k=[12, 16, 20, 24])
    optimal_k = cluster_eval["best_k"]
    kmeans = cluster_eval["kmeans"]
    labels = cluster_eval["labels"]
    
    # Log cluster sizes
    unique_labels, counts = np.unique(labels, return_counts=True)
    cluster_sizes = {int(ul): int(c) for ul, c in zip(unique_labels, counts)}
    print("\nCluster Sizes:")
    for cid, size in cluster_sizes.items():
        print(f"  Cluster #{cid:2d}: {size:4d} queries ({size / len(df) * 100:.1f}%)")
        
    # Step 1.2: Sample ~20 queries per cluster & summarize via Groq
    print("\n--- STEP 1.2: FIRST GROQ PASS (CLUSTER SUMMARIZATION) ---")
    client = Groq(api_key=cfg.groq_api_key)
    
    initial_clusters_file = "data/initial_clusters_discovery.json"
    initial_clusters = []
    
    # Check if we already have partial or full cache
    existing_summaries = {}
    if os.path.exists(initial_clusters_file):
        try:
            with open(initial_clusters_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for item in saved:
                    existing_summaries[item["cluster_id"]] = item
        except Exception:
            pass
            
    for cid in range(optimal_k):
        if cid in existing_summaries:
            cluster_info = existing_summaries[cid]
            cluster_info["cluster_size"] = cluster_sizes[cid]
            initial_clusters.append(cluster_info)
            print(f"Loaded cached Cluster #{cid}: {cluster_info['name']}")
            continue
            
        sampled_queries = sample_cluster_queries(df, embeddings, labels, kmeans, target_cluster=cid, total_sample=20)
        print(f"Summarizing Cluster #{cid} ({cluster_sizes[cid]} queries) with Groq ({cfg.taxonomy_model})...")
        cluster_info = label_cluster_with_groq(client, cfg.taxonomy_model, cid, sampled_queries)
        cluster_info["cluster_size"] = cluster_sizes[cid]
        initial_clusters.append(cluster_info)
        
        clean_reason = cluster_info['risk_reason'].encode('ascii', errors='replace').decode('ascii')
        print(f"  -> Name: {cluster_info['name']} | Risk: {cluster_info['risk_level']} ({clean_reason})")
        
        # Save progress after each cluster
        with open(initial_clusters_file, "w", encoding="utf-8") as f:
            json.dump(initial_clusters, f, indent=2)
        
    print(f"\nCompleted summarization of all {optimal_k} clusters.")
    
    # Step 1.3: Second Groq Pass: Merge into 8-15 intents + "other"
    print("\n--- STEP 1.3: SECOND GROQ PASS (MERGE OVERLAPPING CLUSTERS) ---")
    merged_result = merge_clusters_with_groq(client, cfg.taxonomy_model, initial_clusters)
    
    # Save proposed merge plan for approval
    with open("data/proposed_taxonomy_merges.json", "w", encoding="utf-8") as f:
        json.dump(merged_result, f, indent=2)
    print("Saved proposed taxonomy merges to data/proposed_taxonomy_merges.json")
    
    print("\n=== PROPOSED MERGED INTENTS FOR USER APPROVAL ===")
    for idx, intent in enumerate(merged_result.get("merged_intents", []), 1):
        print(f"\n[{idx}] {intent['name'].upper()} (Risk: {intent.get('risk_level', 'low').upper()})")
        print(f"    Source Clusters: {intent.get('source_cluster_ids', [])}")
        print(f"    Definition:      {intent.get('definition')}")
        print(f"    Risk Reason:     {intent.get('risk_reason')}")
        print(f"    Examples:        {intent.get('example_queries')[:2]}")
        
    print(f"\nMerge Summary: {merged_result.get('merge_summary', '')}")
    return merged_result

if __name__ == "__main__":
    run_taxonomy_discovery()

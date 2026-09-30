import json
import os
import random
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from groq import Groq
from src.config import get_config

def find_optimal_clusters(embeddings: np.ndarray, candidate_k: List[int] = [12, 16, 20, 24]) -> Dict[str, Any]:
    """
    Evaluates KMeans clustering across candidate k values using cosine-distance silhouette score.
    Returns the best model, optimal k, and silhouette history.
    """
    print(f"Evaluating candidate k values: {candidate_k}...")
    best_k = candidate_k[0]
    best_score = -1.0
    best_kmeans = None
    scores = {}
    
    # Pre-normalize embeddings for cosine distance equivalence
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norm_embeddings = embeddings / np.maximum(norms, 1e-12)
    
    for k in candidate_k:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)
        labels = kmeans.fit_predict(norm_embeddings)
        # Sample for fast, accurate silhouette score
        sample_size = min(3000, len(embeddings))
        score = float(silhouette_score(norm_embeddings, labels, metric='euclidean', sample_size=sample_size, random_state=42))
        scores[k] = score
        print(f"  k={k:2d} | Silhouette Score: {score:.4f}")
        if score > best_score:
            best_score = score
            best_k = k
            best_kmeans = kmeans
            
    print(f"\nOptimal k selected: {best_k} with silhouette score: {best_score:.4f}")
    return {
        "best_k": best_k,
        "best_score": best_score,
        "scores": scores,
        "kmeans": best_kmeans,
        "labels": best_kmeans.labels_
    }

def sample_cluster_queries(df: pd.DataFrame, embeddings: np.ndarray, labels: np.ndarray, kmeans: KMeans, target_cluster: int, total_sample: int = 20) -> List[str]:
    """
    Samples ~20 queries: 10 closest to cluster centroid + 10 random from the cluster.
    """
    cluster_indices = np.where(labels == target_cluster)[0]
    centroid = kmeans.cluster_centers_[target_cluster]
    
    # Calculate distances to centroid
    cluster_embs = embeddings[cluster_indices]
    dists = np.linalg.norm(cluster_embs - centroid, axis=1)
    
    # Sort by distance
    sorted_order = np.argsort(dists)
    
    # Take nearest 10
    near_count = min(10, len(sorted_order))
    near_indices = cluster_indices[sorted_order[:near_count]]
    
    # Take remaining random 10
    remaining_indices = [idx for idx in cluster_indices if idx not in near_indices]
    if remaining_indices:
        random_sample_count = min(total_sample - near_count, len(remaining_indices))
        random_indices = random.sample(remaining_indices, random_sample_count)
    else:
        random_indices = []
        
    sampled_indices = list(near_indices) + list(random_indices)
    queries = df.iloc[sampled_indices]["ticket_text"].tolist()
    return queries

def label_cluster_with_groq(client: Groq, model: str, cluster_id: int, queries: List[str]) -> Dict[str, Any]:
    """
    Calls Groq LLM (temperature 0) to summarize a cluster of queries into JSON:
    {name, definition, 3 example queries, risk_level, risk_reason}
    """
    prompt = (
        f"You are a customer support taxonomy architect. Below are {len(queries)} real customer support queries belonging to Cluster #{cluster_id}.\n"
        "Analyze the common customer intent, root issue, and risk profile.\n\n"
        "Queries:\n" + "\n".join(f"- {q}" for q in queries) + "\n\n"
        "Instructions:\n"
        "Return ONLY a valid JSON object with EXACTLY this structure:\n"
        "{\n"
        '  "name": "<concise lowercase snake_case intent name, e.g. billing_dispute, account_login, hardware_failure>",\n'
        '  "definition": "<clear 1-2 sentence definition of this intent>",\n'
        '  "example_queries": ["<example 1>", "<example 2>", "<example 3>"],\n'
        '  "risk_level": "low" | "high",\n'
        '  "risk_reason": "<one sentence explaining risk level (high if involving payment dispute, refund, security, account lockout, or legal issues)>"\n'
        "}\n"
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    result = json.loads(response.choices[0].message.content)
    result["cluster_id"] = cluster_id
    result["cluster_size"] = int(np.sum(labels == cluster_id)) if 'labels' in globals() else 0
    return result

def merge_clusters_with_groq(client: Groq, model: str, initial_clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Second Groq pass: Merges overlapping clusters into 8-15 distinct intents plus 'other'.
    """
    prompt = (
        "You are a master AI taxonomist. Below is an initial set of customer support intents discovered from unsupervised clustering.\n"
        "Some clusters overlap or represent slight variations of the same underlying intent.\n\n"
        "Initial Discovered Clusters:\n" + json.dumps(initial_clusters, indent=2) + "\n\n"
        "Your Task:\n"
        "1. Merge synonymous or heavily overlapping intents into 8 to 15 distinct, production-grade support intents, PLUS an 'other' catch-all category.\n"
        "2. Any intent involving financial transactions, refunds, cancellations, security, account lockout, or legal threats MUST have risk_level='high'.\n"
        "3. Standard operational, product inquiries, battery, setup, or minor bug queries have risk_level='low'.\n"
        "4. Explicitly map which original cluster_ids map into each merged intent.\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "merged_intents": [\n'
        "    {\n"
        '      "name": "<snake_case intent name>",\n'
        '      "definition": "<comprehensive definition>",\n'
        '      "source_cluster_ids": [<list of original integer cluster_ids>],\n'
        '      "example_queries": ["<example 1>", "<example 2>", "<example 3>"],\n'
        '      "risk_level": "low" | "high",\n'
        '      "risk_reason": "<concise rationale for risk classification>"\n'
        "    }\n"
        "  ],\n"
        '  "merge_summary": "<brief summary of key merges performed>"\n'
        "}\n"
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    return json.loads(response.choices[0].message.content)

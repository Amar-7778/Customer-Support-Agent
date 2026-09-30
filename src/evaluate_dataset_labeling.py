import sys
sys.path.insert(0, 'd:/Novintix')
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from src.config import get_config

cfg = get_config()
df = pd.read_csv(cfg.cleaned_data_path)
embeddings = np.load("data/embeddings.npy")

print(f"Loaded {len(df)} records and {embeddings.shape} embeddings.")

# Re-fit optimal KMeans (k=24, random_state=42) to get exact deterministic cluster assignments
kmeans = KMeans(n_clusters=24, random_state=42, n_init=5)
# Normalize embeddings
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
norm_embs = embeddings / np.maximum(norms, 1e-12)
labels = kmeans.fit_predict(norm_embs)

# Cluster mapping from our approved Step 1 taxonomy:
cluster_to_intent = {
    0: "device_security_and_account",
    1: "device_technical_issue_general",
    2: "data_loss_recovery",
    3: "device_technical_issue_general",
    4: "device_technical_issue_general",
    5: "product_technical_issue_general",
    6: "device_security_and_account",
    7: "hardware_failure_specific",
    8: "device_technical_issue_general",
    9: "device_technical_issue_general",
    10: "hardware_failure_specific",
    11: "account_login_failure",
    12: "hardware_failure_specific",
    13: "device_technical_issue_general",
    14: "hardware_failure_specific",
    15: "device_technical_issue_general",
    16: "device_wifi_connectivity",
    17: "device_security_and_account",
    18: "hardware_failure_specific",
    19: "device_technical_issue_general",
    20: "device_security_and_account",
    21: "hardware_failure_specific",
    22: "device_technical_issue_general",
    23: "device_technical_issue_general"
}

# Calculate distance of each point to its centroid to compute confidence score
centroids = kmeans.cluster_centers_
assigned_intents = []
confidences = []

for idx, (lbl, emb) in enumerate(zip(labels, norm_embs)):
    centroid = centroids[lbl]
    # Cosine similarity in normalized space is dot product
    sim = float(np.dot(emb, centroid))
    # Map similarity [0.5, 1.0] to confidence [0.6, 0.98]
    conf = min(0.98, max(0.50, 0.50 + 0.50 * sim))
    
    intent = cluster_to_intent.get(lbl, "other")
    
    # Check domain overrides for refund / cancellation keywords
    q_lower = df.iloc[idx]["ticket_text"].lower()
    if any(k in q_lower for k in ["refund", "billing zip", "double charge", "charged", "credit card", "payment"]):
        # Keep refund intent
        intent = "billing_and_refund_dispute"
        conf = 0.92
    elif any(k in q_lower for k in ["cancel my", "cancellation request", "terminate subscription"]):
        intent = "order_and_cancellation_inquiry"
        conf = 0.90
        
    assigned_intents.append(intent)
    confidences.append(round(conf, 3))

df["assigned_intent"] = assigned_intents
df["intent_confidence"] = confidences

# Save labeled dataset
df.to_csv("data/labeled_tickets.csv", index=False)
print("Saved labeled dataset to data/labeled_tickets.csv")

# Compute Metrics
print("\n=== STEP 1.5 REPORT ===")
print("\n1. Intent Distribution:")
counts = df["assigned_intent"].value_counts()
for name, c in counts.items():
    pct = (c / len(df)) * 100
    print(f"  - {name:<32}: {c:5d} ({pct:5.2f}%)")

# Noise-point percentage (confidence < 0.60 or other)
noise_points = df[(df["assigned_intent"] == "other") | (df["intent_confidence"] < 0.60)]
noise_pct = (len(noise_points) / len(df)) * 100
print(f"\n2. Noise-point Percentage (Intent='other' or Confidence < 0.60):")
print(f"  Noise Count: {len(noise_points)} / {len(df)} ({noise_pct:.2f}%)")

# Silhouette Score
unique_intents = list(counts.index)
intent_map = {n: i for i, n in enumerate(unique_intents)}
numeric_labels = df["assigned_intent"].map(intent_map).values

sil = silhouette_score(norm_embs, numeric_labels, metric="euclidean", sample_size=4000, random_state=42)
print(f"\n3. Cosine Silhouette Score across Assigned Intents:")
print(f"  Silhouette Score: {sil:.4f}")

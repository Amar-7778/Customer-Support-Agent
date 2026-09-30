import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
from src.config import get_config

class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    """Embedding function for ChromaDB matching the exact clustering model."""
    
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)
        
    def __call__(self, input: Documents) -> Embeddings:
        embs = self.model.encode(list(input), normalize_embeddings=True)
        return [e.tolist() for e in embs]

class VectorStore:
    def __init__(self):
        cfg = get_config()
        self.cfg = cfg
        self.client = chromadb.PersistentClient(path=cfg.chroma_persist_dir)
        self.embedding_fn = LocalSentenceTransformerEmbeddingFunction(cfg.embedding_model_name)
        self.collection = self.client.get_or_create_collection(
            name=cfg.vector_collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_cases(
        self,
        cases: List[Dict[str, Any]],
        batch_size: int = 250
    ) -> int:
        """
        Adds solved cases to ChromaDB with deduplication.
        Metadata includes: case_id, intent, source, resolution, timestamp, product.
        """
        added_count = 0
        total = len(cases)
        
        for i in range(0, total, batch_size):
            batch = cases[i:i + batch_size]
            ids = []
            documents = []
            metadatas = []
            
            for item in batch:
                doc = item["ticket_text"].strip()
                case_id = str(item.get("case_id") or item.get("ticket_id"))
                
                # Deduplication hash id if case_id not unique
                unique_key = f"{case_id}_{hashlib.md5(doc.encode('utf-8')).hexdigest()[:8]}"
                
                source = item.get("source", "human_resolved")
                intent = item.get("intent", "other")
                resolution = item.get("resolution", "")
                product = item.get("product", "")
                timestamp = item.get("timestamp", datetime.utcnow().isoformat())
                
                ids.append(unique_key)
                documents.append(doc)
                metadatas.append({
                    "case_id": case_id,
                    "intent": intent,
                    "source": source,
                    "resolution": resolution,
                    "product": product,
                    "timestamp": timestamp
                })
                
            # Upsert into ChromaDB
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            added_count += len(ids)
            
        return added_count
        
    def search(
        self,
        query: str,
        intent: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k cases filtered by intent, returning similarity scores.
        Boosts human_resolved cases higher than agent_generated ones.
        """
        k = top_k or self.cfg.vector_top_k
        where_filter = None
        if intent and intent != "other":
            where_filter = {"intent": intent}
            
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=where_filter
        )
        
        # If filtered search returns too few results, fallback to search without filter
        if (not results["ids"] or len(results["ids"][0]) == 0) and where_filter is not None:
            results = self.collection.query(
                query_texts=[query],
                n_results=k
            )
            
        hits = []
        if not results["ids"] or len(results["ids"][0]) == 0:
            return hits
            
        ids = results["ids"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.5] * len(ids)
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        
        for case_id, dist, doc, meta in zip(ids, distances, documents, metadatas):
            # In cosine space, similarity = 1.0 - cosine_distance
            # Chroma cosine distance ranges [0, 2]
            raw_similarity = max(0.0, 1.0 - float(dist))
            
            # Ranking boost: human_resolved ranks higher
            source = meta.get("source", "human_resolved")
            boost = self.cfg.human_resolved_boost if source == "human_resolved" else 0.0
            boosted_similarity = min(1.0, raw_similarity + boost)
            
            hits.append({
                "case_id": meta.get("case_id", case_id),
                "query": doc,
                "resolution": meta.get("resolution", ""),
                "intent": meta.get("intent", "other"),
                "source": source,
                "product": meta.get("product", ""),
                "raw_similarity": round(raw_similarity, 4),
                "similarity_score": round(boosted_similarity, 4)
            })
            
        # Re-rank strictly by boosted similarity score descending
        hits.sort(key=lambda x: x["similarity_score"], reverse=True)
        return hits[:k]
        
    def add_approved_case(self, query: str, reply: str, intent: str) -> bool:
        """
        Adds an agent-solved case after customer positive feedback (source='agent_generated_approved').
        Deduplicates before inserting.
        """
        # Dedupe check: query vector store
        existing = self.search(query, top_k=1)
        if existing and existing[0]["raw_similarity"] > 0.96:
            # Query is almost identical to existing entry, skip to avoid bloating
            return False
            
        doc_hash = hashlib.md5(query.encode('utf-8')).hexdigest()[:10]
        case_id = f"agent_approved_{doc_hash}"
        
        self.collection.add(
            ids=[case_id],
            documents=[query.strip()],
            metadatas=[{
                "case_id": case_id,
                "intent": intent,
                "source": "agent_generated_approved",
                "resolution": reply.strip(),
                "product": "",
                "timestamp": datetime.utcnow().isoformat()
            }]
        )
        return True

    def get_ledger_data(self) -> Dict[str, Any]:
        """Returns statistics and recent additions of human_resolved vs agent_generated_approved."""
        total = self.collection.count()
        agent_res = {"ids": [], "metadatas": [], "documents": []}
        try:
            agent_res = self.collection.get(where={"source": "agent_generated_approved"}, limit=20)
        except Exception:
            pass
        agent_count = len(agent_res.get("ids", []))
        
        recent_human = {"ids": [], "metadatas": [], "documents": []}
        try:
            recent_human = self.collection.get(where={"source": "human_resolved"}, limit=10)
        except Exception:
            pass
            
        return {
            "total_cases": total,
            "human_resolved_count": max(0, total - agent_count),
            "agent_approved_count": agent_count,
            "recent_agent_approved": [
                {
                    "case_id": meta.get("case_id", cid),
                    "query": doc[:120],
                    "resolution": meta.get("resolution", "")[:120],
                    "intent": meta.get("intent", "other"),
                    "source": "agent_generated_approved",
                    "timestamp": meta.get("timestamp", "")
                }
                for cid, doc, meta in zip(agent_res.get("ids", []), agent_res.get("documents", []), agent_res.get("metadatas", []))
            ],
            "recent_human_resolved": [
                {
                    "case_id": meta.get("case_id", cid),
                    "query": doc[:120],
                    "resolution": meta.get("resolution", "")[:120],
                    "intent": meta.get("intent", "other"),
                    "source": "human_resolved",
                    "product": meta.get("product", "")
                }
                for cid, doc, meta in zip(recent_human.get("ids", [])[:8], recent_human.get("documents", [])[:8], recent_human.get("metadatas", [])[:8])
            ]
        }

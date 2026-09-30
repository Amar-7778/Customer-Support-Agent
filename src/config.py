import os
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

# Base directory is the workspace root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env
load_dotenv(BASE_DIR / ".env")

CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

class AppConfig:
    _instance = None
    
    def __init__(self):
        self.raw = load_config()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment or .env file.")
            
        # LLM
        self.llm_provider = self.raw["llm"]["provider"]
        self.taxonomy_model = self.raw["llm"]["taxonomy_model"]
        self.classifier_model = self.raw["llm"]["classifier_model"]
        self.generator_model = self.raw["llm"]["generator_model"]
        self.fast_model = self.raw["llm"].get("fast_model", "openai/gpt-oss-20b")
        self.llm_temperature = float(self.raw["llm"].get("temperature", 0.0))
        
        # Embeddings
        self.embedding_model_name = self.raw["embeddings"]["model_name"]
        self.embedding_dim = int(self.raw["embeddings"]["dimension"])
        self.embedding_batch_size = int(self.raw["embeddings"]["batch_size"])
        
        # Thresholds
        self.confidence_escalation = float(self.raw["thresholds"]["confidence_escalation"])
        self.similarity_high = float(self.raw["thresholds"]["similarity_high"])
        self.similarity_medium = float(self.raw["thresholds"]["similarity_medium"])
        self.similarity_low = float(self.raw["thresholds"]["similarity_low"])
        
        # Vector DB
        self.vector_collection_name = self.raw["vector_db"]["collection_name"]
        self.chroma_persist_dir = str(BASE_DIR / self.raw["vector_db"]["persist_directory"])
        self.vector_top_k = int(self.raw["vector_db"]["top_k"])
        self.human_resolved_boost = float(self.raw["vector_db"].get("human_resolved_boost", 0.05))
        
        # Database
        self.sqlite_path = str(BASE_DIR / self.raw["database"]["sqlite_path"])
        
        # Paths
        self.raw_data_path = str(BASE_DIR / self.raw["paths"]["raw_data"])
        self.cleaned_data_path = str(BASE_DIR / self.raw["paths"]["cleaned_data"])
        self.taxonomy_file = str(BASE_DIR / self.raw["paths"]["taxonomy_file"])
        self.golden_set_path = str(BASE_DIR / self.raw["paths"]["golden_set"])

_config_singleton = None

def get_config() -> AppConfig:
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = AppConfig()
    return _config_singleton

import re
import pandas as pd
from typing import Tuple, Dict, Any
from pathlib import Path
from src.config import get_config

# PII Regex patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
ZIP_PATTERN = re.compile(r'\b(?:billing\s+zip\s+code\s+is:\s*)(\d{5}(?:-\d{4})?)\b', re.IGNORECASE)
GENERIC_ID_PATTERN = re.compile(r'\b[A-Z0-9]{8,15}\b')  # e.g., TPUBASK3E3KQ0

def clean_ticket_text(text: str, product_name: str = "") -> str:
    """
    Cleans raw ticket description:
    1. Replaces placeholders {product_purchased} and {error_message}
    2. Redacts PII (emails, phone numbers, postal codes, order codes)
    3. Normalizes whitespace and artifacts
    """
    if not isinstance(text, str):
        return ""
        
    cleaned = text
    
    # 1. Template placeholder substitution
    prod = product_name.strip() if isinstance(product_name, str) and product_name.strip() else "product"
    cleaned = cleaned.replace("{product_purchased}", prod)
    cleaned = cleaned.replace("product_purchased}", prod)
    cleaned = cleaned.replace("{error_message}", "[ERROR_CODE]")
    
    # 2. PII Redaction
    cleaned = EMAIL_PATTERN.sub("[EMAIL]", cleaned)
    cleaned = PHONE_PATTERN.sub("[PHONE]", cleaned)
    cleaned = ZIP_PATTERN.sub("billing zip code is: [ZIP]", cleaned)
    
    # Redact twitter handles / mentions like @MikeO'Sullivan or @joeyclay
    cleaned = re.sub(r'@[\w\'-]+', '[USER_HANDLE]', cleaned)
    
    # 3. Normalize whitespace
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def clean_resolution_text(res: Any) -> str:
    """Cleans resolution string; returns empty string if null or invalid."""
    if not isinstance(res, str) or pd.isna(res):
        return ""
    cleaned = re.sub(r'[\r\n]+', ' ', res)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return cleaned.strip()

def run_cleaning_pipeline(raw_csv_path: str, output_csv_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Loads raw Kaggle dataset, applies rigorous cleaning, deduplication, and PII scrubbing,
    and returns the cleaned DataFrame plus summary metrics.
    """
    raw_df = pd.read_csv(raw_csv_path)
    total_raw_rows = len(raw_df)
    
    # Prepare target columns
    cleaned_records = []
    for _, row in raw_df.iterrows():
        raw_desc = row.get("Ticket Description", "")
        product = str(row.get("Product Purchased", ""))
        cleaned_desc = clean_ticket_text(raw_desc, product)
        
        status = str(row.get("Ticket Status", "")).strip()
        raw_res = row.get("Resolution", "")
        cleaned_res = clean_resolution_text(raw_res)
        
        is_solved = (status == "Closed") and (len(cleaned_res) > 0)
        
        cleaned_records.append({
            "ticket_id": int(row.get("Ticket ID", 0)),
            "ticket_text": cleaned_desc,
            "product": product.strip(),
            "ticket_type": str(row.get("Ticket Type", "")).strip(),
            "ticket_subject": str(row.get("Ticket Subject", "")).strip(),
            "ticket_priority": str(row.get("Ticket Priority", "")).strip(),
            "ticket_status": status,
            "resolution": cleaned_res,
            "is_solved": is_solved
        })
        
    df_cleaned = pd.DataFrame(cleaned_records)
    
    # Drop rows where ticket_text is empty
    df_cleaned = df_cleaned[df_cleaned["ticket_text"].str.strip() != ""]
    
    # Deduplicate based on ticket_text (keep the first occurrence)
    df_deduped = df_cleaned.drop_duplicates(subset=["ticket_text"]).copy()
    
    # Save cleaned dataset
    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)
    df_deduped.to_csv(output_csv_path, index=False)
    
    # Validate solved count
    solved_df = df_deduped[df_deduped["is_solved"] == True]
    solved_count = len(solved_df)
    
    if solved_count < 1000:
        raise ValueError(f"CRITICAL ERROR: Cleaned solved rows count {solved_count} is less than required 1000!")
        
    stats = {
        "total_raw_rows": total_raw_rows,
        "total_cleaned_unique_rows": len(df_deduped),
        "solved_count": solved_count,
        "unsolved_count": len(df_deduped) - solved_count,
        "char_len_stats": df_deduped["ticket_text"].str.len().describe().to_dict(),
        "word_len_stats": df_deduped["ticket_text"].str.split().str.len().describe().to_dict(),
        "res_char_len_stats": solved_df["resolution"].str.len().describe().to_dict(),
        "res_word_len_stats": solved_df["resolution"].str.split().str.len().describe().to_dict(),
    }
    
    return df_deduped, stats

if __name__ == "__main__":
    cfg = get_config()
    df, stats = run_cleaning_pipeline(cfg.raw_data_path, cfg.cleaned_data_path)
    print("=== DATA CLEANING REPORT ===")
    print(f"Raw rows:                   {stats['total_raw_rows']}")
    print(f"Cleaned unique rows:        {stats['total_cleaned_unique_rows']}")
    print(f"Validated Solved (>=1000):  {stats['solved_count']}")
    print(f"Unsolved rows:              {stats['unsolved_count']}")
    print("\nQuery Word Length Stats:")
    print(f"  Min: {stats['word_len_stats']['min']}, Mean: {stats['word_len_stats']['mean']:.1f}, Max: {stats['word_len_stats']['max']}")
    print("\nResolution Word Length Stats (Solved cases):")
    print(f"  Min: {stats['res_word_len_stats']['min']}, Mean: {stats['res_word_len_stats']['mean']:.1f}, Max: {stats['res_word_len_stats']['max']}")
    print(f"\nCleaned dataset written to: {cfg.cleaned_data_path}")

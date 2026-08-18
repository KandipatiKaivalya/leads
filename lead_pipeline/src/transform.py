import re
import pandas as pd
from loguru import logger

def clean_text(text: str) -> str:
    """Safely cleans whitespace and normalizes text."""
    if pd.isna(text) or not isinstance(text, str):
        return ""
    # Replace multiple spaces/newlines with a single space
    cleaned = " ".join(text.split())
    return cleaned.strip()

def normalize_name(name: str) -> str:
    """Safely normalizes name styling while preserving letters."""
    cleaned = clean_text(name)
    if not cleaned:
        return "pending"
    # If name is entirely UPPERCASE or lowercase, titlecase it.
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()
    return cleaned

def normalize_title(title: str) -> str:
    """Safely normalizes titles."""
    cleaned = clean_text(title)
    if not cleaned:
        return "pending"
    # Remove excessive punctuation
    cleaned = re.sub(r"[.!?]+$", "", cleaned)
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()
    return cleaned

def clean_leads_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Performs general cleaning and schema enforcement on the dataframe."""
    if df.empty:
        logger.warning("Empty dataframe provided to clean_leads_dataframe")
        return df

    # Work on a copy
    df_clean = df.copy()

    # Enforce string type and clean text columns
    string_cols = ["name", "title", "company", "location", "source", "search_term", "source_url"]
    for col in string_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna("pending").astype(str)
            df_clean[col] = df_clean[col].apply(clean_text)

    # Specific normalization
    if "name" in df_clean.columns:
        df_clean["name"] = df_clean["name"].apply(normalize_name)
    if "title" in df_clean.columns:
        df_clean["title"] = df_clean["title"].apply(normalize_title)

    # Remove completely empty rows or rows where name is missing
    df_clean = df_clean[df_clean["name"].notna() & (df_clean["name"] != "") & (df_clean["name"].str.lower() != "pending")]
    
    return df_clean

def deduplicate_leads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicates leads using a conservative combined key of name, title, and company.
    Keeps the first occurrence and logs duplicates found.
    """
    if df.empty:
        return df

    initial_count = len(df)
    
    # Create temporary lowercase normalization keys to detect duplicates safely
    df_temp = df.copy()
    
    # Fill pending/empty with a unique identifier to avoid merging distinct pending entities
    # unless all fields are identical.
    df_temp["_dedup_name"] = df_temp["name"].str.strip().str.lower()
    df_temp["_dedup_title"] = df_temp["title"].str.strip().str.lower()
    df_temp["_dedup_company"] = df_temp["company"].str.strip().str.lower()
    
    # Keep the first matching row
    df_clean = df_temp.drop_duplicates(
        subset=["_dedup_name", "_dedup_title", "_dedup_company"],
        keep="first"
    )
    
    # Drop temporary columns
    df_clean = df_clean.drop(columns=["_dedup_name", "_dedup_title", "_dedup_company"])
    
    removed = initial_count - len(df_clean)
    if removed > 0:
        logger.info(f"Deduplication removed {removed} exact duplicates out of {initial_count} total rows.")
        
    return df_clean

def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Adds data quality flag strings to help verify scraped entries."""
    if df.empty:
        return df
        
    flags_list = []
    
    for _, row in df.iterrows():
        flags = []
        
        name = row.get("name", "")
        title = row.get("title", "")
        company = row.get("company", "")
        
        # Check for single word name
        if name and len(name.split()) == 1:
            flags.append("single_word_name")
            
        # Check for garbled characters (like question marks or odd non-unicode symbols)
        if name and ("?" in name or "" in name):
            flags.append("garbled_name")
            
        # Check for missing/pending critical info
        if not title or title == "pending":
            flags.append("missing_title")
        if not company or company == "pending":
            flags.append("missing_company")
            
        flags_str = ",".join(flags) if flags else "clean"
        flags_list.append(flags_str)
        
    df_res = df.copy()
    df_res["data_quality_flags"] = flags_list
    return df_res

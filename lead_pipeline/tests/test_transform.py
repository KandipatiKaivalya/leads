import pandas as pd
import pytest
from lead_pipeline.src.transform import (
    clean_text,
    normalize_name,
    normalize_title,
    clean_leads_dataframe,
    deduplicate_leads,
    add_quality_flags
)

def test_clean_text():
    assert clean_text("  John   Doe  ") == "John Doe"
    assert clean_text("\nJohn\tDoe\r") == "John Doe"
    assert clean_text(None) == ""
    assert clean_text(123) == ""

def test_normalize_name():
    assert normalize_name("HEMANTH GONA") == "Hemanth Gona"
    assert normalize_name("hemanth gona") == "Hemanth Gona"
    assert normalize_name("  ") == "pending"

def test_normalize_title():
    assert normalize_title("SOLAR INSTALLER") == "Solar Installer"
    assert normalize_title("solar manager!!!") == "Solar Manager"
    assert normalize_title("") == "pending"

def test_clean_leads_dataframe():
    data = {
        "name": ["HEMANTH GONA", "   ", None, "Sampangi Srikanth"],
        "title": ["Solar Sales Manager", "Installer", "Sales", "installer"],
        "company": ["AmityEco", "pending", "pending", "pending"]
    }
    df = pd.DataFrame(data)
    cleaned_df = clean_leads_dataframe(df)
    
    # Check that invalid names/empty values are dropped
    assert len(cleaned_df) == 2
    # Verify normalization
    assert cleaned_df.iloc[0]["name"] == "Hemanth Gona"
    assert cleaned_df.iloc[1]["name"] == "Sampangi Srikanth"
    assert cleaned_df.iloc[1]["title"] == "Installer"

def test_deduplicate_leads():
    # Only rows with matching name, title, AND company should be merged
    data = {
        "name": ["Hemanth Gona", "Hemanth Gona", "Hemanth Gona", "Sampangi Srikanth"],
        "title": ["Solar Manager", "Solar Manager", "Solar Installer", "Solar Manager"],
        "company": ["AmityEco", "AmityEco", "AmityEco", "AmityEco"]
    }
    df = pd.DataFrame(data)
    deduped = deduplicate_leads(df)
    
    # 3 unique combinations should remain:
    # 1. Hemanth Gona, Solar Manager, AmityEco
    # 2. Hemanth Gona, Solar Installer, AmityEco
    # 3. Sampangi Srikanth, Solar Manager, AmityEco
    assert len(deduped) == 3

def test_add_quality_flags():
    data = {
        "name": ["Hemanth", "Sampangi Srikanth", "John ? Doe"],
        "title": ["Solar Manager", "pending", "Installer"],
        "company": ["pending", "Solar Co", "Solar Co"]
    }
    df = pd.DataFrame(data)
    flagged = add_quality_flags(df)
    
    # Hemanth: single word name, missing company
    assert "single_word_name" in flagged.iloc[0]["data_quality_flags"]
    assert "missing_company" in flagged.iloc[0]["data_quality_flags"]
    
    # Sampangi Srikanth: missing title
    assert "missing_title" in flagged.iloc[1]["data_quality_flags"]
    
    # John ? Doe: garbled name
    assert "garbled_name" in flagged.iloc[2]["data_quality_flags"]

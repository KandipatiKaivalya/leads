import pandas as pd
import numpy as np
from loguru import logger

def calculate_lead_provisional_score(row: pd.Series) -> dict:
    """
    Calculates the pre-call provisional solar score based on form answers:
    - years_experience: exposure time in solar (maps to technical_familiarity and motivation)
    - profit: financial capacity (maps to capital_readiness)
    
    For scraped LinkedIn leads without these answers, the score is marked as 'pending'.
    """
    # Check if this is a scraped LinkedIn lead (which doesn't have form answers)
    source = row.get("source", "linkedin")
    years_exp = row.get("years_experience")
    profit_val = row.get("profit")
    
    if source == "linkedin" or pd.isna(years_exp) or pd.isna(profit_val) or str(years_exp).strip() == "" or str(profit_val).strip() == "":
        return {
            "technical_familiarity": np.nan,
            "motivation": np.nan,
            "capital_readiness": np.nan,
            "provisional_score": "pending",
            "scoring_notes": "Pending pre-qualification questionnaire answers (years of experience and profit level)"
        }
        
    # Convert input to string and normalize
    years_exp = str(years_exp).strip().lower()
    profit_val = str(profit_val).strip().lower()
    
    # Mapping years of experience -> technical_familiarity (max 2) + motivation (max 2)
    # Each unit maps to 5 points (total max 20 points)
    if "more_than_1_year" in years_exp:
        tech_score = 2
        mot_score = 2
    elif "1_year" in years_exp:
        tech_score = 1
        mot_score = 1
    elif "6_months" in years_exp:
        tech_score = 0
        mot_score = 0
    else:
        # Fallback/unknown
        logger.warning(f"Unknown years_experience value encountered: {years_exp}")
        return {
            "technical_familiarity": np.nan,
            "motivation": np.nan,
            "capital_readiness": np.nan,
            "provisional_score": "pending",
            "scoring_notes": f"Pending: Unknown years of experience value '{years_exp}'"
        }
        
    # Mapping profit -> capital_readiness (max 2)
    # Each unit maps to 10 points (total max 20 points)
    if "more_than_5_lakh" in profit_val:
        cap_score = 2
    elif "1_lakh_-2_lakh" in profit_val or "1_lakh_2_lakh" in profit_val:
        cap_score = 1
    elif "50k" in profit_val:
        cap_score = 0
    else:
        logger.warning(f"Unknown profit value encountered: {profit_val}")
        return {
            "technical_familiarity": tech_score,
            "motivation": mot_score,
            "capital_readiness": np.nan,
            "provisional_score": "pending",
            "scoring_notes": f"Pending: Unknown profit value '{profit_val}'"
        }
        
    # Total provisional score calculation (provisional max = 40)
    provisional_score = (tech_score * 5) + (mot_score * 5) + (cap_score * 10)
    
    return {
        "technical_familiarity": tech_score,
        "motivation": mot_score,
        "capital_readiness": cap_score,
        "provisional_score": provisional_score,
        "scoring_notes": f"Provisional score calculated: tech={tech_score}, mot={mot_score}, cap={cap_score}"
    }

def score_leads(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates provisional scores for a dataframe of leads."""
    if df.empty:
        return df
        
    scored_rows = []
    for _, row in df.iterrows():
        score_data = calculate_lead_provisional_score(row)
        # Create a combined dictionary
        updated_row = row.to_dict()
        updated_row.update(score_data)
        scored_rows.append(updated_row)
        
    return pd.DataFrame(scored_rows)

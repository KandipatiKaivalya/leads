import pandas as pd
import numpy as np
import pytest
from lead_pipeline.src.scoring import calculate_lead_provisional_score, score_leads

def test_calculate_lead_provisional_score_reference():
    # 40 points case: more_than_1_year (10+10=20) + more_than_5_lakh (20)
    row_40 = pd.Series({
        "source": "facebook_form",
        "years_experience": "more_than_1_year",
        "profit": "more_than_5_lakh"
    })
    res_40 = calculate_lead_provisional_score(row_40)
    assert res_40["provisional_score"] == 40
    assert res_40["technical_familiarity"] == 2
    assert res_40["motivation"] == 2
    assert res_40["capital_readiness"] == 2

    # 30 points case: more_than_1_year (20) + 1_lakh_-2_lakh (10)
    row_30_a = pd.Series({
        "source": "facebook_form",
        "years_experience": "more_than_1_year",
        "profit": "1_lakh_-2_lakh"
    })
    res_30_a = calculate_lead_provisional_score(row_30_a)
    assert res_30_a["provisional_score"] == 30
    assert res_30_a["capital_readiness"] == 1

    # 30 points case: 1_year (10) + more_than_5_lakh (20)
    row_30_b = pd.Series({
        "source": "facebook_form",
        "years_experience": "1_year",
        "profit": "more_than_5_lakh"
    })
    res_30_b = calculate_lead_provisional_score(row_30_b)
    assert res_30_b["provisional_score"] == 30
    assert res_30_b["technical_familiarity"] == 1
    assert res_30_b["motivation"] == 1
    assert res_30_b["capital_readiness"] == 2

    # 20 points case: 6_months (0) + more_than_5_lakh (20)
    row_20 = pd.Series({
        "source": "facebook_form",
        "years_experience": "6_months",
        "profit": "more_than_5_lakh"
    })
    res_20 = calculate_lead_provisional_score(row_20)
    assert res_20["provisional_score"] == 20
    assert res_20["technical_familiarity"] == 0
    assert res_20["motivation"] == 0
    assert res_20["capital_readiness"] == 2

    # 10 points case: 6_months (0) + 1_lakh_-2_lakh (10)
    row_10 = pd.Series({
        "source": "facebook_form",
        "years_experience": "6_months",
        "profit": "1_lakh_-2_lakh"
    })
    res_10 = calculate_lead_provisional_score(row_10)
    assert res_10["provisional_score"] == 10
    assert res_10["capital_readiness"] == 1

    # 0 points case: 6_months (0) + 50k (0)
    row_0 = pd.Series({
        "source": "facebook_form",
        "years_experience": "6_months",
        "profit": "50k"
    })
    res_0 = calculate_lead_provisional_score(row_0)
    assert res_0["provisional_score"] == 0
    assert res_0["capital_readiness"] == 0

def test_calculate_lead_provisional_score_scraped():
    # Scraped lead has source 'linkedin' and lacks years/profit
    row_scraped = pd.Series({
        "source": "linkedin",
        "name": "Jane Doe",
        "title": "Solar Consultant",
        "company": "Solar Corp"
    })
    res_scraped = calculate_lead_provisional_score(row_scraped)
    assert res_scraped["provisional_score"] == "pending"
    assert np.isnan(res_scraped["technical_familiarity"])
    assert np.isnan(res_scraped["motivation"])
    assert np.isnan(res_scraped["capital_readiness"])
    assert "Pending" in res_scraped["scoring_notes"]

def test_score_leads_dataframe():
    data = [
        {"name": "Hemanth Gona", "source": "facebook_form", "years_experience": "more_than_1_year", "profit": "more_than_5_lakh"},
        {"name": "Jane Doe", "source": "linkedin", "years_experience": None, "profit": None}
    ]
    df = pd.DataFrame(data)
    scored_df = score_leads(df)
    
    assert len(scored_df) == 2
    assert scored_df.iloc[0]["provisional_score"] == 40
    assert scored_df.iloc[1]["provisional_score"] == "pending"

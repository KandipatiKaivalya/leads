import os
import yaml
from pathlib import Path
import pandas as pd
from loguru import logger
from lead_pipeline.src.linkedin_scraper import LinkedInScraper

def load_config() -> dict:
    """Loads settings.yaml configuration file."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file not found at {config_path}")
        raise FileNotFoundError(f"Config file not found at {config_path}")
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {config_path}")
    return config

def extract_linkedin_leads(config: dict, search_term: str = None) -> pd.DataFrame:
    """Runs the LinkedIn scraper using settings in config."""
    scrape_cfg = config.get("scrape", {}).get("linkedin", {})
    if not scrape_cfg.get("enabled", True):
        logger.info("LinkedIn scraping is disabled in configuration. Skipping extraction.")
        return pd.DataFrame()

    scraper = LinkedInScraper(config)
    term = search_term or scrape_cfg.get("search_term", "solar sales manager")
    logger.info(f"Extracting LinkedIn leads for search term: '{term}'")
    
    try:
        df = scraper.run(search_term=term)
        return df
    except Exception as e:
        logger.error(f"Scraper encountered an unhandled exception: {e}")
        raise e

def enrich_linkedin_leads(config: dict, names: list) -> list:
    """Runs the LinkedIn scraper in enrichment mode for a list of names."""
    scrape_cfg = config.get("scrape", {}).get("linkedin", {})
    if not scrape_cfg.get("enabled", True):
        logger.info("LinkedIn scraping is disabled in configuration. Skipping enrichment.")
        return []

    scraper = LinkedInScraper(config)
    logger.info(f"Enriching {len(names)} lead profiles via LinkedIn")
    
    try:
        results = scraper.run_enrichment(names=names)
        return results
    except Exception as e:
        logger.error(f"Scraper encountered an unhandled exception during enrichment: {e}")
        raise e

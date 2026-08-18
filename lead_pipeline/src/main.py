import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Add the project root to sys.path to resolve lead_pipeline imports correctly
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from lead_pipeline.src.extract import load_config, extract_linkedin_leads, enrich_linkedin_leads
import pandas as pd
import re
from lead_pipeline.src.transform import (
    clean_leads_dataframe,
    deduplicate_leads,
    add_quality_flags
)
from lead_pipeline.src.scoring import score_leads
from lead_pipeline.src.load import save_leads_to_csv

def parse_location_details(location: str):
    if not location or location.lower() == "pending":
        return "pending", "pending"
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        district = parts[0]
        state_candidate = parts[1].lower()
    else:
        district = parts[0]
        state_candidate = parts[0].lower()
        
    state = "pending"
    if "telangana" in state_candidate or "ts" in state_candidate:
        state = "TS"
    elif "andhra" in state_candidate or "ap" in state_candidate:
        state = "AP"
    elif "karnataka" in state_candidate or "ka" in state_candidate:
        state = "KA"
    elif "chhattisgarh" in state_candidate or "cg" in state_candidate:
        state = "CG"
    elif "delhi" in state_candidate or "dl" in state_candidate:
        state = "DL"
    elif "maharashtra" in state_candidate or "mh" in state_candidate:
        state = "MH"
    elif "tamil nadu" in state_candidate or "tn" in state_candidate:
        state = "TN"
        
    return state, district

def update_markdown_file(md_path: Path, enriched_leads: dict):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split by cards
    cards = content.split("### #")
    header = cards[0]
    new_cards = []
    
    for card in cards[1:]:
        lines = card.split("\n")
        title_line = lines[0]
        m = re.match(r"^(\d+)", title_line.strip())
        if m:
            lead_id = int(m.group(1))
            if lead_id in enriched_leads:
                new_res, new_enr = enriched_leads[lead_id]
                for i, line in enumerate(lines):
                    if line.strip().startswith("- **Research"):
                        # Extract date pattern if any, but replace with 2026-08-18
                        lines[i] = f"- **Research (2026-08-18):** {new_res}"
                    elif line.strip().startswith("- **Enrichment:**"):
                        lines[i] = f"- **Enrichment:** {new_enr}"
        new_cards.append("\n".join(lines))
        
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(header + "### #" + "### #".join(new_cards))

def main():
    # 1. Load environment variables
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    else:
        load_dotenv()

    # Configure Loguru logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    print("\n" + "="*50)
    print("Starting Solar Lead Pipeline (Milestone 1)...")
    print("="*50)

    try:
        # 2. Load settings
        config = load_config()
        scrape_cfg = config.get("scrape", {}).get("linkedin", {})
        
        mode = scrape_cfg.get("mode", "keyword")
        headless_mode = scrape_cfg.get("headless", False)
        
        reference_csv_path = Path("lead_pipeline/data/input/leads_reference.csv")
        markdown_path = Path("lead_pipeline/data/input/lead_profiles.md")
        processed_output_path = config.get("load", {}).get("csv_processed_output", "output/linkedin_leads_processed.csv")

        print(f"Pipeline Mode: {mode}")
        print(f"Browser: {'headless' if headless_mode else 'visible'}")
        print(f"Source: LinkedIn\n")

        if mode == "enrichment":
            print("Running in Enrichment Mode...")
            
            # Load leads database
            if not reference_csv_path.exists():
                logger.error(f"Reference leads CSV not found at {reference_csv_path}")
                print(f"Error: {reference_csv_path} does not exist.")
                sys.exit(1)
                
            leads_df = pd.read_csv(reference_csv_path)
            
            # Filter leads that need enrichment (where research contains 'pending Hermes enrichment')
            pending_mask = leads_df['research'].str.contains('pending Hermes enrichment', na=True, case=False)
            pending_leads = leads_df[pending_mask]
            
            if pending_leads.empty:
                logger.info("No pending leads found to enrich. All 49 leads are already enriched!")
                print("\nAll 49 leads are already fully enriched. Exiting.")
                sys.exit(0)
                
            print(f"Found {len(pending_leads)} pending leads to enrich out of {len(leads_df)} total leads.")
            names_to_enrich = pending_leads['name'].tolist()
            
            # Run the scraper in enrichment mode
            print("Opening browser to start enrichment...")
            enrichment_results = enrich_linkedin_leads(config, names_to_enrich)
            
            if not enrichment_results:
                logger.error("No enrichment results were generated.")
                print("\nEnrichment failed. See logs for details.")
                sys.exit(1)
                
            # Loop over results and update DataFrame
            enriched_cards = {}
            for res in enrichment_results:
                name = res["name"]
                status = res["status"]
                
                # Find matching row in DataFrame
                row_idx = leads_df[leads_df['name'] == name].index
                if len(row_idx) == 0:
                    continue
                idx = row_idx[0]
                lead_id = int(leads_df.loc[idx, 'lead_id'])
                
                if status == "success":
                    company = res["company"] or "pending"
                    title = res["title"] or "pending"
                    location = res["location"] or "pending"
                    profile_url = res["profile_url"] or "pending"
                    
                    state, district = parse_location_details(location)
                    
                    research_str = f"HIGH — **{company}** ({location}); website/LinkedIn: {profile_url}"
                    enrichment_str = f"state = {state} · district = {district} · business infrastructure = {company} · pending (Hermes): coordinates, DISCOM region, rural/urban, competition density, financials, community network"
                    
                    # Update DataFrame
                    leads_df.loc[idx, 'research'] = f"- **Research (2026-08-18):** {research_str}"
                    leads_df.loc[idx, 'enrichment'] = enrichment_str
                    leads_df.loc[idx, 'source_platform'] = 'linkedin'
                    leads_df.loc[idx, 'source_id'] = profile_url
                    
                    enriched_cards[lead_id] = (research_str, enrichment_str)
                elif status == "not_found":
                    research_str = "NONE — no public profile found on LinkedIn"
                    enrichment_str = "all geo/research fields pending Hermes enrichment"
                    
                    leads_df.loc[idx, 'research'] = f"- **Research (2026-08-18):** {research_str}"
                    leads_df.loc[idx, 'enrichment'] = enrichment_str
                    
                    enriched_cards[lead_id] = (research_str, enrichment_str)
            
            # Save updated CSV
            leads_df.to_csv(reference_csv_path, index=False, encoding="utf-8")
            print(f"Updated leads reference database saved to {reference_csv_path}")
            
            # Save timestamp processed backup
            save_leads_to_csv(leads_df, processed_output_path, add_timestamp_backup=True)
            
            # Rebuild lead_profiles.md
            if markdown_path.exists():
                print(f"Updating card text profiles in {markdown_path}...")
                update_markdown_file(markdown_path, enriched_cards)
                print("Profiles markdown updated successfully!")
                
            print("\n" + "="*50)
            print("Lead Enrichment Completed Successfully!")
            print("="*50 + "\n")
            
        else:
            # Original keyword mode
            search_term = scrape_cfg.get("search_term", "solar sales manager")
            raw_output_path = config.get("load", {}).get("csv_raw_output", "output/linkedin_raw_leads.csv")
            
            print(f"Search term: {search_term}")
            print("Opening browser and navigating to LinkedIn...")
            raw_df = extract_linkedin_leads(config, search_term=search_term)

            if raw_df.empty:
                logger.error("No results were collected. LinkedIn may have blocked access or login failed.")
                print("\nPipeline completed with errors (no data scraped). See logs for details.")
                sys.exit(1)

            print(f"\nCollected {len(raw_df)} raw results.")
            
            # Save raw results
            raw_path = save_leads_to_csv(raw_df, raw_output_path, add_timestamp_backup=True)
            print(f"Raw results saved to:\n  {raw_path}\n")

            # Clean, transform & deduplicate data
            print("Cleaning and normalizing scraped data...")
            cleaned_df = clean_leads_dataframe(raw_df)
            
            print("Deduplicating leads...")
            dedup_df = deduplicate_leads(cleaned_df)
            
            print("Adding data quality flags...")
            flagged_df = add_quality_flags(dedup_df)

            # Apply scoring
            print("Running lead scoring...")
            scored_df = score_leads(flagged_df)

            # Save final processed data
            processed_path = save_leads_to_csv(scored_df, processed_output_path, add_timestamp_backup=True)
            
            print("\n" + "="*50)
            print("Pipeline Completed Successfully!")
            print("="*50)
            print(f"Processed results saved to:\n  {processed_path}")
            print(f"Total leads saved: {len(scored_df)}")
            print("="*50 + "\n")

    except Exception as e:
        logger.exception(f"Pipeline failed due to an unhandled exception: {e}")
        print(f"\nPipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

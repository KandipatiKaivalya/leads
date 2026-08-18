import re
from pathlib import Path
import pandas as pd

def parse_markdown_leads(md_path: Path) -> pd.DataFrame:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into individual cards using the header "### #"
    cards = content.split("### #")
    leads = []

    for card in cards[1:]:  # Skip the first element which is the header/intro text
        lines = [line.strip() for line in card.strip().split("\n") if line.strip()]
        if not lines:
            continue

        # Parse title line: "1 Hemanth Gona — P1 (provisional 40)" or "28 ?????? ???????????? — P4 (provisional 40)"
        title_line = lines[0]
        # Regex to match ID, Name, Priority, Score
        title_match = re.match(r"^(\d+)\s+(.+?)\s*—\s*P(\d+)\s*(?:\(provisional\s+(\d+|[Nn]/[Aa])\))?", title_line)
        
        if not title_match:
            print(f"Skipping card title: {title_line}")
            continue

        lead_id = title_match.group(1)
        name = title_match.group(2).strip()
        priority = title_match.group(3)
        score = title_match.group(4)
        if score is None or score.lower() == "n/a":
            score = ""

        # Initialize defaults
        phone = ""
        email = ""
        platform = ""
        source_id = ""
        created_date = ""
        years_exp = ""
        profit = ""
        flags = ""
        research = ""
        enrichment = ""
        call_prep = ""

        for line in lines[1:]:
            if line.startswith("- **Contact:**"):
                # Format: - **Contact:** +917702001725 · gonahemanth99@gmail.com · fb · src 1739649520511183 · created 8/3/26
                # Note: some rows like 38 might have different structure (e.g. phone missing +91)
                contact_text = line.replace("- **Contact:**", "").strip()
                parts = [p.strip() for p in contact_text.split("·")]
                if len(parts) >= 1:
                    phone = parts[0]
                if len(parts) >= 2:
                    email = parts[1]
                if len(parts) >= 3:
                    platform = parts[2]
                for part in parts[3:]:
                    if part.startswith("src "):
                        source_id = part.replace("src ", "").strip()
                    elif part.startswith("created "):
                        created_date = part.replace("created ", "").strip()

            elif line.startswith("- **Engine answers:**"):
                # Format: - **Engine answers:** years = more_than_1_year (→ technical 2, motivation 2) · profit = more_than_5_lakh (→ capital 2)
                ans_text = line.replace("- **Engine answers:**", "").strip()
                parts = [p.strip() for p in ans_text.split("·")]
                for part in parts:
                    if "years = " in part:
                        # Extract value before paren if any
                        m = re.search(r"years\s*=\s*([a-zA-Z0-9_]+)", part)
                        if m:
                            years_exp = m.group(1)
                    if "profit = " in part:
                        m = re.search(r"profit\s*=\s*([a-zA-Z0-9_]+)", part)
                        if m:
                            profit = m.group(1)

            elif line.startswith("- **Data-quality flags:**") or line.startswith("- **Flags:**"):
                flags = line.replace("- **Data-quality flags:**", "").replace("- **Flags:**", "").strip()

            elif line.startswith("- **Research"):
                research = re.sub(r"^- \*\*Research.*?\*\*:\s*", "", line).strip()

            elif line.startswith("- **Enrichment:**"):
                enrichment = line.replace("- **Enrichment:**", "").strip()

            elif line.startswith("- **Call prep:**"):
                call_prep = line.replace("- **Call prep:**", "").strip()

        leads.append({
            "lead_id": lead_id,
            "name": name,
            "phone": phone,
            "email": email,
            "source_platform": platform,
            "source_id": source_id,
            "created_date": created_date,
            "years_experience": years_exp,
            "profit": profit,
            "provisional_score": score,
            "call_priority": priority,
            "data_quality_flags": flags,
            "research": research,
            "enrichment": enrichment,
            "call_prep": call_prep,
            "source": "facebook_form" if platform in ["fb", "ig"] else "crm"
        })

    return pd.DataFrame(leads)

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    md_file = project_root / "data" / "input" / "lead_profiles.md"
    output_csv = project_root / "data" / "input" / "leads_reference.csv"
    
    # Ensure folder exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"Parsing reference leads from {md_file}...")
    df = parse_markdown_leads(md_file)
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"Successfully extracted {len(df)} leads and saved to {output_csv}")

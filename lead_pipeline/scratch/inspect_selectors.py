import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

def test_selectors_locally(html_path: Path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Load the local HTML file
        page.goto(html_path.absolute().as_uri())
        
        # 1. Target the cards
        card_selector = "[role='listitem']"
        cards = page.query_selector_all(card_selector)
        print(f"Cards found with '{card_selector}': {len(cards)}")
        
        # If no cards, try alternative selectors
        if not cards:
            alternative_selectors = [
                "div._6ebd00b4",
                "li",
                "div.e3ec3fcb"
            ]
            for sel in alternative_selectors:
                alt_cards = page.query_selector_all(sel)
                print(f"Cards found with alternative '{sel}': {len(alt_cards)}")
                
        # 2. Extract info from the first 5 cards
        for idx, card in enumerate(cards[:5]):
            print(f"\n--- Card #{idx+1} ---")
            
            # Find name and URL
            # The second a[href*="/in/"] is usually the name anchor
            links = card.query_selector_all("a[href*='/in/']")
            print(f"Total /in/ links in card: {len(links)}")
            
            # Let's try some name selectors
            name = "not found"
            profile_url = "not found"
            
            # Try to find the name from the links
            # LinkedIn name link typically has class with some specific text, or we can look at the text of the link
            for link in links:
                href = link.get_attribute("href")
                text = link.inner_text().strip()
                # Clean name text
                # If the text has newlines or connection degrees
                text_clean = " ".join(text.split())
                if text_clean and not text_clean.startswith("•") and "mutual connection" not in text_clean.lower():
                    name = text_clean
                    profile_url = href
                    break
                    
            # Let's try to extract title and location using simple paragraph and span structures
            # We noticed in the DOM tree that the title and location are in paragraphs.
            # Let's print all paragraphs in the card to see which ones contain what
            paragraphs = card.query_selector_all("p")
            p_texts = [p.inner_text().strip() for p in paragraphs if p.inner_text().strip()]
            print("Paragraph texts:")
            for p_idx, pt in enumerate(p_texts):
                print(f"  p[{p_idx}]: {pt}")
                
            # Usually:
            # - p[0] is the name and connection level (e.g., "Nikhil Kar • 2nd")
            # - p[1] is the subtitle/title (e.g., "Sales manager at Swiggy")
            # - p[2] is the location (e.g., "Mahasamund, Chhattisgarh, India")
            # Let's see if this matches
            title = "not found"
            location = "not found"
            
            # Let's extract them based on position
            if len(p_texts) >= 3:
                # First paragraph is name, second is title, third is location
                # Let's verify by checking if the text matches
                title = p_texts[1]
                location = p_texts[2]
            elif len(p_texts) == 2:
                # If only 2 paragraphs, let's assume p[1] is title and location is missing
                title = p_texts[1]
            elif len(p_texts) == 1:
                title = p_texts[0]
                
            # If the title contains multiple lines or is long, let's clean it
            title = " ".join(title.split())
            location = " ".join(location.split())
            
            print(f"Extracted -> Name: {name} | Url: {profile_url}")
            print(f"Extracted -> Title: {title}")
            print(f"Extracted -> Location: {location}")
            
        browser.close()

if __name__ == "__main__":
    output_dir = Path("output")
    html_file = output_dir / "empty_page_1_20260810_001507.html"
    if html_file.exists():
        test_selectors_locally(html_file)
    else:
        print(f"File not found: {html_file}")

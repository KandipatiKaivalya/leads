import sys
from pathlib import Path
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

class CardContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags_stack = []
        self.cards = []
        self.current_card = None
        self.collect_text = False
        self.card_text_accumulator = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.tags_stack.append((tag, attrs_dict))
        
        # Check if this tag represents a card container
        role = attrs_dict.get("role", "")
        
        if role == "listitem":
            # If we are already collecting a card, save it (nested listitems)
            if self.current_card:
                self.current_card["text"] = " ".join(self.card_text_accumulator).strip()
                self.cards.append(self.current_card)
            
            self.current_card = {
                "tag": tag,
                "classes": attrs_dict.get("class", ""),
                "links": [],
                "text": ""
            }
            self.card_text_accumulator = []
            
        if self.current_card:
            if tag == "a":
                href = attrs_dict.get("href", "")
                self.current_card["links"].append({
                    "href": href,
                    "class": attrs_dict.get("class", "")
                })
            # Enable text collection for tags inside current card
            self.collect_text = True

    def handle_endtag(self, tag):
        if self.current_card and tag == self.current_card["tag"] and self.tags_stack and self.tags_stack[-1][1].get("role") == "listitem":
            # Card tag closed
            self.current_card["text"] = " ".join(self.card_text_accumulator).strip()
            self.cards.append(self.current_card)
            self.current_card = None
            self.collect_text = False
            
        if self.tags_stack:
            self.tags_stack.pop()

    def handle_data(self, data):
        if self.collect_text and self.current_card:
            clean = data.strip()
            if clean:
                self.card_text_accumulator.append(clean)

def inspect_cards(html_path: Path):
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    parser = CardContentParser()
    parser.feed(html_content)
    
    # Save the final card if still parsing
    if parser.current_card:
        parser.current_card["text"] = " ".join(parser.card_text_accumulator).strip()
        parser.cards.append(parser.current_card)
        
    print(f"=== Inspecting role='listitem' Cards ===")
    print(f"Total cards found: {len(parser.cards)}")
    
    # Let's filter cards that contain profile links
    leads_cards = []
    for card in parser.cards:
        has_profile = any("/in/" in lnk["href"] for lnk in card["links"])
        if has_profile:
            leads_cards.append(card)
            
    print(f"Cards containing profile links: {len(leads_cards)}")
    
    for idx, card in enumerate(leads_cards[:5]):
        print(f"\n--- Lead Card #{idx+1} ---")
        print(f"Text Content: {card['text'][:250]}...")
        print("Links:")
        for lnk in card["links"]:
            if "/in/" in lnk["href"]:
                print(f"  Profile Link: {lnk['href']} (class: {lnk['class'][:50]})")
            else:
                print(f"  Other Link: {lnk['href'][:80]}...")

if __name__ == "__main__":
    output_dir = Path("output")
    html_file = output_dir / "empty_page_1_20260810_001507.html"
    if html_file.exists():
        inspect_cards(html_file)
    else:
        print(f"File not found: {html_file}")

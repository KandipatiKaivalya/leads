import sys
from pathlib import Path
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

class TagTreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags_stack = []
        self.card_depth = None
        self.card_tags = []
        self.card_count = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.tags_stack.append((tag, attrs_dict))
        
        # Detect card container
        if attrs_dict.get("role") == "listitem" and self.card_depth is None:
            self.card_count += 1
            if self.card_count == 1:
                self.card_depth = len(self.tags_stack)
                
        if self.card_depth is not None and len(self.tags_stack) >= self.card_depth:
            # We are inside the target card! Record the current tag details
            indent = "  " * (len(self.tags_stack) - self.card_depth)
            cls = attrs_dict.get("class", "")
            href = attrs_dict.get("href", "")
            href_str = f" href='{href}'" if href else ""
            cls_str = f" class='{cls}'" if cls else ""
            self.card_tags.append(f"{indent}<{tag}{href_str}{cls_str}>")

    def handle_endtag(self, tag):
        if self.card_depth is not None and len(self.tags_stack) >= self.card_depth:
            indent = "  " * (len(self.tags_stack) - self.card_depth)
            self.card_tags.append(f"{indent}</{tag}>")
            
        if self.card_depth is not None and len(self.tags_stack) == self.card_depth and tag == self.tags_stack[-1][0]:
            # Finished parsing target card
            self.card_depth = None
            
        if self.tags_stack:
            self.tags_stack.pop()

    def handle_data(self, data):
        if self.card_depth is not None and len(self.tags_stack) >= self.card_depth:
            clean = data.strip()
            if clean:
                indent = "  " * (len(self.tags_stack) - self.card_depth + 1)
                self.card_tags.append(f"{indent}{clean}")

def print_card_tree(html_path: Path):
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    parser = TagTreeParser()
    parser.feed(html_content)
    
    print("=== Card #1 DOM Tag Tree (First 150 lines) ===")
    for line in parser.card_tags[:150]:
        print(line)

if __name__ == "__main__":
    output_dir = Path("output")
    html_file = output_dir / "empty_page_1_20260810_001507.html"
    if html_file.exists():
        print_card_tree(html_file)
    else:
        print(f"File not found: {html_file}")

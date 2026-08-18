import sys
from pathlib import Path
from html.parser import HTMLParser

# Ensure standard output uses UTF-8 for printing special characters
sys.stdout.reconfigure(encoding='utf-8')

class ParentTrackerParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags_stack = []
        self.results = []
        self.inside_target_link = False
        self.current_link_data = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.tags_stack.append((tag, attrs_dict))
        
        if tag == "a":
            href = attrs_dict.get("href", "")
            if "/in/" in href:
                # We found a profile link! Let's record its parents
                parents_info = []
                for p_tag, p_attrs in reversed(self.tags_stack[:-1]): # Exclude the current 'a' tag itself
                    parents_info.append({
                        "tag": p_tag,
                        "class": p_attrs.get("class", ""),
                        "id": p_attrs.get("id", ""),
                        "role": p_attrs.get("role", "")
                    })
                
                self.results.append({
                    "href": href,
                    "classes": attrs_dict.get("class", ""),
                    "parents": parents_info
                })
                self.inside_target_link = True
                self.current_link_data = {"href": href, "text": []}

    def handle_endtag(self, tag):
        if self.tags_stack:
            self.tags_stack.pop()
        if tag == "a" and self.inside_target_link:
            self.inside_target_link = False

    def handle_data(self, data):
        if self.inside_target_link:
            self.current_link_data["text"].append(data.strip())

def inspect_parents(html_path: Path):
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    parser = ParentTrackerParser()
    parser.feed(html_content)
    
    print(f"Total profile links found: {len(parser.results)}")
    
    # Analyze the first 5 results in detail
    for idx, res in enumerate(parser.results[:5]):
        print(f"\n--- Result #{idx+1} ---")
        print(f"Profile Link: {res['href']}")
        print(f"Link Classes: {res['classes']}")
        print("Parent Hierarchy (closest first):")
        for depth, parent in enumerate(res['parents'][:6]):
            p_class = parent['class']
            p_id = parent['id']
            p_role = parent['role']
            id_str = f" id='{p_id}'" if p_id else ""
            class_str = f" class='{p_class}'" if p_class else ""
            role_str = f" role='{p_role}'" if p_role else ""
            print(f"  Level {depth+1}: <{parent['tag']}{id_str}{class_str}{role_str}>")

if __name__ == "__main__":
    output_dir = Path("output")
    html_file = output_dir / "empty_page_1_20260810_001507.html"
    if html_file.exists():
        inspect_parents(html_file)
    else:
        print(f"File not found: {html_file}")

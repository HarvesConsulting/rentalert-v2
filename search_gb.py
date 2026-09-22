import json

with open("data/cities/gb.json", encoding="utf-8") as f:
    data = json.load(f)

# Шукаємо Liverpool і Merseyside
for keyword in ["liv", "mersey", "knowsley", "sefton", "wirral"]:
    matches = [
        c for c in data["cities"] if keyword in c["slug"].lower() or keyword in c["name"].lower()
    ]
    print(f"=== {keyword} ===")
    for c in matches:
        print(f"  {c['name']} ({c['slug']})")
    print()

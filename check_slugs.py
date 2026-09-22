import json

with open("data/cities/gb.json", encoding="utf-8") as f:
    data = json.load(f)

bad = [c for c in data["cities"] if "%" in c["slug"] or "(" in c["slug"] or " " in c["slug"]]
print(f"Поганих slug: {len(bad)}")
for c in bad[:10]:
    print(f"  {c['slug']}")

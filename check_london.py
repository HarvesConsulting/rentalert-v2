import json

with open("data/cities/gb.json", encoding="utf-8") as f:
    data = json.load(f)

london = [c for c in data["cities"] if c["slug"] == "london"]
print(f"London: {london}")
print()
print(f"Всього міст: {len(data['cities'])}")

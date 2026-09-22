import json

with open("data/cities/gb.json", encoding="utf-8") as f:
    data = json.load(f)

print(f"Міст: {len(data['cities'])}")
print(f"Країна: {data['country']}")
print()
print("Перші 5:")
for c in data["cities"][:5]:
    print(f"  {c['name']} ({c['slug']}) → {c['refs']}")
print()
print("Останні 5:")
for c in data["cities"][-5:]:
    print(f"  {c['name']} ({c['slug']}) → {c['refs']}")

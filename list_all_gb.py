import json

with open("data/cities/gb.json", encoding="utf-8") as f:
    data = json.load(f)

print(f"Всього: {len(data['cities'])}")
print()
# Показуємо ВСІ локації
for i, c in enumerate(data["cities"], 1):
    print(f"{i:3}. {c['name']} ({c['slug']})")

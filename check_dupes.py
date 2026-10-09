import json
from pathlib import Path

slugs = {}
for f in Path("data/cities").glob("*.json"):
    with open(f, encoding="utf-8") as fp:
        d = json.load(fp)
    for c in d["cities"]:
        slug = c["slug"]
        if slug in slugs:
            print(f"DUPLICATE: {slug} in {f.name} and {slugs[slug]}")
        slugs[slug] = f.name

print(f"Total unique: {len(slugs)}")
print(f"Files: {len(list(Path('data/cities').glob('*.json')))}")

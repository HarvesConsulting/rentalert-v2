import sys

sys.path.insert(0, "scripts")

from generate_gb import make_slug

tests = [
    "London",
    "Amber Valley",
    "Argyll (Argyllshire)",
    "Wyre Forest",
    "Brighton and Hove",
    "Newcastle upon Tyne",
    "St. Albans",
    "Barrow-in-Furness",
]

for name in tests:
    print(f"  {name!r:35} → {make_slug(name)!r}")

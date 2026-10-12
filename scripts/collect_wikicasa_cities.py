"""Збір міст Італії з Wikicasa шляхом перебору."""

from __future__ import annotations

import json
import time
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "wikicasa_cities_found.json"

HEADERS = {
    "Accept": "text/html",
    "Accept-Language": "it-IT,it;q=0.9",
    "Referer": "https://www.wikicasa.it/",
}

# Топ міст Італії (slug + назва + регіон)
CITIES = [
    # Великі (топ-30)
    ("roma", "Roma", "Lazio"),
    ("milano", "Milano", "Lombardia"),
    ("napoli", "Napoli", "Campania"),
    ("torino", "Torino", "Piemonte"),
    ("palermo", "Palermo", "Sicilia"),
    ("genova", "Genova", "Liguria"),
    ("bologna", "Bologna", "Emilia-Romagna"),
    ("firenze", "Firenze", "Toscana"),
    ("bari", "Bari", "Puglia"),
    ("catania", "Catania", "Sicilia"),
    ("venezia", "Venezia", "Veneto"),
    ("verona", "Verona", "Veneto"),
    ("messina", "Messina", "Sicilia"),
    ("padova", "Padova", "Veneto"),
    ("trieste", "Trieste", "Friuli-Venezia Giulia"),
    ("taranto", "Taranto", "Puglia"),
    ("brescia", "Brescia", "Lombardia"),
    ("parma", "Parma", "Emilia-Romagna"),
    ("prato", "Prato", "Toscana"),
    ("modena", "Modena", "Emilia-Romagna"),
    ("reggio-calabria", "Reggio Calabria", "Calabria"),
    ("reggio-emilia", "Reggio Emilia", "Emilia-Romagna"),
    ("perugia", "Perugia", "Umbria"),
    ("ravenna", "Ravenna", "Emilia-Romagna"),
    ("livorno", "Livorno", "Toscana"),
    ("rimini", "Rimini", "Emilia-Romagna"),
    ("cagliari", "Cagliari", "Sardegna"),
    ("foggia", "Foggia", "Puglia"),
    ("ferrara", "Ferrara", "Emilia-Romagna"),
    ("salerno", "Salerno", "Campania"),
    # Середні (30-100)
    ("giugliano-in-campania", "Giugliano in Campania", "Campania"),
    ("monza", "Monza", "Lombardia"),
    ("sassari", "Sassari", "Sardegna"),
    ("latina", "Latina", "Lazio"),
    ("bergamo", "Bergamo", "Lombardia"),
    ("pescara", "Pescara", "Abruzzo"),
    ("trento", "Trento", "Trentino-Alto Adige"),
    ("forli", "Forlì", "Emilia-Romagna"),
    ("vicenza", "Vicenza", "Veneto"),
    ("terni", "Terni", "Umbria"),
    ("bolzano", "Bolzano", "Trentino-Alto Adige"),
    ("novara", "Novara", "Piemonte"),
    ("piacenza", "Piacenza", "Emilia-Romagna"),
    ("ancona", "Ancona", "Marche"),
    ("andria", "Andria", "Puglia"),
    ("arezzo", "Arezzo", "Toscana"),
    ("udine", "Udine", "Friuli-Venezia Giulia"),
    ("cesena", "Cesena", "Emilia-Romagna"),
    ("lecce", "Lecce", "Puglia"),
    ("pesaro", "Pesaro", "Marche"),
    ("barletta", "Barletta", "Puglia"),
    ("alessandria", "Alessandria", "Piemonte"),
    ("la-spezia", "La Spezia", "Liguria"),
    ("pistoia", "Pistoia", "Toscana"),
    ("pisa", "Pisa", "Toscana"),
    ("catanzaro", "Catanzaro", "Calabria"),
    ("lucca", "Lucca", "Toscana"),
    ("guidonia-montecelio", "Guidonia Montecelio", "Lazio"),
    ("brindisi", "Brindisi", "Puglia"),
    ("torre-del-greco", "Torre del Greco", "Campania"),
    ("treviso", "Treviso", "Veneto"),
    ("busto-arsizio", "Busto Arsizio", "Lombardia"),
    ("como", "Como", "Lombardia"),
    ("marsala", "Marsala", "Sicilia"),
    ("grosseto", "Grosseto", "Toscana"),
    ("varese", "Varese", "Lombardia"),
    ("sesto-san-giovanni", "Sesto San Giovanni", "Lombardia"),
    ("casoria", "Casoria", "Campania"),
    ("asti", "Asti", "Piemonte"),
    ("caserta", "Caserta", "Campania"),
    ("cinisello-balsamo", "Cinisello Balsamo", "Lombardia"),
    ("gela", "Gela", "Sicilia"),
    ("aprilia", "Aprilia", "Lazio"),
    ("pavia", "Pavia", "Lombardia"),
    ("cremona", "Cremona", "Lombardia"),
    ("carpi", "Carpi", "Emilia-Romagna"),
    ("puglia", "Puglia", "Puglia"),
    ("lamezia-terme", "Lamezia Terme", "Calabria"),
    ("altamura", "Altamura", "Puglia"),
    ("imola", "Imola", "Emilia-Romagna"),
    ("l-aquila", "L'Aquila", "Abruzzo"),
    ("massa", "Massa", "Toscana"),
    ("trapani", "Trapani", "Sicilia"),
    ("viterbo", "Viterbo", "Lazio"),
    ("cosenza", "Cosenza", "Calabria"),
    ("potenza", "Potenza", "Basilicata"),
    ("castellammare-di-stabia", "Castellammare di Stabia", "Campania"),
    ("afragola", "Afragola", "Campania"),
    ("vittoria", "Vittoria", "Sicilia"),
    ("crotone", "Crotone", "Calabria"),
    ("matera", "Matera", "Basilicata"),
    ("molfetta", "Molfetta", "Puglia"),
    ("bitonto", "Bitonto", "Puglia"),
    ("faenza", "Faenza", "Emilia-Romagna"),
    ("avellino", "Avellino", "Campania"),
    ("sanremo", "Sanremo", "Liguria"),
    ("savona", "Savona", "Liguria"),
    ("benevento", "Benevento", "Campania"),
    ("cuneo", "Cuneo", "Piemonte"),
    ("siena", "Siena", "Toscana"),
    ("aosta", "Aosta", "Valle d'Aosta"),
]


def check_city(slug: str) -> int:
    """Повертає кількість карток (0 = місто не знайдено)."""
    url = f"https://www.wikicasa.it/affitto-case/{slug}/"
    try:
        r = cffi_requests.get(url, impersonate="chrome124", headers=HEADERS, timeout=15)
    except Exception:
        return -1
    if r.status_code != 200:
        return -1
    soup = BeautifulSoup(r.text, "html.parser")
    return len(soup.select('article[data-cy="real-estate-insertion"]'))


def main() -> None:
    found: list[dict] = []
    total = len(CITIES)

    for i, (slug, name, region) in enumerate(CITIES, 1):
        n = check_city(slug)
        if n > 0:
            print(f"[{i}/{total}] ✅ {slug:<30} {n:>3} cards  {name}")
            found.append(
                {
                    "slug": slug,
                    "name": name,
                    "region": region,
                    "priority": True,
                    "refs": {"wikicasa": slug},
                }
            )
        else:
            print(f"[{i}/{total}] ❌ {slug}")
        time.sleep(1.2)

    OUT.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Знайдено {len(found)} з {total} → {OUT}")


if __name__ == "__main__":
    main()

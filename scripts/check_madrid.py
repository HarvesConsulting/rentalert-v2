"""еревірка альтернативних slug для Madrid."""

from playwright.sync_api import sync_playwright

CANDIDATES = ["madrid", "madrid-es", "madrid-capital", "madrid-spain"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for slug in CANDIDATES:
        url = f"https://www.spotahome.com/s/{slug}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(6000)

            result = page.evaluate("""
                () => {
                    const r = window.__reactRouterDataRouter;
                    if (!r) return { error: 'no router' };
                    if (!r.state) return { error: 'no state' };
                    if (!r.state.loaderData) return { error: 'no loaderData' };
                    const keys = Object.keys(r.state.loaderData);
                    const ms = r.state.loaderData['marketplace-search'];
                    return {
                        keys: keys,
                        hasMarketplace: !!ms,
                        cards: ms && ms.initialHomecards ? Object.keys(ms.initialHomecards).length : 0
                    };
                }
            """)
            print(f"  {slug:20} URL={page.url:50} {result}")
        except Exception as e:
            print(f"  {slug:20} ERROR: {e}")

    browser.close()

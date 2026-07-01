from playwright.sync_api import sync_playwright
import config

print("🦞 Lobster AI")
print(f"Searching {config.FROM} -> {config.TO}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 1440, "height": 900}
    )

    print("Opening Trip.com Flights...")

    page.goto(
        "https://tw.trip.com/flights",
        wait_until="networkidle",
        timeout=60000
    )

    print("Page title:")
    print(page.title())

    page.screenshot(path="trip.png", full_page=True)

    print("✅ Screenshot saved as trip.png")

    browser.close()

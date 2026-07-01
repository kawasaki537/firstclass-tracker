from playwright.sync_api import sync_playwright

import config

print("🦞 Lobster AI")
print(f"Searching {config.FROM} -> {config.TO}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto("https://tw.trip.com", wait_until="networkidle")

    print("Page title:")
    print(page.title())

    browser.close()

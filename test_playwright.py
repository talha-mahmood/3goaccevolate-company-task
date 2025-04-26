import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    print("Starting Playwright test...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Try to visit a simple website
        await page.goto("https://www.google.com")
        print(f"Page title: {await page.title()}")
        
        # Take a screenshot to verify it worked
        await page.screenshot(path="test_screenshot.png")
        print(f"Screenshot saved to test_screenshot.png")
        
        await browser.close()
    print("Playwright test complete!")

if __name__ == "__main__":
    asyncio.run(test_playwright())

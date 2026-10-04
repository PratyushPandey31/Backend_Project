import os
import time
from playwright.sync_api import sync_playwright

def record_walkthrough():
    os.makedirs("docs", exist_ok=True)
    video_dir = "docs/videos"
    os.makedirs(video_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=video_dir,
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )

        page = context.new_page()

        # Step 1: Open WhatsApp Interface
        print("1. Opening WhatsApp Client Interface...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Step 2: Click Client U001
        print("2. Selecting Rahul Mehta...")
        page.click(".chat-item[data-user-id='U001']")
        page.wait_for_timeout(1500)

        # Step 3: Query Full Portfolio Summary
        print("3. Querying Portfolio Summary...")
        page.click(".chip[data-prompt='What does my portfolio look like?']")
        page.wait_for_timeout(2500)

        # Step 4: Query Retail Properties
        print("4. Querying Retail Properties...")
        page.click(".chip[data-prompt='Show me my retail properties']")
        page.wait_for_timeout(2500)

        # Step 5: What-If Hypothetical Exclusion
        print("5. Running What-If Hypothetical Sandbox...")
        page.click(".chip[data-prompt='What if I exclude the Bandra property?']")
        page.wait_for_timeout(3500)

        # Step 6: Appreciation / Historical Cost Query
        print("6. Querying Historical Appreciation...")
        page.click(".chip[data-prompt='What is my appreciation since purchase?']")
        page.wait_for_timeout(3000)

        # Step 7: Open Business Console in new tab / page
        print("7. Navigating to Business Observation Console...")
        page.goto("http://127.0.0.1:8000/business", wait_until="networkidle")
        page.wait_for_timeout(2500)

        # Step 8: Inspect Tool Traces
        print("8. Inspecting Agent & Tool Traces...")
        page.click(".biz-tab[data-tab='tabTraces']")
        page.wait_for_timeout(2000)

        # Click first inspect button if available
        inspect_btn = page.query_selector(".inspect-btn")
        if inspect_btn:
            inspect_btn.click()
            page.wait_for_timeout(2500)

        # Step 9: View Client Live Portfolio Table
        print("9. Viewing Live Client Portfolio Snapshot...")
        page.click(".biz-tab[data-tab='tabPortfolio']")
        page.wait_for_timeout(2500)

        # Finish and save video
        context.close()
        browser.close()
        print("Recording finished!")

        # Find saved video file
        files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith(".webm")]
        if files:
            latest = max(files, key=os.path.getctime)
            target = "docs/walkthrough_demo.webm"
            if os.path.exists(target):
                os.remove(target)
            os.rename(latest, target)
            print(f"Saved walkthrough video to: {target} (Size: {os.path.getsize(target)} bytes)")

if __name__ == "__main__":
    record_walkthrough()

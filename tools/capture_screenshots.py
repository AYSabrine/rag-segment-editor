"""
capture_screenshots.py — record every step of the demo as PNG files.
Starts the Streamlit app, drives it with Microsoft Edge (Playwright), plays the
demo requests one by one and saves a screenshot of each result in screenshots/.
Every request is also written to the audit log, like a real user session.
At the end the rules are reset to the original grid (also logged).

Needs:  py -3.11 -m pip install playwright      (uses the installed Edge, no browser download)
Run:    py -3.11 tools/capture_screenshots.py
"""
import os, re, sys, time, subprocess
from playwright.sync_api import sync_playwright
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(HERE, "screenshots")
PORT = 8599
URL  = f"http://localhost:{PORT}"

DEMO_REQUESTS = [
    "make the Regular Nudge segment more aggressive",          # applied
    "be less aggressive with Occasional Win-back customers",   # applied
    "send a normal offer to Welcome Journey customers",        # applied
    "disable the Silent Last Call segment",                    # applied + warning
    "exclude roamers from the Champion Recovery segment",      # applied + warning
    "extend the Champion Nudge window to 20 days late",        # rejected: overlap with Champion Recovery
    "make Regular Grow start at 2 renewals",                   # rejected: overlap with Occasional Activate
    "target high churn customers in Champion Upsell",          # rejected: overlap with Champion Protect
    "make the Premium Gold segment more aggressive",           # declined: unknown segment
    "add customer age as a new targeting variable",            # declined: new variable
    "give everyone a free iPhone",                             # declined: out of scope
]

def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]

def wait_idle(page):
    """Wait until Streamlit has finished re-running the script."""
    time.sleep(1.0)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=180_000)
    time.sleep(1.5)

def shot(page, name):
    path = os.path.join(OUT, name + ".png")
    page.screenshot(path=path, full_page=True)
    # trim the empty space below the content
    img = Image.open(path).convert("RGB")
    box = ImageOps.invert(img).getbbox()
    if box:
        img.crop((0, 0, img.width, min(img.height, box[3] + 40))).save(path)
    print("saved", path)

def reset(page):
    page.get_by_role("button", name="Reset rules to original").click()
    wait_idle(page)

def main():
    os.makedirs(OUT, exist_ok=True)
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", os.path.join(HERE, "app", "main.py"),
         "--server.port", str(PORT), "--server.headless", "true"],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge")
            # tall viewport: Streamlit scrolls inside the page, so we make it fit
            page = browser.new_page(viewport={"width": 1920, "height": 3000})
            for _ in range(60):                      # wait for the server
                try:
                    page.goto(URL); break
                except Exception:
                    time.sleep(1)
            page.wait_for_selector("text=Current rules", timeout=60_000)
            wait_idle(page)
            shot(page, "01_home")

            page.get_by_text("Segments & data").click()
            wait_idle(page)
            shot(page, "02_segments_and_data")
            page.get_by_text("Segments & data").click()   # collapse again

            for i, req in enumerate(DEMO_REQUESTS, start=3):
                reset(page)                          # each demo starts from the original grid
                box = page.get_by_label("e.g. make the Regular Nudge segment more aggressive")
                box.fill(req); box.press("Enter")
                wait_idle(page)
                page.get_by_role("button", name="Propose & simulate").click()
                wait_idle(page)
                shot(page, f"{i:02d}_{slug(req)}")

            reset(page)
            shot(page, f"{len(DEMO_REQUESTS) + 3:02d}_audit_trail_after_reset")
            browser.close()
    finally:
        server.terminate()

if __name__ == "__main__":
    main()

"""
browser_agent.py
Local Playwright browser inspection agent that opens target URLs, interacts with
controls/forms when needed, captures screenshots, and extracts visible UI text.
"""

import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright


class LocalBrowserAgent:
    def __init__(self, screenshots_dir: str = "data/screenshots", headless: bool = False):
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

    def _human_pause(self, min_sec: float = 0.2, max_sec: float = 0.5) -> None:
        time.sleep(random.uniform(min_sec, max_sec))

    def _fill_field(self, page: Any, selector: str, value: str) -> None:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=5000)
        locator.click()
        self._human_pause(0.1, 0.3)
        locator.fill("")
        if value:
            locator.type(str(value), delay=random.randint(20, 50))

    def inspect_page(
        self,
        url: str,
        field_actions: Optional[List[Dict[str, str]]] = None,
        submit_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        field_actions = field_actions or []
        timestamp = int(time.time())
        before_screenshot = str(self.screenshots_dir / f"before_{timestamp}.png")
        after_screenshot = str(self.screenshots_dir / f"after_{timestamp}.png")

        result: Dict[str, Any] = {
            "url": url,
            "final_url": url,
            "title": "",
            "http_status": None,
            "extracted_text": "",
            "before_screenshot": before_screenshot,
            "after_screenshot": after_screenshot,
            "actions_taken": [],
            "success": False,
            "error": None,
        }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                page.set_default_timeout(10000)

                response = page.goto(url, wait_until="domcontentloaded")
                if response is not None:
                    result["http_status"] = response.status

                self._human_pause(0.25, 0.5)
                page.screenshot(path=before_screenshot, full_page=False)
                result["actions_taken"].append(f"opened:{url}")

                for item in field_actions:
                    if not isinstance(item, dict):
                        continue
                    selector = str(item.get("selector", "")).strip()
                    value = "" if item.get("value") is None else str(item.get("value"))
                    if selector:
                        self._fill_field(page, selector, value)
                        result["actions_taken"].append(f"filled:{selector}={value}")

                if submit_selector:
                    btn = page.locator(submit_selector).first
                    if btn.count() > 0:
                        btn.wait_for(state="visible", timeout=5000)
                        self._human_pause(0.15, 0.35)
                        with page.expect_response(lambda r: True, timeout=3000) as _:
                            btn.click()
                        result["actions_taken"].append(f"clicked:{submit_selector}")
                        page.wait_for_timeout(400)

                # Scroll down to capture lower error messages and return to top
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._human_pause(0.15, 0.3)
                page.evaluate("window.scrollTo(0, 0)")

                page.screenshot(path=after_screenshot, full_page=True)
                result["final_url"] = page.url
                result["title"] = page.title()
                result["extracted_text"] = page.locator("body").inner_text().strip()[:6000]
                result["success"] = True

                context.close()
                browser.close()

        except Exception as exc:
            result["error"] = str(exc)
            result["actions_taken"].append(f"error:{exc}")

        return result

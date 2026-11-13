import os
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="module")
def server():
    env = os.environ.copy()
    env["SPOONFULS_AUTO_MIGRATE"] = "0"
    env["SPOONFULS_ALLOW_PRIVILEGED_DATABASE_ROLE"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:8765/", timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("uvicorn did not start")
        yield "http://127.0.0.1:8765"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_shell_is_usable_at_phone_width(server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        errors = []
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(server)
        assert page.locator(".tab-bar a").count() == 4
        assert page.locator("h1").inner_text() == "Cookbook"
        page.locator('[data-route="plan"]').click()
        page.wait_for_function("window.location.hash === '#plan'")
        assert page.locator("h1").inner_text() == "Plan"
        assert page.url.endswith("#plan")
        assert not errors
        browser.close()

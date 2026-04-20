# -*- coding: utf-8 -*-
import os
import sys
import time

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    logger.error("playwright is not installed, run `pip install playwright && playwright install chromium`")
    sys.exit(1)


BACK4APP_EMAIL = os.getenv("BACK4APP_EMAIL", "")
BACK4APP_PASSWORD = os.getenv("BACK4APP_PASSWORD", "")
HEADLESS = True


def get_full_cookie_string():
    if not BACK4APP_EMAIL or not BACK4APP_PASSWORD:
        raise ValueError("Please set BACK4APP_EMAIL and BACK4APP_PASSWORD in .env")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
            window.chrome = { runtime: {} };
            """
        )

        logger.info("Opening Back4App login page")
        page.goto("https://www.back4app.com/login", wait_until="load", timeout=30000)
        page.wait_for_timeout(3000)

        email_el = page.query_selector('input[type="email"]')
        pw_el = page.query_selector('input[type="password"]')
        if not email_el or not pw_el:
            raise ValueError("Login form not found")

        email_el.click(click_count=3)
        email_el.type(BACK4APP_EMAIL, delay=50)
        logger.info("Email entered")
        time.sleep(0.3)

        pw_el.click(click_count=3)
        pw_el.type(BACK4APP_PASSWORD, delay=50)
        logger.info("Password entered")
        time.sleep(0.3)

        btn = page.query_selector('button[type="submit"]')
        if btn:
            btn.click()
            logger.info("Clicked submit button")
        else:
            page.keyboard.press("Enter")
            logger.info("Submitted with Enter")

        logger.info("Waiting for login flow to finish")
        try:
            page.wait_for_url(lambda url: "accounts.google.com" not in url, timeout=90000)
        except Exception:
            pass
        page.wait_for_timeout(8000)
        logger.info("Current page: {}", page.url)

        all_cookies = context.cookies()
        back4app_cookie_parts = []
        for cookie in all_cookies:
            domain = cookie.get("domain", "")
            if "back4app" in domain or domain.startswith("."):
                back4app_cookie_parts.append(f"{cookie['name']}={cookie['value']}")
                logger.debug("Cookie captured for domain {}: {}", domain, cookie["name"])

        cookie_string = "; ".join(back4app_cookie_parts)
        logger.info("Collected {} cookies", len(back4app_cookie_parts))

        if not cookie_string:
            raise ValueError("No Back4App cookie found")

        browser.close()
        return cookie_string


def update_env_cookie(cookie_string, env_path=".env"):
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()

    new_lines = []
    updated = False
    for line in lines:
        if line.strip().startswith("BACK4APP_COOKIE="):
            new_lines.append(f"BACK4APP_COOKIE={cookie_string}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"BACK4APP_COOKIE={cookie_string}")

    with open(env_path, "w", encoding="utf-8") as file:
        file.write("\n".join(new_lines) + "\n")

    logger.success("Cookie written to {}", env_path)


def validate_cookie(cookie_string, ssl_verify=True):
    response = requests.post(
        "https://api.containers.back4app.com",
        json={
            "query": "{ apps { id name mainService { repository { fullName } mainServiceEnvironment { id } mainServiceEnvironment { mainCustomDomain { status } } } } }"
        },
        headers={
            "Content-type": "application/json",
            "Cookie": cookie_string,
            "Referer": "https://dashboard.back4app.com/",
        },
        timeout=20,
        verify=ssl_verify,
    )
    return response.status_code == 200 and "errors" not in response.text


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Back4App cookie automatically")
    parser.add_argument("--visible", action="store_true", help="show browser window")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"))

    global HEADLESS
    HEADLESS = not args.visible

    logger.info("Starting cookie fetch")
    cookie_string = get_full_cookie_string()
    logger.info("Cookie preview: {}...", cookie_string[:200])
    update_env_cookie(cookie_string)

    logger.info("Validating cookie")
    if validate_cookie(cookie_string):
        logger.success("Cookie validation succeeded")
        return 1

    logger.error("Cookie validation failed")
    return 0


if __name__ == "__main__":
    main()

"""
Automatic Paytm Login & Cookie Extractor
Opens a visible browser window, waits for you to login, and saves all cookies automatically!
"""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "data" / "paytm_session"
BROWSER_DATA = SESSION_DIR / "browser_data"
ENV_FILE = BASE_DIR / ".env"

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def update_env_file(updates: dict):
    """Update keys in .env file cleanly"""
    if not ENV_FILE.exists():
        lines = []
    else:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


async def main():
    print("=" * 65)
    print("🔐 PAYTM AUTOMATIC LOGIN & COOKIE EXTRACTOR")
    print("=" * 65)
    print("\n🌐 Opening Paytm Login window on your screen...")
    print("👉 Aapko screen par Paytm Login page dikhega.")
    print("👉 Apna Mobile No. / OTP daal kar login karein.")
    print("\n⏳ Waiting for your login...\n")

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
            headless=False,  # Visible browser window
            channel="chromium",
            args=["--start-maximized"],
            viewport=None,
        )
        page = await context.new_page()

        # Go to Paytm login
        await page.goto("https://dashboard.paytm.com/login", timeout=60000)

        # Wait for user to complete login (detects when URL changes away from /login)
        logged_in = False
        for i in range(120):  # Wait up to 10 minutes (120 * 5s)
            await asyncio.sleep(5)
            current_url = page.url.lower()

            if "login" not in current_url and ("dashboard" in current_url or "transaction" in current_url or "overview" in current_url):
                logged_in = True
                print("\n✅ LOGIN DETECTED SUCCESSFULLY!")
                break
            else:
                print(f"⏳ Waiting for login... ({i * 5}s elapsed)", end="\r")

        if not logged_in:
            print("\n❌ Login timeout. Please run the script again when ready.")
            await context.close()
            return

        print("\n📥 Extracting session cookies...")
        await asyncio.sleep(3)
        await page.goto("https://dashboard.paytm.com/next/transactions", timeout=30000)
        await asyncio.sleep(4)

        # Extract all cookies
        cookies = await context.cookies("https://dashboard.paytm.com")

        extracted = {}
        for c in cookies:
            extracted[c["name"]] = c["value"]

        session_cookie = extracted.get("SESSION", "")
        xsrf_token = extracted.get("XSRF-TOKEN", "")
        ump_session = extracted.get("UMP_SESSION", session_cookie)
        abck = extracted.get("_abck", "")
        ak_bmsc = extracted.get("ak_bmsc", "")
        bm_sz = extracted.get("bm_sz", "")

        if not session_cookie or not xsrf_token:
            print("⚠️ Could not find SESSION or XSRF-TOKEN. Trying full list...")
            all_cookies = await context.cookies()
            for c in all_cookies:
                extracted[c["name"]] = c["value"]
            session_cookie = extracted.get("SESSION", "")
            xsrf_token = extracted.get("XSRF-TOKEN", "")

        print("=" * 65)
        print(f"🔑 SESSION Cookie: {'✅ FOUND' if session_cookie else '❌ NOT FOUND'}")
        print(f"🔑 XSRF Token:     {'✅ FOUND' if xsrf_token else '❌ NOT FOUND'}")
        print("=" * 65)

        if session_cookie and xsrf_token:
            update_data = {
                "PAYTM_SESSION": session_cookie,
                "PAYTM_XSRF_TOKEN": xsrf_token,
                "PAYTM_UMP_SESSION": ump_session,
                "PAYTM_ABCK": abck,
                "PAYTM_AK_BMSC": ak_bmsc,
                "PAYTM_BM_SZ": bm_sz,
            }
            update_env_file(update_data)
            print("\n🎉 SUCCESS! All Paytm cookies have been automatically saved to .env!")
            print("🚀 Bot is now ready for 100% Automated Payment Verification!")
        else:
            print("\n⚠️ Failed to extract cookies. Please make sure you are fully on the dashboard.")

        print("\nClosing browser in 5 seconds...")
        await asyncio.sleep(5)
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())

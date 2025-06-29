import time, psutil, pandas as pd
import os
import signal
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ── 1.  CONFIG ────────────────────────────────────────────────────────────────
PROFILE_DIR = Path("./whatsapp_profile")     # persistent WhatsApp session
CHECK_INTERVAL = 60                          # seconds between scans
RESP_CSV = "responses.csv"                   # predefined replies file

# ── 2.  LOAD PREDEFINED RESPONSES ─────────────────────────────────────────────
try:
    df = pd.read_csv(RESP_CSV)
    RESPONSES = dict(zip(df["question"].str.lower(), df["response"]))
    print("✅  Loaded responses.csv")
except Exception as e:
    raise SystemExit(f"❌  Failed to load {RESP_CSV}: {e}")

# ── 3.  IS PROFILE ALREADY IN USE? ────────────────────────────────────────────
def profile_in_use() -> bool:
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.info["name"] and "chrome" in p.info["name"].lower():
                if any(str(PROFILE_DIR) in arg for arg in p.info["cmdline"]):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

# ── 4.  CREATE CHROMEDRIVER WITH PROFILE ─────────────────────────────────────
def launch_driver() -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--app=https://web.whatsapp.com")  # open WA directly
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=opts)

# ── 5.  MAIN BOT LOOP ────────────────────────────────────────────────────────
def start_bot() -> None:
    PROFILE_DIR.mkdir(exist_ok=True)

    # Wait for Chrome to release the profile if needed
    print("🔍 Checking if profile is locked...")
    # while profile_in_use():
    #     kill_chrome_using_profile(PROFILE_DIR)
    #     time.sleep(2)
    #     print("⏳ Profile in use. Waiting 10s...")
    #     time.sleep(10)

    # Launch Chrome with persistent session
    try:
        driver = launch_driver()
    except Exception as e:
        print(f"❌ ChromeDriver launch failed: {e}")
        return

    # First-time QR scan check
    try:
        time.sleep(3)  # let page load
        qr_present = driver.find_elements(By.CSS_SELECTOR, "canvas[aria-label='Scan me!']")
        if qr_present:
            input("📷  Scan the QR code, then press ENTER to continue...")
        else:
            print("🔑  WhatsApp session already active.")
    except Exception as qr_err:
        print("⚠️  Could not detect QR code:", qr_err)

    print(f"🚀  Bot running — scanning every {CHECK_INTERVAL}s.")

    try:
        while True:
            unread_chats = driver.find_elements(
                By.XPATH, '//span[@aria-label="Unread message"]/ancestor::div[@role="row"]'
            )

            if not unread_chats:
                print("🔍  No unread chats.")
            for chat in unread_chats:
                try:
                    chat.click()
                    time.sleep(1.5)

                    contact = driver.find_element(By.XPATH, '//header//span[@title]').text
                    msgs = driver.find_elements(
                        By.CSS_SELECTOR, "div.message-in span.selectable-text"
                    )
                    if not msgs:
                        continue

                    last_msg = msgs[-1].text.strip().lower()
                    print(f"\n📥  {contact}: {last_msg}")

                    reply = RESPONSES.get(last_msg)
                    if reply:
                        box = driver.find_element(By.XPATH, '//div[@title="Type a message"]')
                        box.send_keys(reply, Keys.ENTER)
                        print(f"✅  Replied: {reply}")
                    else:
                        print("⚠️  No matching reply.")

                    time.sleep(1.2)
                except Exception as chat_err:
                    print("⚠️  Chat error:", chat_err)

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑  Stopped by user.")
    except Exception as loop_err:
        print("⚠️  Loop error:", loop_err)
    finally:
        driver.quit()

def kill_chrome_using_profile(profile_path):
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'chrome' in p.info['name'].lower() and any(str(profile_path) in arg for arg in p.info['cmdline']):
                print(f"💀 Killing Chrome PID {p.pid} using {profile_path}")
                os.kill(p.pid, signal.SIGTERM)  # Or SIGKILL for hard kill
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


# ── 6.  RUN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()

import time, psutil, pandas as pd, os, signal
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import tempfile

# ── 0.  CHOOSE PROFILE STRATEGY ───────────────────────────────────────────────
# A)  SINGLE‑LOGIN (persistent)  ← scan QR ONCE, stays logged in
# PROFILE_DIR = Path("./whatsapp_profile")

# B)  TEMP PROFILE (new each run) ← scan QR EVERY run, avoids lock errors
PROFILE_DIR = Path(tempfile.mkdtemp(prefix="wa_profile_"))

# ── 1.  CONFIG ────────────────────────────────────────────────────────────────
CHECK_INTERVAL = 15          # seconds between inbox scans
RESP_CSV       = "responses.csv"

# ── 2.  LOAD REPLIES ──────────────────────────────────────────────────────────
try:
    df = pd.read_csv(RESP_CSV)
    RESPONSES = {q.lower(): r for q, r in zip(df["question"], df["response"])}
    print("✅  Loaded responses.csv")
except Exception as e:
    raise SystemExit(f"❌  Failed to load {RESP_CSV}: {e}")

# ── 3.  PROFILE UTILITIES ─────────────────────────────────────────────────────
def profile_in_use() -> bool:
    """Return True if any Chrome process is using PROFILE_DIR."""
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if p.info['name'] and 'chrome' in p.info['name'].lower():
                if any(str(PROFILE_DIR) in arg for arg in p.info['cmdline']):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def kill_chrome_using_profile():
    """Kill any Chrome that has PROFILE_DIR open."""
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'chrome' in p.info['name'].lower() and any(str(PROFILE_DIR) in arg for arg in p.info['cmdline']):
                print(f"💀 Killing Chrome PID {p.pid} holding the profile")
                os.kill(p.pid, signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

# ── 4.  LAUNCH CHROME ────────────────────────────────────────────────────────
def launch_driver() -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--app=https://web.whatsapp.com")  # start directly at WA
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=opts)

# ── 5.  MAIN LOOP ────────────────────────────────────────────────────────────
def start_bot() -> None:
    PROFILE_DIR.mkdir(exist_ok=True)

    # ensure no conflicting Chrome processes
    while profile_in_use():
        kill_chrome_using_profile()
        print("⏳ Profile still in use, retrying in 5 s…")
        time.sleep(5)

    try:
        driver = launch_driver()
    except Exception as e:
        print(f"❌  ChromeDriver launch failed: {e}")
        return

    # first‑run QR
    time.sleep(3)
    if driver.find_elements(By.CSS_SELECTOR, "canvas[aria-label='Scan me!']"):
        input("📷  Scan QR code, then press ENTER…")
    else:
        print("🔑  Session already active.")

    print(f"🚀  Bot running — checks every {CHECK_INTERVAL}s.")

    try:
        while True:
            # ✅ XPath: find numeric unread badge, then go to the chat row
            unread_chats = driver.find_elements(
                By.XPATH,
                '//span[@aria-label and translate(@aria-label,"0123456789","")=""]'
                '/ancestor::div[@role="row"]'
            )
            chat_rows = driver.find_elements(By.XPATH, '//div[@role="row"]')
            print(f"🔎 Total chats discovered: {len(chat_rows)}")
            for row in chat_rows[:5]:  # Only print first 5 for brevity
                label = row.get_attribute("aria-label")
                print("  • aria-label:", label)
            time.sleep(5)
            print(f"📬  Unread chats found: {len(unread_chats)}")
            print(f"📬  Unread chats found: {len(chat_rows)}")


            for chat in unread_chats:
                try:
                    chat.click(); time.sleep(1.4)

                    contact = driver.find_element(By.XPATH, '//header//span[@title]').text
                    messages = driver.find_elements(
                        By.CSS_SELECTOR, "div.message-in span.selectable-text"
                    )
                    if not messages:
                        continue

                    last_msg = messages[-1].text.strip().lower()
                    print(f"📥  {contact}: {last_msg}")

                    reply = RESPONSES.get(last_msg)
                    if reply:
                        box = driver.find_element(By.XPATH, '//div[@title="Type a message"]')
                        box.send_keys(reply, Keys.ENTER)
                        print(f"✅  Replied: {reply}")
                    else:
                        print("⚠️  No predefined reply.")

                    time.sleep(1)

                except Exception as chat_err:
                    print("⚠️  Chat error:", chat_err)

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑  Bot stopped by user.")
    except Exception as loop_err:
        print("⚠️  Loop error:", loop_err)
    finally:
        driver.quit()

# ── 6.  RUN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()

import os
import time
import re
from datetime import datetime, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PORTAL_URL = "https://course.onlinecareerendeavour.com/student/tests"
MY_COOKIE_STRING = os.environ.get("MY_COOKIE_STRING")
# ----------------------

IST = timezone(timedelta(hours=5, minutes=30))

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
        print("[+] Telegram alert sent successfully.")
    except Exception as e:
        print(f"[-] Messaging failed: {e}")

def parse_portal_date(text_content):
    match = re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[A-P]M)', text_content)
    if match:
        date_str = match.group(1)
        try:
            naive_dt = datetime.strptime(date_str, "%b %d, %Y %I:%M %p")
            return naive_dt.replace(tzinfo=IST)
        except Exception:
            pass
    return None

def monitor_and_extract(context, page, lecture_title):
    print(f"[+] Fail-Safe activated for: {lecture_title}")
    
    max_attempts = 40
    for attempt in range(max_attempts):
        print(f"[*] Attempt {attempt + 1}/{max_attempts}: Checking for live button...")
        try:
            page.reload(wait_until="load")
            
            # Smart Wait: Ensure Angular loads the package before clicking
            try:
                page.wait_for_selector("text='NET DEC'", timeout=10000)
            except:
                pass
            page.wait_for_timeout(2000)
            
            # Bulletproof Angular Click
            page.locator("a[data-toggle='tab']:has-text('Live')").first.click(force=True)
            page.wait_for_timeout(4000) 
            
            # ONLY search inside the currently active tab
            lecture_row = page.locator("div.tab-pane.active tr", has_text=lecture_title)
            
            if lecture_row.count() > 0:
                play_button = lecture_row.locator("text='Play'").first
                if not play_button.is_visible():
                    play_button = lecture_row.locator("text='Play 1'").first

                if play_button.is_visible():
                    print("[+] Class is LIVE! Intercepting Zoom redirect...")
                    with context.expect_page() as new_page_info:
                        play_button.click(force=True)
                    
                    zoom_page = new_page_info.value
                    zoom_page.wait_for_load_state("networkidle")
                    zoom_url = zoom_page.url
                    zoom_page.close()
                    
                    send_telegram_msg(f"✨ Live Class Link Captured!\n📌 {lecture_title}\n🔗 Link: {zoom_url}")
                    return True
            
            print("[-] Button not active. Retrying in 30 seconds...")
        except Exception as error:
            print(f"⚠️ Transient error intercepted: {error}")
            
        time.sleep(30)
        
    send_telegram_msg(f"❌ Fail-Safe Alert: {lecture_title} link could not be captured.")
    return False

def check_schedule():
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    print(f"[*] Cloud run initialization time: {now_ist.strftime('%Y-%m-%d %I:%M:%S %p')} IST")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Spoof timezone to perfectly match your Indian schedule
        context = browser.new_context(
            extra_http_headers={"Cookie": MY_COOKIE_STRING},
            timezone_id="Asia/Kolkata"
        )
        page = context.new_page()
        
        page.goto(PORTAL_URL, wait_until="load")
        
        print("[*] Waiting for Angular to initialize course packages...")
        try:
            # Smart Wait: Watches the screen until your specific package text appears
            page.wait_for_selector("text='NET DEC'", timeout=15000)
        except Exception as e:
            print("[-] Package text wait timed out, continuing anyway...")
        page.wait_for_timeout(3000) # Give it a moment to settle
        
        print("[*] Clicking the Live tab...")
        try:
            page.locator("a[data-toggle='tab']:has-text('Live')").first.click(force=True)
            page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"[-] Could not click Live tab: {e}")
            
        # CRITICAL FIX: Only grab rows from the ACTIVE Live tab, ignore the hidden Videos tab
        rows = page.locator("div.tab-pane.active tr").all()
        upcoming_class_found = False
        
        for row in rows:
            row_text = row.text_content()
            
            if not row_text or "lecture" not in row_text.lower():
                continue
                
            class_time = parse_portal_date(row_text)
            if not class_time:
                continue
                
            lines = [line.strip() for line in row_text.splitlines() if line.strip()]
            if not lines:
                continue
            lecture_title = lines[0]
            
            if "Completed" in row_text or "Ended" in row_text:
                continue

            time_difference = class_time - now_ist
            if timedelta(minutes=-180) <= time_difference <= timedelta(minutes=180):
                upcoming_class_found = True
                sleep_seconds = max(0, int(time_difference.total_seconds()))
                
                print(f"[+] Found Target Class: {lecture_title}")
                print(f"[*] Scheduled for: {class_time.strftime('%I:%M %p')} IST")
                
                if sleep_seconds > 0:
                    print(f"[*] Sleeping for {sleep_seconds} seconds until class begins...")
                    time.sleep(sleep_seconds)
                else:
                    print("[*] Class time has already arrived! Executing immediately.")
                
                monitor_and_extract(context, page, lecture_title)
                break
                
        if not upcoming_class_found:
            print("[*] Scan complete: No classes scheduled within the next 180 minutes. Exiting instantly.")
            
        browser.close()

if __name__ == "__main__":
    check_schedule()

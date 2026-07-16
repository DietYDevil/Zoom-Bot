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

# Indian Standard Time (IST) Offset is UTC + 5:30
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
    """
    Extracts and parses dates like 'Jul 14, 2026 9:30 AM' from page text
    """
    match = re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[A-P]M)', text_content)
    if match:
        date_str = match.group(1)
        try:
            # Parse the string into a datetime object and attach IST timezone
            naive_dt = datetime.strptime(date_str, "%b %d, %Y %I:%M %p")
            return naive_dt.replace(tzinfo=IST)
        except Exception as e:
            print(f"[-] Date parsing error for '{date_str}': {e}")
    return None

def monitor_and_extract(context, page, lecture_title):
    print(f"[+] Fail-Safe activated for: {lecture_title}")
    
    # Retry window parameters: try every 30 seconds for 20 minutes (40 attempts)
    max_attempts = 40
    for attempt in range(max_attempts):
        print(f"[*] Attempt {attempt + 1}/{max_attempts}: Checking for live button...")
        try:
            page.reload(wait_until="networkidle")
            lecture_row = page.locator("tr", has_text=lecture_title)
            
            if lecture_row.count() > 0:
                # Target the play button inside this specific lecture row
                play_button = lecture_row.locator("text='Play'").first
                if not play_button.is_visible():
                    play_button = lecture_row.locator("text='Play 1'").first

                if play_button.is_visible():
                    print("[+] Class is LIVE! Intercepting Zoom redirect...")
                    with context.expect_page() as new_page_info:
                        play_button.click()
                    
                    zoom_page = new_page_info.value
                    zoom_page.wait_for_load_state("networkidle")
                    zoom_url = zoom_page.url
                    zoom_page.close()
                    
                    # Target achieved! Send message and terminate script cleanly
                    send_telegram_msg(f"✨ Live Class Link Captured!\n📌 {lecture_title}\n🔗 Link: {zoom_url}")
                    return True
            
            print("[-] Button not active or page loading. Retrying in 30 seconds...")
        except Exception as error:
            # Crucial Fail-Safe: If any browser or network error happens, catch it and keep looping
            print(f"⚠️ Transient error intercepted: {error}")
            
        time.sleep(30)
        
    # If loop completely finishes without success
    send_telegram_msg(f"❌ Fail-Safe Alert: {lecture_title} time arrived, but the link could not be captured within 20 minutes.")
    return False

def check_schedule():
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    print(f"[*] Cloud run initialization time: {now_ist.strftime('%Y-%m-%d %I:%M:%S %p')} IST")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(extra_http_headers={"Cookie": MY_COOKIE_STRING})
        page = context.new_page()
        
        page.goto(PORTAL_URL, wait_until="networkidle")
        
        # Gather all table rows from the live classes tab
        rows = page.locator("tr").all()
        upcoming_class_found = False
        
        for row in rows:
            row_text = row.text_content()
            if not row_text or "Lecture" not in row_text:
                continue
                
            class_time = parse_portal_date(row_text)
            if not class_time:
                continue
                
            # Extract clean title name (grabs up to the keyword Lecture/L_0X)
            title_match = re.search(r'(NET\s+.*?_LECTURE_\d+|MP_.*?_LECTURE_\d+)', row_text)
            lecture_title = title_match.group(1) if title_match else row_text.splitlines()[0].strip()

            # Check if class starts in next 35 mins OR is currently ongoing (started up to 2 hours ago)
            time_difference = class_time - now_ist
            if timedelta(minutes=-120) <= time_difference <= timedelta(minutes=180):
                upcoming_class_found = True
                
                # If time_difference is negative (class already started), sleep_seconds becomes 0
                sleep_seconds = max(0, int(time_difference.total_seconds()))
                
                print(f"[+] Found Target Class: {lecture_title}")
                print(f"[*] Scheduled for: {class_time.strftime('%I:%M %p')} IST")
                
                if sleep_seconds > 0:
                    print(f"[*] Sleeping for {sleep_seconds} seconds until class begins...")
                    time.sleep(sleep_seconds)
                else:
                    print("[*] Class time has already arrived! Executing immediately.")
                
                # Execute the fail-safe retrieval loop
                monitor_and_extract(context, page, lecture_title)
                break

                
        if not upcoming_class_found:
            print("[*] Scan complete: No classes scheduled within the next 180 minutes. Exiting instantly.")
            
        browser.close()

if __name__ == "__main__":
    check_schedule()

import os
import requests
import time
from datetime import datetime, timedelta, timezone

# Configurations
URL = "https://course.onlinecareerendeavour.com/student/tests/get-live-videos/6a11721a519e790e090f33f9"
IST = timezone(timedelta(hours=5, minutes=30))

# Secrets fetched from GitHub Actions Environment
MY_COOKIE = os.environ.get("PORTAL_COOKIE")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "cookie": MY_COOKIE,
    "user-agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"
}

def send_telegram_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[-] Error: Telegram credentials are missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def fetch_class_data():
    if not MY_COOKIE:
        print("[-] FATAL ERROR: MY_COOKIE is EMPTY! Your GitHub Secrets are not linked correctly in the YAML file.")
        return []
    print(f"[*] Debug: Cookie loaded successfully (Length: {len(MY_COOKIE)})")

    try:
        response = requests.get(URL, headers=HEADERS, timeout=10)
        print(f"[*] Debug: HTTP Status Code: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("status") and data.get("data"):
                    return data["data"]
            except ValueError:
                print("[-] FATAL ERROR: Server returned HTML instead of JSON.")
                print(f"[-] RAW SERVER RESPONSE: {response.text[:500]}")
        else:
            print(f"[-] Server rejected the request.")
            print(f"[-] RAW SERVER RESPONSE: {response.text[:500]}")
                
    except Exception as e:
        print(f"[-] Fetch error: {e}")
    return []

def main():
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    print(f"[*] Bot initialized at {now_ist.strftime('%Y-%m-%d %I:%M:%S %p')} IST")
    
    classes = fetch_class_data()
    if not classes:
        print("[*] No classes found in database. Exiting.")
        return

    target_class = None
    target_class_time = None

    # Step 1: Scan for the correct class in the active 2-hour window
    for cls in classes:
        title = cls.get("title", "Unknown Class")
        unix_time = cls.get("time_schedule")
        class_time = datetime.fromtimestamp(unix_time, tz=IST)
        
        # Calculate exactly how many minutes away the class is
        diff_mins = (class_time - datetime.now(timezone.utc).astimezone(IST)).total_seconds() / 60
        
        print(f"--- ANALYZING: {title} ---")
        print(f"    Scheduled: {class_time.strftime('%I:%M %p')}")
        
        if diff_mins < 0:
            print("    ❌ ACTION: Ignored (Class is in the past)")
        elif diff_mins > 130:
            print("    ❌ ACTION: Ignored (Class is too far in the future, will be caught in next cron run)")
        else:
            print("    ✅ ACTION: Target Locked! (Class is coming up in this 2-hour window)")
            target_class = cls
            target_class_time = class_time
            # Break the loop so we only focus on the next immediate class
            break 
            
    print("-" * 50)

    # Step 2: Execute the 5-Minute Warning Logic
    if target_class:
        title = target_class.get("title", "Unknown Class")
        unix_time = target_class.get("time_schedule")
        
        # Recalculate time to ensure precision right before sleeping
        current_time = datetime.now(timezone.utc).astimezone(IST)
        seconds_until_class = (target_class_time - current_time).total_seconds()
        
        # We want to wake up exactly 300 seconds (5 minutes) before the class starts
        sleep_seconds = seconds_until_class - 300 
        
        if sleep_seconds > 0:
            print(f"[*] Sleeping for {int(sleep_seconds / 60)} minutes to wait for link generation...")
            time.sleep(sleep_seconds)
            
        print("[*] 5-MINUTE WARNING! Fetching fresh Zoom credentials...")
        fresh_classes = fetch_class_data()
        
        # Find the exact same class in the fresh data to pull the generated link
        for fresh_cls in fresh_classes:
            if fresh_cls.get("time_schedule") == unix_time:
                zoom_url = fresh_cls.get("zoom_join_url", "No Link Yet")
                zoom_pass = fresh_cls.get("zoom_password", "None")
                
                msg = (
                    f"🚨 <b>CLASS STARTING IN FEW MINS</b> 🚨\n\n"
                    f"📚 <b>Subject:</b> {title}\n"
                    f"⏰ <b>Time:</b> {target_class_time.strftime('%I:%M %p')}\n"
                    f"🔗 <b>Zoom Link:</b> {zoom_url}\n"
                    f"🔑 <b>Passcode:</b> {zoom_pass}"
                )
                send_telegram_msg(msg)
                print("[+] Telegram alert sent successfully! Terminating script.")
                return 

    print("[*] Scan complete. Shutting down until next cron schedule.")

if __name__ == "__main__":
    main()

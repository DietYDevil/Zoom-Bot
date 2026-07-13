import time
import requests
from playwright.sync_api import sync_playwright

BOT_TOKEN = "8569732444:AAF-MXnoL8dyqcggIPsKCBr9fb652U3wXZk"
CHAT_ID = "1103873760"
PORTAL_URL = "https://course.onlinecareerendeavour.com/student/tests"
TARGET_LECTURE = "NET THERMO & STATISTICAL PHYSICS_LECTURE_04"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

def run_cloud_bot():
    with sync_playwright() as p:
        # Inject your copied session cookies to bypass login!
        # ... inside run_cloud_bot() ...
        browser = p.chromium.launch(headless=True)
        
        # Paste your massive cookie string inside these quotes
        MY_COOKIE_STRING = "reset_id=64874dd10477e17e9626e112; captchaWord=311663; device_id=281b9c84481067c950da; token=a577aa5fe418eb710a1429b198bbd307; student_id=64874dd10477e17e9626e112; sprofile_pic=https%3A%2F%2Fd3bioexaf647f4.cloudfront.net%2Fsubjectiveuploads%2Fuser_careerendeavour%2F1686588930.jpg; _ga_1RSRE352DM=GS2.1.s1783965172$o1$g0$t1783965172$j60$l0$h0; _ga=GA1.1.367767714.1783965172"
        
        # Inject the cookie directly into the browser's headers
        context = browser.new_context(
            extra_http_headers={
                "Cookie": MY_COOKIE_STRING
            }
        )
        page = context.new_page()
        
        page.goto(PORTAL_URL, wait_until="networkidle")
        
        # --- THE SAME EXTRACTION LOOP WE BUILT EARLIER ---
        max_attempts = 30
        for attempt in range(max_attempts):
            lecture_row = page.locator("tr", has_text=TARGET_LECTURE)
            if lecture_row.count() > 0:
                play_button = lecture_row.locator("text='Play 1'")
                if play_button.is_visible():
                    with context.expect_page() as new_page_info:
                        play_button.click()
                    zoom_page = new_page_info.value
                    zoom_page.wait_for_load_state("networkidle")
                    
                    send_telegram_msg(f"✨ Live Class Link!\n🔗 {zoom_page.url}")
                    zoom_page.close()
                    break
            
            time.sleep(30)
            page.reload(wait_until="networkidle")
            
        browser.close()

if __name__ == "__main__":
    run_cloud_bot()
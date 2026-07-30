import csv
import os
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

CSV_FILE = "jobs.csv"
# Removed EXCLUDE terms entirely to prevent throwing away multi-job agency pages
INCLUDE_KEYWORDS = ["director", "manager", "information", "pio", "chief", "lead", "officer", "communication"]

def send_email(subject, body):
    sender_email = os.environ.get("SENDER_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL")

    if not sender_email or not app_password:
        print("Email credentials missing.")
        return

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def read_csv_file(filepath):
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, mode="r", encoding=enc, errors="replace") as f:
                return list(csv.DictReader(f))
        except Exception:
            continue
    return []

def main():
    if not os.path.exists(CSV_FILE):
        print(f"{CSV_FILE} not found.")
        return

    rows = read_csv_file(CSV_FILE)
    if not rows:
        print("CSV file is empty or could not be parsed.")
        return

    results = []
    print(f"Starting headless Chrome scan of {len(rows)} targets...")

    with sync_playwright() as p:
        # Launch invisible Chrome
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for row in rows:
            agency = row.get("Agency", row.get("Title", row.get("Name", "Agency")))
            url = row.get("URL", row.get("Link", row.get("Website", "")))
            
            if not url or not url.startswith("http"):
                continue

            try:
                page = context.new_page()
                # Load the page and wait 3 seconds to ensure NEOGOV JS loads the jobs
                page.goto(url.strip(), wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000) 
                
                text = page.inner_text("body").lower()
                page.close()

                # Search for target keywords
                found_matches = [kw.upper() for kw in INCLUDE_KEYWORDS if kw in text]
                
                if found_matches:
                    print(f"[MATCH] {agency}: {found_matches}")
                    results.append(f"<li><b>{agency}</b>: Found ({', '.join(found_matches)}) — <a href='{url}'>{url}</a></li>")
                else:
                    print(f"[NO MATCH] {agency}")

            except Exception as e:
                print(f"[TIMEOUT/ERROR] {agency} - {url}")

        browser.close()

    if results:
        email_body = f"<h2>Daily Job Hits</h2><ul>{''.join(results)}</ul>"
        send_email("Daily Job Scan Matches Found", email_body)
    else:
        send_email("Scan complete. No matches found today.","Scan complete. No matches found today.")

if __name__ == "__main__":
    main()

import csv
import os
import smtplib
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

CSV_FILE = "jobs.csv"
INCLUDE_KEYWORDS = ["director", "manager", "public information", "pio", "chief", "lead"]
# Only exclude if these words appear in the TITLE itself, not in the body text
EXCLUDE_TITLE_KEYWORDS = ["assistant director", "deputy", "intern", "technician"]

def check_url(url):
    try:
        # Standard headers + NEOGOV JSON/HTML acceptance
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check page title and main headings specifically
        page_title = soup.title.string.lower() if soup.title else ""
        text = soup.get_text().lower()
        
        found_matches = []
        for kw in INCLUDE_KEYWORDS:
            if kw in text or kw in page_title:
                # Ensure the title itself isn't an assistant/intern role
                if not any(ex in page_title for ex in EXCLUDE_TITLE_KEYWORDS):
                    found_matches.append(kw.upper())
        
        return list(set(found_matches))
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return []

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

    print("Starting scan...")
    rows = read_csv_file(CSV_FILE)
    results = []
    
    for row in rows:
        agency = row.get("Agency", row.get("Title", row.get("Name", "Agency")))
        url = row.get("URL", row.get("Link", row.get("Website", "")))
        
        if not url or not url.startswith("http"):
            continue
        
        matches = check_url(url.strip())
        if matches:
            print(f"[MATCH] {agency}: {matches}")
            results.append(f"<li><b>{agency}</b>: Found ({', '.join(matches)}) — <a href='{url}'>{url}</a></li>")
        else:
            print(f"[NO MATCH] {agency}")

    if results:
        email_body = f"<h2>Daily Job Hits</h2><ul>{''.join(results)}</ul>"
        send_email("Daily Job Scan Matches Found", email_body)
    else:
        send_email("Scan complete. No matches found today.","Scan complete. No matches found today.")

if __name__ == "__main__":
    main()

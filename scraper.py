import csv
import os
import smtplib
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION & KEYWORDS ---
CSV_FILE = "jobs.csv"
INCLUDE_KEYWORDS = ["director", "manager", "public information", "pio", "lead", "officer", "chief"]
EXCLUDE_KEYWORDS = ["coordinator", "assistant", "intern", "technician", "specialist"]

def check_url(url):
    """Fetches web page text and searches for target keywords."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text().lower()
        
        found_matches = []
        for kw in INCLUDE_KEYWORDS:
            if kw in text and not any(ex in text for ex in EXCLUDE_KEYWORDS):
                found_matches.append(kw.upper())
        
        return list(set(found_matches))
    except Exception:
        return []

def send_email(subject, body):
    """Sends a summary email via Gmail SMTP using GitHub Secrets."""
    sender_email = os.environ.get("SENDER_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL")

    if not sender_email or not app_password:
        print("Email credentials not found. Skipping email dispatch.")
        return

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print("Summary email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

def read_csv_file(filepath):
    """Reads CSV file trying UTF-8 first, falling back to Latin-1/CP1252 if needed."""
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, mode="r", encoding=enc, errors="replace") as f:
                reader = list(csv.DictReader(f))
                return reader
        except Exception:
            continue
    return []

def main():
    if not os.path.exists(CSV_FILE):
        print(f"File {CSV_FILE} not found!")
        return

    print("Starting scan across target career pages...")
    rows = read_csv_file(CSV_FILE)
    
    if not rows:
        print("CSV file is empty or could not be parsed.")
        return

    results = []
    
    for row in rows:
        agency = row.get("Agency", row.get("Title", row.get("Name", "Unknown Agency")))
        url = row.get("URL", row.get("Link", row.get("Website", "")))
        
        if not url or not url.startswith("http"):
            continue
        
        matches = check_url(url.strip())
        if matches:
            results.append(f"<li><b>{agency}</b>: Found keywords ({', '.join(matches)}) — <a href='{url}'>{url}</a></li>")

    # Force a test email dispatch
    if results:
        email_body = f"<h2>Daily Executive Job Search Hits</h2><ul>{''.join(results)}</ul>"
    else:
        email_body = "<h2>Test Run Successful</h2><p>Your GitHub Action scraper is connected and email alerts are working properly!</p>"
    
    send_email("Job Search Scraper Test Email", email_body)

if __name__ == "__main__":
    main()

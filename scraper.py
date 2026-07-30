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
        
        # Simple keyword presence check
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

def main():
    if not os.path.exists(CSV_FILE):
        print(f"File {CSV_FILE} not found!")
        return

    print("Starting scan across target career pages...")
    results = []
    
    with open(CSV_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            agency = row.get("Agency", row.get("Title", "Unknown Agency"))
            url = row.get("URL", row.get("Link", ""))
            
            if not url:
                continue
            
            matches = check_url(url)
            if matches:
                results.append(f"<li><b>{agency}</b>: Found keywords ({', '.join(matches)}) — <a href='{url}'>{url}</a></li>")

    if results:
        email_body = f"<h2>Daily Executive Job Search Hits</h2><ul>{''.join(results)}</ul>"
        send_email("Daily Job Scan Matches Found", email_body)
    else:
        print("Scan complete. No new high-priority matches found today.")

if __name__ == "__main__":
    main()

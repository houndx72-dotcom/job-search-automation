import csv
import os
import smtplib
import time
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

CSV_FILE = "jobs.csv"
INCLUDE_KEYWORDS = ["director", "manager", "pio", "information", "chief", "communications", "relations"]

# Safety Kill Switch: Prevent the script from running infinitely (e.g., max 45 minutes)
MAX_RUNTIME_SECONDS = 45 * 60 

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

def extract_url(row):
    for key, value in row.items():
        if key and value and isinstance(value, str):
            k = key.strip().lower()
            if 'url' in k or 'link' in k or 'web' in k:
                return value.strip()
    for value in row.values():
        if value and isinstance(value, str):
            v = value.strip()
            if v.startswith("http") or v.startswith("www") or ".gov" in v or ".com" in v:
                return v
    return ""

def main():
    if not os.path.exists(CSV_FILE):
        print(f"{CSV_FILE} not found.")
        return

    rows = read_csv_file(CSV_FILE)
    if not rows:
        print("CSV file is empty or could not be parsed.")
        return

    results = []
    scanned_count = 0
    start_time = time.time()

    print(f"Loaded {len(rows)} rows. Scanning for specific job titles...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # SPEED FIX 1: Block heavy resources (images, media, fonts, CSS)
        # This prevents government pages from hanging while trying to load a massive town seal or video
        def block_bloat(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                route.abort()
            else:
                route.continue_()
                
        context.route("**/*", block_bloat)

        for row in rows:
            # SPEED FIX 2: Global timeout check
            if time.time() - start_time > MAX_RUNTIME_SECONDS:
                print("⚠️ MAXIMUM RUNTIME REACHED (45 Mins). Halting loop to prevent infinite hang.")
                break

            agency = row.get("Agency", row.get("Title", row.get("Name", "Agency/Organization")))
            raw_url = extract_url(row)
            
            if not raw_url:
                continue

            if not raw_url.startswith("http"):
                raw_url = "https://" + raw_url
            
            scanned_count += 1

            try:
                page = context.new_page()
                
                # SPEED FIX 3: Auto-dismiss popups/alerts that freeze Playwright
                page.on("dialog", lambda dialog: dialog.dismiss())
                
                # Reduced timeout to 15 seconds. If a municipal site takes longer, skip it.
                page.goto(raw_url, wait_until="domcontentloaded", timeout=15000)
                
                # SPEED FIX 4: Soft-wait instead of forced 3.5s sleep. Let it process immediately if loaded.
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass # Ignore if network isn't perfectly idle, just grab what we have
                
                # SPEED FIX 5: Bulk grab all text instantly using JavaScript instead of querying thousands of DOM elements
                body_text = page.evaluate("document.body ? document.body.innerText : ''")
                
                matched_titles = []
                # Process the lines purely in fast Python memory
                for line in body_text.split('\n'):
                    clean_el = line.strip()
                    if 5 < len(clean_el) < 100: # Filter out single characters or huge paragraphs
                        lower_el = clean_el.lower()
                        if any(kw in lower_el for kw in INCLUDE_KEYWORDS):
                            if clean_el not in matched_titles:
                                matched_titles.append(clean_el)

                page.close()

                if matched_titles:
                    print(f"[{scanned_count}] MATCH at {agency}: {matched_titles}")
                    titles_html = "<ul>" + "".join([f"<li>{t}</li>" for t in matched_titles[:5]]) + "</ul>"
                    results.append(f"<li><b>{agency}</b>:<br>{titles_html}— <a href='{raw_url}'>Portal Link</a></li><br>")
                else:
                    print(f"[{scanned_count}] CLEAR: {agency}")

            except Exception as e:
                print(f"[{scanned_count}] TIMED OUT / SKIPPED at {agency}")
                try:
                    page.close()
                except:
                    pass

        browser.close()

    if results:
        email_body = f"<h2>Target Job Hits (Scanned {scanned_count} sites)</h2><ul>{''.join(results)}</ul>"
        send_email("Executive Job Scan Matches Found", email_body)
    else:
        print("Scan complete. No title matches found.")
        # Optional: Send a "Nothing found" email just so you know it ran
        send_email("Executive Job Scan - No Matches Today", f"<p>Scan complete across {scanned_count} municipal boards. No executive titles found.</p>")

if __name__ == "__main__":
    main()

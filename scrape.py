# Find out when our schedules come out...

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import smtplib
import ssl
from email.message import EmailMessage
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
import json
import config as cfg

# Define
URL = "https://www.fridayparentportal.com/ocvts"
STATE_FILE = Path("menu_state.json")

USERNAME = cfg.USERNAME
PASSWORD = cfg.PASSWORD

TEST_MODE = False
NOTIFICATIONS = True

# Email cooldowns
COOLDOWN_FILE = Path("alert_cooldown.json")
COOLDOWN_MINUTES = 60 * 12  # only alert once every 12 hours max
SMTP_HOST = cfg.SMTP_HOST
SMTP_PORT = cfg.SMTP_PORT
SMTP_USERNAME = cfg.SMTP_USERNAME
FROM_EMAIL = cfg.FROM_EMAIL
RECIPIENTS = cfg.RECIPIENTS
SMTP_PASSWORD = cfg.SMTP_PASSWORD

# Email Setup

# Read Old list of items
def read_state():
    if not STATE_FILE.exists():
        return []
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# Write
def write_state(items):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=4)

# Get list
def get_menu_items(driver):
    wait = WebDriverWait(driver, 20)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#nav > li > a")))

    menu_links = driver.find_elements(By.CSS_SELECTOR, "#nav > li > a")

    items = []
    for link in menu_links:
        text = link.text.strip()
        href = link.get_attribute("href")
        if text:
            items.append({
                "text": text,
                "href": href
            })

    return items

# Compare new list to old list
def compare_items(old_items, new_items):
    old_texts = {item["text"] for item in old_items}
    new_texts = {item["text"] for item in new_items}

    added = [item for item in new_items if item["text"] not in old_texts]
    removed = [item for item in old_items if item["text"] not in new_texts]

    count_increased = len(new_items) > len(old_items)

    return {
        "added": added,
        "removed": removed,
        "count_increased": count_increased,
        "old_count": len(old_items),
        "new_count": len(new_items)
    }

# OPen Json file
def read_cooldown():
    if not COOLDOWN_FILE.exists():
        return {}
    try:
        with COOLDOWN_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Write
def write_cooldown(data):
    with COOLDOWN_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Check if enough time 
def should_send_alert(key: str, cooldown_minutes: int) -> bool:
    from datetime import datetime, timedelta

    cooldowns = read_cooldown()
    last_sent_str = cooldowns.get(key)

    if last_sent_str:
        last_sent = datetime.fromisoformat(last_sent_str)
        if datetime.now() < last_sent + timedelta(minutes=cooldown_minutes):
            return False

    cooldowns[key] = datetime.now().isoformat()
    write_cooldown(cooldowns)
    return True

# Email People
def email(recipients: list[str]) -> None:
    
    msg = EmailMessage()
    msg["Subject"] = "GUYS SCHEDULES ARE OUT"
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(recipients)
    msg.set_content(f"Go check portal or smth.\n- Krupam\n\nP.S Sorry if I missed anyone, it is REALLY annoying to type out emails.")

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls(context=context)
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(msg)

# Print/notifiy of changes
def notify(changes):
    print("\n Menu Change Detected =====")

    if changes["count_increased"]:
        print(f"Menu count increased: {changes['old_count']} : {changes['new_count']}")

    if changes["added"]:
        print("\nNew items:")
        for item in changes["added"]:
            print(f"- {item['text']} : {item['href']}")

    if changes["removed"]:
        print("\nRemoved items:")
        for item in changes["removed"]:
            print(f"- {item['text']} : {item['href']}")

    if NOTIFICATIONS and should_send_alert("menu_change_alert", COOLDOWN_MINUTES):
        email(RECIPIENTS)
        print("Sending emails...")
    elif NOTIFICATIONS:
        print("Alert suppressed (cooldown active).")


# Start browser
driver = webdriver.Chrome()

try:
# Go to webpage
    print("Opening page...")
    driver.get("https://www.fridayparentportal.com/ocvts")

    time.sleep(2)

    # Cookies
    cookie = {
        "name": "DISTRICTID",
        "value": "ocvts"
    }
    driver.add_cookie(cookie)
    driver.refresh()
    print("Setting Cookies...")

    wait = WebDriverWait(driver, 20)
    time.sleep(1)

    # Find inputs
    username = wait.until(EC.presence_of_element_located((By.NAME, "username")))
    password = wait.until(EC.presence_of_element_located((By.NAME, "password")))

    # Send Values
    username.send_keys(USERNAME)
    password.send_keys(PASSWORD)

    # Submit form
    password.send_keys(Keys.RETURN)
    print("Logging in...")

    current_items = get_menu_items(driver)

    # Test the system
    if TEST_MODE:
        current_items.append({
            "text": "Schedule Test Item",
            "href": "https://test.local/schedule"
        })

    print(f"\nFound {len(current_items)} current menu items:")
    for item in current_items:
        print(f"{item['text']} -> {item['href']}")

    old_items = read_state()

    if not old_items:
        print("\nNo previous state found. Saving baseline menu.")
        write_state(current_items)
    else:
        changes = compare_items(old_items, current_items)

        if changes["added"] or changes["removed"] or changes["count_increased"]:
            notify(changes)
        else:
            print("\nNo menu changes detected.")

        write_state(current_items)

finally:
    print("\nClosing browser...")
    driver.quit()


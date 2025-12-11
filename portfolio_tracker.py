
import json
import os
from datetime import datetime, timedelta

HISTORY_FILE = "portfolio_history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def autosave_portfolio_value(value):
    history = load_history()
    now = datetime.now()

    # Save every 8 hours
    if history:
        last_time = datetime.fromisoformat(history[-1]["timestamp"])
        if now - last_time < timedelta(hours=8):
            return

    history.append({
        "timestamp": now.isoformat(),
        "value": value
    })
    save_history(history)

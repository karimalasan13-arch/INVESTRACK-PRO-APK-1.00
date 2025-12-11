import json, os, datetime as dt

# ---------------------------
# File paths
# ---------------------------
CRYPTO_HISTORY_FILE = "crypto_history.json"
STOCK_HISTORY_FILE  = "stock_history.json"

CRYPTO_INV_FILE = "crypto_investments.json"
STOCK_INV_FILE  = "stock_investments.json"


# ---------------------------
# Generic JSON helpers
# ---------------------------
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------
# Investment LOAD/SAVE
# ---------------------------
def load_crypto_investments():
    return load_json(CRYPTO_INV_FILE, {"assets": {}, "investment": 0.0})


def save_crypto_investments(data):
    save_json(CRYPTO_INV_FILE, data)


def load_stock_investments():
    return load_json(STOCK_INV_FILE, {"assets": {}, "investment": 0.0})


def save_stock_investments(data):
    save_json(STOCK_INV_FILE, data)


# ---------------------------
# History (daily values)
# ---------------------------
def load_crypto_history():
    return load_json(CRYPTO_HISTORY_FILE, [])


def save_crypto_history(history):
    save_json(CRYPTO_HISTORY_FILE, history)


def load_stock_history():
    return load_json(STOCK_HISTORY_FILE, [])


def save_stock_history(history):
    save_json(STOCK_HISTORY_FILE, history)


# ---------------------------
# Append today's value
# ---------------------------
def append_daily_value(history, value):
    """
    Saves only *one* entry per day.
    """
    today = dt.date.today()
    timestamp = dt.datetime.utcnow().isoformat()

    updated = False
    for item in history:
        entry_date = dt.datetime.fromisoformat(item["timestamp"]).date()
        if entry_date == today:
            item["value"] = value
            updated = True
            break

    if not updated:
        history.append({"timestamp": timestamp, "value": value})

    return history

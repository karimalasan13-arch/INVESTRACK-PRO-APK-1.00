import json
from db import save_setting, save_holdings

# ---- Crypto ----
with open("user_data.json") as f:
    data = json.load(f)

save_setting("crypto_rate", data["crypto_rate"])
save_setting("crypto_invested", data["crypto_investment"])
save_holdings("crypto_holdings", data["crypto_holdings"])

# ---- Stock ----
with open("stock_data.json") as f:
    data = json.load(f)

save_setting("stock_rate", data["rate"])
save_setting("stock_invested", data["invested"])
save_holdings("stock_holdings", data["assets"])

print("Migration complete ✅")

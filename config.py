# ===== Lobster AI Config =====

# Route
FROM = "TPE"
TO = "KIX"

# Date
GO_DATE = "2026-08-28"
BACK_DATE = "2026-08-31"

# Budget
MAX_PRICE = 12000

# Airlines
AIRLINES = [
    "BR",   # EVA
    "CI",   # China Airlines
    "JX"    # STARLUX
]

# Flight Rules
DIRECT_ONLY = True

# Outbound flight must depart no later than 11:00
GO_BEFORE = "11:00"

# Exclude red-eye flights
NO_REDEYE = True

# Telegram
SEND_ONLY_ON_PRICE_DROP = True

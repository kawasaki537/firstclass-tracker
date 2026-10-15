# ===== Lobster AI Config =====

# Route
FROM = "TPE"
TO = "KIX"

# Fixed round-trip dates (YYYY-MM-DD)
GO_DATE = "2027-06-01"
BACK_DATE = "2027-06-30"

# One adult; budget applies to the complete round trip in TWD
ADULTS = 1
CURRENCY = "TWD"
MAX_PRICE = 15000

# Allowed airlines
AIRLINES = [
    "BR",  # EVA Air
    "CI",  # China Airlines
    "JX",  # STARLUX Airlines
]

# Flight rules
DIRECT_ONLY = True
GO_BEFORE = "11:00"  # outbound departure local time must be earlier than 11:00
NO_REDEYE = True     # excludes departures from 22:00 through 05:59 local time

# Notify only on first qualifying fare or a lower fare than the last notification
SEND_ONLY_ON_PRICE_DROP = True

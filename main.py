import config

print("🦞 Lobster AI")

print(f"Route : {config.FROM} -> {config.TO}")
print(f"Go    : {config.GO_DATE}")
print(f"Back  : {config.BACK_DATE}")
print(f"Budget: {config.MAX_PRICE}")

print("Airlines:")
for airline in config.AIRLINES:
    print(" -", airline)

print("Direct only :", config.DIRECT_ONLY)
print("Go before   :", config.GO_BEFORE)
print("No redeye   :", config.NO_REDEYE)

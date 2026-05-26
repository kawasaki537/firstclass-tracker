import os
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# 模擬機票價格
price = 3999

# 你的目標價格
target_price = 5500

if price <= target_price:
    message = f"🦞 發現便宜機票！\n\nTPE → BKK\n價格：{price} TWD"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })

    print("已發送通知")
else:
    print("價格太高")

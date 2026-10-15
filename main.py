import json
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
import config

AMADEUS_BASE_URL = "https://api.amadeus.com"
STATE_PATH = Path("price_state.json")
TIMEOUT = 30


class FlightSearchError(RuntimeError):
    pass


def validate_config() -> None:
    """Validate route/date/settings before making any external API requests."""
    try:
        go_date = date.fromisoformat(config.GO_DATE)
        back_date = date.fromisoformat(config.BACK_DATE)
    except (TypeError, ValueError) as exc:
        raise FlightSearchError("GO_DATE and BACK_DATE must use YYYY-MM-DD dates.") from exc

    if go_date < date.today():
        raise FlightSearchError(f"GO_DATE {go_date} is in the past.")
    if back_date <= go_date:
        raise FlightSearchError("BACK_DATE must be later than GO_DATE.")
    if not config.FROM or not config.TO or config.FROM == config.TO:
        raise FlightSearchError("FROM and TO must be different airport codes.")
    if not config.AIRLINES:
        raise FlightSearchError("AIRLINES must contain at least one airline code.")
    if config.ADULTS < 1:
        raise FlightSearchError("ADULTS must be at least 1.")
    if Decimal(str(config.MAX_PRICE)) <= 0:
        raise FlightSearchError("MAX_PRICE must be greater than zero.")
    if len(config.GO_BEFORE) != 5 or config.GO_BEFORE[2] != ":":
        raise FlightSearchError("GO_BEFORE must use HH:MM format.")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise FlightSearchError(f"Missing required GitHub Secret: {name}")
    return value


def telegram_send(text: str) -> None:
    token = required_env("BOT_TOKEN")
    chat_id = required_env("CHAT_ID")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise FlightSearchError(f"Telegram rejected the message: {payload}")


def get_amadeus_token() -> str:
    client_id = required_env("AMADEUS_CLIENT_ID")
    client_secret = required_env("AMADEUS_CLIENT_SECRET")
    response = requests.post(
        f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    if not response.ok:
        raise FlightSearchError(
            f"Amadeus authentication failed ({response.status_code}). "
            "Confirm that production API credentials are used in GitHub Secrets."
        )
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise FlightSearchError("Amadeus response did not include an access token.")
    return token


def parse_hour(timestamp: str) -> int:
    # Amadeus local airport times use ISO timestamps such as 2027-06-01T08:20:00.
    try:
        return int(timestamp.split("T", 1)[1][:2])
    except (IndexError, ValueError):
        raise FlightSearchError(f"Unexpected flight time format: {timestamp!r}")


def segment_carrier(segment: dict) -> str:
    operating = segment.get("operating") or {}
    return operating.get("carrierCode") or segment.get("carrierCode", "")


def format_itinerary(itinerary: dict, label: str) -> str:
    segments = itinerary.get("segments") or []
    if not segments:
        return f"{label}: time unavailable"
    first = segments[0]
    last = segments[-1]
    dep_at = first.get("departure", {}).get("at", "")
    arr_at = last.get("arrival", {}).get("at", "")
    dep_time = dep_at[11:16] if len(dep_at) >= 16 else dep_at
    arr_time = arr_at[11:16] if len(arr_at) >= 16 else arr_at
    carrier = segment_carrier(first) or first.get("carrierCode", "Unknown")
    flight_number = f"{carrier}{first.get('number', '')}"
    return (
        f"{label}: {dep_time} {first.get('departure', {}).get('iataCode', '?')} "
        f"→ {arr_time} {last.get('arrival', {}).get('iataCode', '?')} "
        f"({flight_number})"
    )


def is_qualifying_offer(offer: dict) -> bool:
    itineraries = offer.get("itineraries") or []
    if len(itineraries) != 2:
        return False

    outbound, inbound = itineraries
    outbound_segments = outbound.get("segments") or []
    inbound_segments = inbound.get("segments") or []

    # Direct flight means exactly one segment in each direction.
    if config.DIRECT_ONLY and (
        len(outbound_segments) != 1 or len(inbound_segments) != 1
    ):
        return False

    if not outbound_segments or not inbound_segments:
        return False

    # The outbound flight must depart at or before the configured local-time cutoff.
    outbound_departure = outbound_segments[0].get("departure", {}).get("at", "")

    if outbound_departure and outbound_departure[11:16] > config.GO_BEFORE:
        return False

    all_segments = outbound_segments + inbound_segments
    allowed_airlines = set(config.AIRLINES)
    if not all_segments:
        return False

    # Use operating carrier where available to avoid accepting a codeshare
    # operated by an airline outside the requested list.
    for segment in all_segments:
        if segment_carrier(segment) not in allowed_airlines:
            return False

    if config.NO_REDEYE:
        # Practical rule: exclude segments departing 22:00–05:59 local time.
        for segment in all_segments:
            departure = segment.get("departure", {}).get("at", "")
            if departure:
                hour = parse_hour(departure)
                if hour >= 22 or hour < 6:
                    return False

    return True


def search_offers(token: str) -> list:
    params = {
        "originLocationCode": config.FROM,
        "destinationLocationCode": config.TO,
        "departureDate": config.GO_DATE,
        "returnDate": config.BACK_DATE,
        "adults": config.ADULTS,
        "currencyCode": config.CURRENCY,
        "includedAirlineCodes": ",".join(config.AIRLINES),
        "nonStop": str(config.DIRECT_ONLY).lower(),
        "max": 250,
    }
    response = requests.get(
        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    if not response.ok:
        body = response.text[:700].replace("\n", " ")
        raise FlightSearchError(
            f"Amadeus flight search failed ({response.status_code}): {body}"
        )
    payload = response.json()
    if "data" not in payload:
        raise FlightSearchError("Amadeus response did not contain a data field.")
    return payload.get("data") or []


def offer_price(offer: dict) -> Decimal:
    try:
        return Decimal(str(offer["price"]["grandTotal"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise FlightSearchError(f"Offer had no valid total price: {exc}") from exc


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        print("Warning: previous price state was unreadable; starting fresh.")
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    validate_config()
    print("🦞 Lobster AI — live flight-price check")
    print(f"Route: {config.FROM} → {config.TO} → {config.FROM}")
    print(f"Dates: {config.GO_DATE} / {config.BACK_DATE}")
    print(f"Budget: {config.CURRENCY} {config.MAX_PRICE}")
    print(f"Airlines: {', '.join(config.AIRLINES)}")
    print(f"Direct only: {config.DIRECT_ONLY}; outbound at or before {config.GO_BEFORE}")
    print(f"Exclude red-eye departures: {config.NO_REDEYE}")

    token = get_amadeus_token()
    raw_offers = search_offers(token)
    print(f"Offers returned by Amadeus: {len(raw_offers)}")

    qualifying = []
    for offer in raw_offers:
        if not is_qualifying_offer(offer):
            continue
        price = offer_price(offer)
        qualifying.append((price, offer))

    qualifying.sort(key=lambda item: item[0])
    under_budget = [
        (price, offer)
        for price, offer in qualifying
        if price <= Decimal(str(config.MAX_PRICE))
    ]

    print(f"Offers matching all flight rules: {len(qualifying)}")
    print(f"Offers at or below budget: {len(under_budget)}")

    if not under_budget:
        print("No qualifying real offers are currently within budget. No price alert sent.")
        return 0

    best_price = under_budget[0][0]
    state = load_state()
    previous_raw = state.get("last_notified_price")
    previous_price = Decimal(str(previous_raw)) if previous_raw is not None else None

    should_notify = (
        not config.SEND_ONLY_ON_PRICE_DROP
        or previous_price is None
        or best_price < previous_price
    )
    if not should_notify:
        print(
            f"Best fare {best_price} is not below the last notified fare "
            f"{previous_price}; duplicate alert suppressed."
        )
        return 0

    lines = [
        "🦞 Lobster AI｜找到符合條件的真實機票報價",
        f"台北 TPE ⇄ 大阪 KIX｜{config.GO_DATE} – {config.BACK_DATE}",
        f"來回總價：NT$ {best_price:,.0f}（Amadeus API 報價，訂票前請再次確認）",
        f"預算：NT$ {config.MAX_PRICE:,.0f}",
        "",
    ]
    for index, (price, offer) in enumerate(under_budget[:5], start=1):
        itineraries = offer.get("itineraries") or []
        lines.extend([
            f"{index}. 來回 NT$ {price:,.0f}",
            format_itinerary(itineraries[0], "去程"),
            format_itinerary(itineraries[1], "回程"),
            "",
        ])
    lines.append(
        "篩選：BR／CI／JX、去程不晚於 11:00、直飛、排除 22:00–05:59 起飛航段。"
    )
    lines.append("價格與座位可能變動；此通知不是訂票或最終出票確認。")

    telegram_send("\n".join(lines))
    state["last_notified_price"] = str(best_price)
    state["last_notified_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    save_state(state)
    print(f"Telegram alert sent for best fare: {best_price}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FlightSearchError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

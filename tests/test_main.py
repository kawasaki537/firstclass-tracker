import os
import unittest
from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests

import config
import main


def segment(dep, arr, carrier="BR", number="123", operating=None):
    item = {
        "departure": {"iataCode": dep, "at": "2027-06-01T08:00:00"},
        "arrival": {"iataCode": arr, "at": "2027-06-01T10:00:00"},
        "carrierCode": carrier,
        "number": number,
    }
    # Set departure/arrival independently in tests using ISO strings.
    item["departure"]["at"] = dep
    item["arrival"]["at"] = arr
    if operating:
        item["operating"] = {"carrierCode": operating}
    return item


def offer(out_dep="2027-06-01T08:00:00", back_dep="2027-06-30T15:00:00",
          out_carrier="BR", back_carrier="CI", out_segments_count=1,
          back_segments_count=1, out_operating=None, price="12345.00"):
    outbound = []
    for i in range(out_segments_count):
        outbound.append({
            "departure": {"iataCode": "TPE", "at": out_dep},
            "arrival": {"iataCode": "KIX", "at": "2027-06-01T10:00:00"},
            "carrierCode": out_carrier,
            "number": str(100 + i),
            **({"operating": {"carrierCode": out_operating}} if out_operating else {}),
        })
    inbound = []
    for i in range(back_segments_count):
        inbound.append({
            "departure": {"iataCode": "KIX", "at": back_dep},
            "arrival": {"iataCode": "TPE", "at": "2027-06-30T18:00:00"},
            "carrierCode": back_carrier,
            "number": str(200 + i),
        })
    return {
        "itineraries": [{"segments": outbound}, {"segments": inbound}],
        "price": {"grandTotal": price},
    }


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.go = config.GO_DATE
        self.back = config.BACK_DATE

    def tearDown(self):
        config.GO_DATE = self.go
        config.BACK_DATE = self.back

    def test_repository_dates_are_valid_and_future(self):
        main.validate_config()
        self.assertEqual(config.GO_DATE, "2027-06-01")
        self.assertEqual(config.BACK_DATE, "2027-06-30")

    def test_invalid_date_format_fails(self):
        config.GO_DATE = "2027/06/01"
        with self.assertRaisesRegex(main.FlightSearchError, "YYYY-MM-DD"):
            main.validate_config()

    def test_past_date_fails(self):
        config.GO_DATE = (date.today() - timedelta(days=1)).isoformat()
        config.BACK_DATE = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(main.FlightSearchError, "in the past"):
            main.validate_config()

    def test_return_must_be_after_departure(self):
        config.GO_DATE = (date.today() + timedelta(days=5)).isoformat()
        config.BACK_DATE = config.GO_DATE
        with self.assertRaisesRegex(main.FlightSearchError, "later than GO_DATE"):
            main.validate_config()


class FlightFilterTests(unittest.TestCase):
    def test_accepts_matching_direct_offer(self):
        self.assertTrue(main.is_qualifying_offer(offer()))

    def test_rejects_connection(self):
        self.assertFalse(main.is_qualifying_offer(offer(out_segments_count=2)))

    def test_rejects_unapproved_airline(self):
        self.assertFalse(main.is_qualifying_offer(offer(out_carrier="XX")))

    def test_rejects_codeshare_operated_by_unapproved_airline(self):
        self.assertFalse(main.is_qualifying_offer(offer(out_operating="XX")))

    def test_rejects_outbound_after_cutoff(self):
        self.assertFalse(main.is_qualifying_offer(offer(out_dep="2027-06-01T11:01:00")))

    def test_accepts_outbound_exactly_at_cutoff(self):
        self.assertTrue(main.is_qualifying_offer(offer(out_dep="2027-06-01T11:00:00")))

    def test_rejects_red_eye_departure(self):
        self.assertFalse(main.is_qualifying_offer(offer(back_dep="2027-06-30T23:15:00")))

    def test_rejects_empty_itinerary_segments(self):
        self.assertFalse(main.is_qualifying_offer(offer(out_segments_count=0)))


class ApiFailureTests(unittest.TestCase):
    @patch.dict(os.environ, {"AMADEUS_CLIENT_ID": "dummy", "AMADEUS_CLIENT_SECRET": "dummy"})
    @patch("main.requests.post")
    def test_amadeus_auth_failure_is_reported(self, post):
        response = Mock()
        response.ok = False
        response.status_code = 401
        post.return_value = response
        with self.assertRaisesRegex(main.FlightSearchError, "authentication failed"):
            main.get_amadeus_token()

    @patch("main.requests.get")
    def test_flight_search_http_failure_is_reported(self, get):
        response = Mock()
        response.ok = False
        response.status_code = 503
        response.text = "service unavailable"
        get.return_value = response
        with self.assertRaisesRegex(main.FlightSearchError, "503"):
            main.search_offers("fake-test-token")

    @patch("main.requests.get")
    def test_flight_search_rejects_unexpected_payload(self, get):
        response = Mock()
        response.ok = True
        response.json.return_value = {"unexpected": []}
        get.return_value = response
        with self.assertRaisesRegex(main.FlightSearchError, "data field"):
            main.search_offers("fake-test-token")


class TelegramTests(unittest.TestCase):
    @patch.dict(os.environ, {"BOT_TOKEN": "dummy-test-token", "CHAT_ID": "12345"})
    @patch("main.requests.post")
    def test_successful_telegram_response(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        post.return_value = response
        main.telegram_send("test message")
        post.assert_called_once()

    @patch.dict(os.environ, {"BOT_TOKEN": "dummy-test-token", "CHAT_ID": "12345"})
    @patch("main.requests.post")
    def test_telegram_api_rejection_is_reported(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {"ok": False, "description": "chat not found"}
        post.return_value = response
        with self.assertRaisesRegex(main.FlightSearchError, "rejected"):
            main.telegram_send("test message")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_telegram_secret_is_reported(self):
        with self.assertRaisesRegex(main.FlightSearchError, "BOT_TOKEN"):
            main.telegram_send("test message")


if __name__ == "__main__":
    unittest.main(verbosity=2)

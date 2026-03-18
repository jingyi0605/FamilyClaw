import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.modules.weather.providers import (
    MetNorwayAdapter,
    OpenWeatherAdapter,
    WeatherApiAdapter,
    WeatherProviderError,
)
from app.modules.weather.schemas import WeatherCoordinate, WeatherProviderConfig


def _build_met_payload() -> dict:
    return {
        "properties": {
            "meta": {
                "updated_at": "2026-03-18T02:15:00Z",
            },
            "timeseries": [
                {
                    "time": "2026-03-18T02:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_pressure_at_sea_level": 1012.4,
                                "air_temperature": 21.3,
                                "cloud_area_fraction": 12.0,
                                "relative_humidity": 61.0,
                                "wind_from_direction": 130.0,
                                "wind_speed": 3.6,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "partlycloudy_day"},
                            "details": {"precipitation_amount": 0.4},
                        },
                        "next_6_hours": {
                            "summary": {"symbol_code": "cloudy"},
                            "details": {"precipitation_amount": 1.5},
                        },
                    },
                },
                {
                    "time": "2026-03-18T03:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 22.0}}},
                },
                {
                    "time": "2026-03-18T04:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 24.6}}},
                },
                {
                    "time": "2026-03-18T05:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 25.1}}},
                },
                {
                    "time": "2026-03-18T06:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 23.8}}},
                },
                {
                    "time": "2026-03-18T07:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 22.4}}},
                },
            ],
        }
    }


def _build_openweather_payload() -> dict:
    return {
        "lat": 39.9042,
        "lon": 116.4074,
        "timezone": "Asia/Shanghai",
        "current": {
            "dt": 1710728100,
            "temp": 24.5,
            "humidity": 57,
            "wind_speed": 4.4,
            "wind_deg": 188,
            "pressure": 1008,
            "clouds": 60,
            "weather": [
                {
                    "id": 500,
                    "main": "Rain",
                    "description": "light rain",
                }
            ],
            "rain": {"1h": 0.7},
        },
        "hourly": [
            {"dt": 1710728100, "temp": 24.5, "weather": [{"id": 500, "main": "Rain", "description": "light rain"}], "rain": {"1h": 0.7}},
            {"dt": 1710731700, "temp": 23.8, "weather": [{"id": 500, "main": "Rain", "description": "light rain"}]},
            {"dt": 1710735300, "temp": 23.2, "weather": [{"id": 500, "main": "Rain", "description": "light rain"}]},
            {"dt": 1710738900, "temp": 22.4, "weather": [{"id": 804, "main": "Clouds", "description": "overcast clouds"}]},
            {"dt": 1710742500, "temp": 21.8, "weather": [{"id": 804, "main": "Clouds", "description": "overcast clouds"}]},
            {"dt": 1710746100, "temp": 21.1, "weather": [{"id": 500, "main": "Rain", "description": "light rain"}]},
        ],
    }


def _build_weatherapi_payload() -> dict:
    return {
        "location": {
            "name": "Beijing",
            "localtime_epoch": 1710728100,
        },
        "current": {
            "last_updated_epoch": 1710728100,
            "temp_c": 19.6,
            "humidity": 71,
            "wind_kph": 12.6,
            "wind_degree": 45,
            "pressure_mb": 1015.0,
            "cloud": 82,
            "precip_mm": 0.1,
            "condition": {
                "text": "Light drizzle",
                "code": 1150,
            },
        },
        "forecast": {
            "forecastday": [
                {
                    "hour": [
                        {
                            "time_epoch": 1710728100,
                            "temp_c": 19.6,
                            "precip_mm": 0.1,
                            "condition": {"text": "Light drizzle", "code": 1150},
                        },
                        {
                            "time_epoch": 1710731700,
                            "temp_c": 20.1,
                            "precip_mm": 0.4,
                            "condition": {"text": "Patchy rain nearby", "code": 1063},
                        },
                        {
                            "time_epoch": 1710735300,
                            "temp_c": 21.3,
                            "precip_mm": 0.2,
                            "condition": {"text": "Patchy rain nearby", "code": 1063},
                        },
                        {
                            "time_epoch": 1710738900,
                            "temp_c": 22.0,
                            "precip_mm": 0.0,
                            "condition": {"text": "Cloudy", "code": 1006},
                        },
                        {
                            "time_epoch": 1710742500,
                            "temp_c": 23.1,
                            "precip_mm": 0.0,
                            "condition": {"text": "Cloudy", "code": 1006},
                        },
                        {
                            "time_epoch": 1710746100,
                            "temp_c": 22.4,
                            "precip_mm": 0.0,
                            "condition": {"text": "Cloudy", "code": 1006},
                        },
                    ]
                }
            ]
        },
    }


class WeatherProviderTests(unittest.TestCase):
    def test_met_norway_adapter_maps_snapshot(self) -> None:
        adapter = MetNorwayAdapter()
        response = MagicMock()
        response.json.return_value = _build_met_payload()
        response.raise_for_status.return_value = None

        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = None

        with patch("app.modules.weather.providers.httpx.Client", return_value=client):
            snapshot = adapter.fetch_weather(
                coordinate=WeatherCoordinate(latitude=39.9042, longitude=116.4074),
                config=WeatherProviderConfig(),
            )

        self.assertEqual("met_norway", snapshot.source_type)
        self.assertEqual("partlycloudy_day", snapshot.condition_code)
        self.assertEqual("局部多云", snapshot.condition_text)
        self.assertEqual(21.3, snapshot.temperature)
        self.assertEqual(61.0, snapshot.humidity)
        self.assertEqual(3.6, snapshot.wind_speed)
        self.assertEqual(130.0, snapshot.wind_direction)
        self.assertEqual(1012.4, snapshot.pressure)
        self.assertEqual(12.0, snapshot.cloud_cover)
        self.assertEqual(0.4, snapshot.precipitation_next_1h)
        assert snapshot.forecast_6h is not None
        self.assertEqual("cloudy", snapshot.forecast_6h.condition_code)
        self.assertEqual("多云", snapshot.forecast_6h.condition_text)
        self.assertEqual(21.3, snapshot.forecast_6h.min_temperature)
        self.assertEqual(25.1, snapshot.forecast_6h.max_temperature)
        self.assertEqual("2026-03-18T02:15:00Z", snapshot.updated_at)

    def test_met_norway_adapter_surfaces_timeout(self) -> None:
        client = MagicMock()
        client.get.side_effect = httpx.TimeoutException("boom")
        client.__enter__.return_value = client
        client.__exit__.return_value = None

        with patch("app.modules.weather.providers.httpx.Client", return_value=client):
            with self.assertRaises(WeatherProviderError) as ctx:
                MetNorwayAdapter().fetch_weather(
                    coordinate=WeatherCoordinate(latitude=39.9042, longitude=116.4074),
                    config=WeatherProviderConfig(),
                )

        self.assertEqual("weather_provider_timeout", ctx.exception.error_code)
        self.assertTrue(ctx.exception.retryable)

    def test_openweather_adapter_maps_snapshot(self) -> None:
        adapter = OpenWeatherAdapter()
        response = MagicMock()
        response.json.return_value = _build_openweather_payload()
        response.raise_for_status.return_value = None

        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = None

        with patch("app.modules.weather.providers.httpx.Client", return_value=client):
            snapshot = adapter.fetch_weather(
                coordinate=WeatherCoordinate(latitude=39.9042, longitude=116.4074),
                config=WeatherProviderConfig(provider_type="openweather", openweather_api_key="demo-key"),
            )

        self.assertEqual("openweather", snapshot.source_type)
        self.assertEqual("owm_500", snapshot.condition_code)
        self.assertEqual("light rain", snapshot.condition_text)
        self.assertEqual(24.5, snapshot.temperature)
        self.assertEqual(57.0, snapshot.humidity)
        self.assertEqual(4.4, snapshot.wind_speed)
        self.assertEqual(188.0, snapshot.wind_direction)
        self.assertEqual(1008.0, snapshot.pressure)
        self.assertEqual(60.0, snapshot.cloud_cover)
        self.assertEqual(0.7, snapshot.precipitation_next_1h)
        assert snapshot.forecast_6h is not None
        self.assertEqual("owm_500", snapshot.forecast_6h.condition_code)
        self.assertEqual("light rain", snapshot.forecast_6h.condition_text)
        self.assertEqual(21.1, snapshot.forecast_6h.min_temperature)
        self.assertEqual(24.5, snapshot.forecast_6h.max_temperature)
        self.assertEqual("2024-03-18T02:15:00Z", snapshot.updated_at)

    def test_openweather_adapter_surfaces_http_401(self) -> None:
        request = httpx.Request("GET", "https://api.openweathermap.org/data/3.0/onecall")
        response = httpx.Response(401, request=request, text='{"message":"Invalid API key"}')
        mocked_response = MagicMock()
        mocked_response.text = response.text
        mocked_response.status_code = response.status_code

        def _raise_for_status() -> None:
            raise httpx.HTTPStatusError("boom", request=request, response=response)

        mocked_response.raise_for_status.side_effect = _raise_for_status

        client = MagicMock()
        client.get.return_value = mocked_response
        client.__enter__.return_value = client
        client.__exit__.return_value = None

        with patch("app.modules.weather.providers.httpx.Client", return_value=client):
            with self.assertRaises(WeatherProviderError) as ctx:
                OpenWeatherAdapter().fetch_weather(
                    coordinate=WeatherCoordinate(latitude=39.9042, longitude=116.4074),
                    config=WeatherProviderConfig(provider_type="openweather", openweather_api_key="bad-key"),
                )

        self.assertEqual("weather_provider_http_error", ctx.exception.error_code)
        self.assertFalse(ctx.exception.retryable)
        self.assertIn("HTTP 401", ctx.exception.detail)

    def test_weatherapi_adapter_maps_snapshot(self) -> None:
        adapter = WeatherApiAdapter()
        response = MagicMock()
        response.json.return_value = _build_weatherapi_payload()
        response.raise_for_status.return_value = None

        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = None

        with patch("app.modules.weather.providers.httpx.Client", return_value=client):
            snapshot = adapter.fetch_weather(
                coordinate=WeatherCoordinate(latitude=39.9042, longitude=116.4074),
                config=WeatherProviderConfig(provider_type="weatherapi", weatherapi_api_key="demo-key"),
            )

        self.assertEqual("weatherapi", snapshot.source_type)
        self.assertEqual("weatherapi_1150", snapshot.condition_code)
        self.assertEqual("Light drizzle", snapshot.condition_text)
        self.assertEqual(19.6, snapshot.temperature)
        self.assertEqual(71.0, snapshot.humidity)
        self.assertAlmostEqual(3.5, snapshot.wind_speed, places=1)
        self.assertEqual(45.0, snapshot.wind_direction)
        self.assertEqual(1015.0, snapshot.pressure)
        self.assertEqual(82.0, snapshot.cloud_cover)
        self.assertEqual(0.1, snapshot.precipitation_next_1h)
        assert snapshot.forecast_6h is not None
        self.assertEqual("weatherapi_1006", snapshot.forecast_6h.condition_code)
        self.assertEqual("Cloudy", snapshot.forecast_6h.condition_text)
        self.assertEqual(19.6, snapshot.forecast_6h.min_temperature)
        self.assertEqual(23.1, snapshot.forecast_6h.max_temperature)
        self.assertEqual("2024-03-18T02:15:00Z", snapshot.updated_at)


if __name__ == "__main__":
    unittest.main()

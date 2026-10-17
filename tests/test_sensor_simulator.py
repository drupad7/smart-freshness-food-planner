
from datetime import datetime

from sensor_simulator import generate_reading


def test_reading_contains_required_fields():
    reading = generate_reading()

    assert "device_id" in reading
    assert "timestamp" in reading
    assert "temperature" in reading
    assert "humidity" in reading
    assert "gas_raw" in reading


def test_sensor_values_are_in_expected_ranges():
    reading = generate_reading()

    assert 20.0 <= reading["temperature"] <= 30.0
    assert 40.0 <= reading["humidity"] <= 80.0
    assert 200 <= reading["gas_raw"] <= 600


def test_timestamp_is_valid():
    reading = generate_reading()

    timestamp = datetime.fromisoformat(reading["timestamp"])
    assert timestamp.tzinfo is not None


def test_device_id_is_correct():
    reading = generate_reading()

    assert reading["device_id"] == "freshness_box_01"

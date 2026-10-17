
from freshness_analyzer import analyze_freshness


def sample_reading(temperature=25, humidity=60, gas_raw=300):
    return {
        "device_id": "freshness_box_01",
        "timestamp": "2026-10-18T10:00:00+00:00",
        "temperature": temperature,
        "humidity": humidity,
        "gas_raw": gas_raw,
    }


def test_fresh_reading():
    result = analyze_freshness(sample_reading())
    assert result["freshness_status"] == "Fresh"


def test_use_soon_temperature():
    result = analyze_freshness(sample_reading(temperature=28))
    assert result["freshness_status"] == "Use Soon"


def test_possible_deterioration_temperature():
    result = analyze_freshness(sample_reading(temperature=30))
    assert result["freshness_status"] == "Possible Deterioration"


def test_use_soon_humidity():
    result = analyze_freshness(sample_reading(humidity=75))
    assert result["freshness_status"] == "Use Soon"


def test_possible_deterioration_gas():
    result = analyze_freshness(sample_reading(gas_raw=550))
    assert result["freshness_status"] == "Possible Deterioration"

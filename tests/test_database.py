
import pytest

from database import init_db, save_reading, get_readings


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_sensor.db"
    init_db(db_path)
    return db_path


def sample_reading():
    return {
        "device_id": "freshness_box_01",
        "timestamp": "2026-10-18T00:00:00+00:00",
        "temperature": 25.4,
        "humidity": 68.0,
        "gas_raw": 415,
    }


def test_database_initializes(test_db):
    assert test_db.exists()


def test_save_and_retrieve_reading(test_db):
    reading = sample_reading()

    reading_id = save_reading(reading, test_db)
    results = get_readings(db_path=test_db)

    assert reading_id == 1
    assert len(results) == 1
    assert results[0]["device_id"] == reading["device_id"]
    assert results[0]["temperature"] == reading["temperature"]


def test_newest_reading_comes_first(test_db):
    first = sample_reading()
    second = sample_reading()
    second["temperature"] = 28.5

    save_reading(first, test_db)
    save_reading(second, test_db)

    results = get_readings(db_path=test_db)

    assert results[0]["temperature"] == 28.5
    assert results[1]["temperature"] == 25.4


def test_invalid_limit_is_rejected(test_db):
    with pytest.raises(ValueError):
        get_readings(limit=0, db_path=test_db)

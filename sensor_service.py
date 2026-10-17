
from database import save_reading
from sensor_simulator import generate_reading


def collect_and_save():
    """Generate a simulated reading and save it to SQLite."""
    reading = generate_reading()
    reading_id = save_reading(reading)

    print("Sensor reading saved successfully!")
    print(f"Database ID: {reading_id}")

    for key, value in reading.items():
        print(f"{key}: {value}")

    return reading_id


if __name__ == "__main__":
    collect_and_save()

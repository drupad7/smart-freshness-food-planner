
import random
from datetime import datetime, timezone


def generate_reading():
    """Generate simulated environmental sensor readings."""
    return {
        "device_id": "freshness_box_01",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": round(random.uniform(20.0, 30.0), 2),
        "humidity": round(random.uniform(40.0, 80.0), 2),
        "gas_raw": random.randint(200, 600),
    }


if __name__ == "__main__":
    reading = generate_reading()

    print("Smart Freshness System - Sensor Simulator")
    print("-----------------------------------------")

    for key, value in reading.items():
        print(f"{key}: {value}")

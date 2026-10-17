
def analyze_freshness(reading):
    """Estimate freshness status from environmental readings."""

    temperature = reading["temperature"]
    humidity = reading["humidity"]
    gas_raw = reading["gas_raw"]

    if temperature >= 30 or humidity >= 80 or gas_raw >= 550:
        status = "Possible Deterioration"
    elif temperature >= 27 or humidity >= 70 or gas_raw >= 450:
        status = "Use Soon"
    else:
        status = "Fresh"

    return {
        "device_id": reading["device_id"],
        "timestamp": reading["timestamp"],
        "freshness_status": status,
        "temperature": temperature,
        "humidity": humidity,
        "gas_raw": gas_raw,
    }


if __name__ == "__main__":
    from sensor_simulator import generate_reading

    sample = generate_reading()
    result = analyze_freshness(sample)

    print("Freshness Analysis")
    print("------------------")
    for key, value in result.items():
        print(f"{key}: {value}")

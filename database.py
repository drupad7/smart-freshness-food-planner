
import sqlite3
from contextlib import closing
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "sensor_readings.db"


def init_db(db_path=None):
    """Create the sensor readings table if it doesn't exist."""
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    gas_raw INTEGER NOT NULL
                )
            """)


def save_reading(reading, db_path=None):
    """Save one sensor reading and return its database ID."""
    path = Path(db_path) if db_path is not None else DB_PATH
    init_db(path)

    with closing(sqlite3.connect(path)) as connection:
        with connection:
            cursor = connection.execute("""
                INSERT INTO sensor_readings (
                    device_id, timestamp, temperature,
                    humidity, gas_raw
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                reading["device_id"],
                reading["timestamp"],
                reading["temperature"],
                reading["humidity"],
                reading["gas_raw"],
            ))
            return cursor.lastrowid


def get_readings(limit=100, db_path=None):
    """Return the most recent readings, newest first."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    path = Path(db_path) if db_path is not None else DB_PATH
    init_db(path)

    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT * FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

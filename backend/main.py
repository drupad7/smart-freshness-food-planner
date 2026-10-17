
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_readings, save_reading

app = FastAPI(
    title="Smart Freshness API",
    description="API for the Smart Freshness & Food Planning System",
    version="1.0.0",
)


class SensorReading(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    temperature: float = Field(ge=-40, le=100)
    humidity: float = Field(ge=0, le=100)
    gas_raw: int = Field(ge=0)


@app.get("/")
def home():
    return {
        "message": "Smart Freshness API is running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/readings", status_code=201)
def create_reading(reading: SensorReading):
    try:
        reading_id = save_reading(reading.model_dump(mode="json"))
        return {
            "message": "Reading saved successfully",
            "id": reading_id,
            "reading": reading.model_dump(mode="json"),
        }
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to save sensor reading",
        ) from exc


@app.get("/readings")
def list_readings(
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        readings = get_readings(limit=limit)
        return {
            "count": len(readings),
            "readings": readings,
        }
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve sensor readings",
        ) from exc

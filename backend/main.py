import base64
from datetime import datetime
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from database import get_readings, save_reading
from food_detector import detect_food

app = FastAPI(
    title="Smart Freshness API",
    description="API for the Smart Freshness Monitoring System",
    version="1.1.0",
)

@app.get("/camera")
def mobile_camera():
    camera_page = Path(__file__).resolve().parent.parent / "static" / "camera.html"

    if not camera_page.is_file():
        raise HTTPException(
            status_code=404,
            detail="Camera webpage not found",
        )

    return FileResponse(camera_page)


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


@app.post("/detect-food")
async def detect_food_from_image(
    file: UploadFile = File(...),
):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WebP image.",
        )

    try:
        image_bytes = await file.read(8 * 1024 * 1024 + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded image is empty.",
            )

        if len(image_bytes) > 8 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Image size must not exceed 8 MB.",
            )

        with Image.open(BytesIO(image_bytes)) as source_image:
            source_image.verify()

        with Image.open(BytesIO(image_bytes)) as source_image:
            image = source_image.convert("RGB")

    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image.",
        ) from exc
    finally:
        await file.close()

    try:
        detections, annotated_image = detect_food(image)

        image_buffer = BytesIO()
        annotated_image.save(image_buffer, format="JPEG")
        annotated_base64 = base64.b64encode(
            image_buffer.getvalue()
        ).decode("ascii")

        return {
            "detection_count": len(detections),
            "detections": detections,
            "annotated_image": annotated_base64,
            "message": (
                "Food detection completed."
                if detections
                else "No supported food items detected."
            ),
            "note": (
                "Object detection identifies supported food categories; "
                "it does not determine freshness or food safety."
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Food detection failed on the server.",
        ) from exc
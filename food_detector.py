
from time import perf_counter

from ultralytics import YOLO
from PIL import Image

_model = None

FOOD_CLASSES = {
    "apple",
    "banana",
    "orange",
    "broccoli",
    "carrot",
    "sandwich",
    "pizza",
    "cake",
    "donut",
}


def detect_food(image: Image.Image):
    """Detect supported food objects and measure processing time."""

    global _model

    start = perf_counter()

    if _model is None:
        _model = YOLO("yolo11n.pt")

    model_load_time = perf_counter() - start

    inference_start = perf_counter()
    results = _model.predict(
        image,
        imgsz=256,
        verbose=False,
	device="cpu",
    )
    inference_time = perf_counter() - inference_start

    annotation_start = perf_counter()
    detections = []

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            label = result.names[class_id]

            if label in FOOD_CLASSES:
                detections.append({
                    "food": label,
                    "confidence": round(float(box.conf[0]), 3),
                    "box": [
                        round(float(value), 1)
                        for value in box.xyxy[0].tolist()
                    ],
                })

    annotated_image = results[0].plot()
    annotated_image = Image.fromarray(annotated_image[:, :, ::-1])

    annotation_time = perf_counter() - annotation_start
    total_time = perf_counter() - start

    print(
        "[FOOD DETECTION TIMING] "
        f"model_load={model_load_time:.2f}s, "
        f"inference={inference_time:.2f}s, "
        f"annotation={annotation_time:.2f}s, "
        f"total={total_time:.2f}s"
    )

    return detections, annotated_image
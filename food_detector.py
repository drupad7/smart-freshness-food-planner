
from ultralytics import YOLO
from PIL import Image

# Load a small pretrained object-detection model.
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
    """Detect supported food objects in a PIL image."""

    global _model

    if _model is None:
        _model = YOLO("yolo11n.pt")

    results = _model.predict(image, verbose=False)
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
    return detections, Image.fromarray(annotated_image[:, :, ::-1])


import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from time import perf_counter

from ultralytics import YOLO
from PIL import Image

freshness_model = None

FRESHNESS_CLASSES = [
    "freshapples",
    "freshbanana",
    "freshoranges",
    "rottenapples",
    "rottenbanana",
    "rottenoranges",
]

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
        imgsz=320,
        conf=0.45,
        iou=0.5,
        max_det=10,
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

         if label not in FOOD_CLASSES:
             continue

         x1, y1, x2, y2 = [
             int(value) for value in box.xyxy[0].tolist()
         ]

         x1 = max(0, x1)
         y1 = max(0, y1)
         x2 = min(image.width, x2)
         y2 = min(image.height, y2)

         detection = {
             "food": label,
             "confidence": round(float(box.conf[0]), 3),
             "box": [x1, y1, x2, y2],
             "freshness": None,
         }

         if label in ("apple", "banana", "orange") and x2 > x1 and y2 > y1:
             crop = image.crop((x1, y1, x2, y2))
             detection["freshness"] = predict_freshness(crop, label)
 
         detections.append(detection)

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

def predict_freshness(image, expected_fruit):
    global freshness_model

    if freshness_model is None:
        freshness_model = tf.keras.models.load_model(
            "fresho_freshness.keras",
            custom_objects={
                "preprocess_input": preprocess_input
            },
            compile=False
        )

    image = image.convert("RGB").resize((224, 224))

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)

    predictions = freshness_model.predict(
        image_array,
        verbose=0
    )[0]

    fruit_indices = {
        "apple": (0, 3),
        "banana": (1, 4),
        "orange": (2, 5),
    }

    if expected_fruit not in fruit_indices:
        return None

    fresh_index, rotten_index = fruit_indices[expected_fruit]

    fresh_score = float(predictions[fresh_index])
    rotten_score = float(predictions[rotten_index])

    total = fresh_score + rotten_score

    if total == 0:
        return None

    if fresh_score >= rotten_score:
        status = "Fresh"
        confidence = fresh_score / total
    else:
        status = "Rotten"
        confidence = rotten_score / total

    return {
        "freshness": status,
        "confidence": round(confidence, 3),
    }
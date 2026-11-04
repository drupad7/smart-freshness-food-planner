from PIL import Image
from food_detector import detect_food

image = Image.open("test_food.jpg").convert("RGB")

detections, annotated_image = detect_food(image)

print("\nFRESHO DETECTION RESULTS")

for detection in detections:
    print(detection)

annotated_image.show()
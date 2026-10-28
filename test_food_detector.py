
from PIL import Image
from food_detector import detect_food

image = Image.open("test_food.jpg").convert("RGB")
detections, annotated_image = detect_food(image)

print("Detected food items:")
for item in detections:
    print(item)

annotated_image.save("food_detection_result.jpg")
print("Saved result to food_detection_result.jpg")

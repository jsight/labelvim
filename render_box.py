
from PIL import Image, ImageDraw, ImageFont
import os

def render_box_on_image(image_path, detections, output_path):
    # Load the image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    
    # Try to get a font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Process each detection
    for detection in detections:
        label = detection["label"]
        confidence = detection["confidence"]
        box = detection["box_2d"]  # [ymin, xmin, ymax, xmax]
        
        # Draw rectangle
        draw.rectangle(
            [(box[1], box[0]), (box[3], box[2])],  # (xmin, ymin), (xmax, ymax)
            outline="red",
            width=2
        )
        
        # Prepare label text
        text = f"{label} ({confidence:.2f})"
        
        # Calculate text position (above the box)
        text_position = (box[1], box[0] - 25 if box[0] >= 25 else box[0])
        
        # Draw text background
        text_bbox = draw.textbbox(text_position, text, font=font)
        draw.rectangle(text_bbox, fill="red")
        
        # Draw text
        draw.text(text_position, text, fill="white", font=font)
    
    # Save the output image
    image.save(output_path)

# Example usage
if __name__ == "__main__":
    detections = [
        {
            "label": "tesla_screen",
            "confidence": 0.98,
            "box_2d": [80, 85, 825, 689]
        }
    ]
    input_image = "carscrape/2020_Model_Y_1_10.jpg"  # Replace with your input image path
    output_image = "output_with_box.jpg"
    
    if os.path.exists(input_image):
        render_box_on_image(input_image, detections, output_image)
        print(f"Image saved as {output_image}")
    else:
        print(f"Input image {input_image} not found")

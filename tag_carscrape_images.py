token="AIzaSyBmdJQ8Elt_0Butpu1v2uv_K2DQ1taDxHI"

prompt="""
Look carefully at this image and detect the tesla screen, even if only partially visible. Return no objects if the screen isn't
clearly there.

IMPORTANT: Focus on finding the screen
Valid object classes: tesla_screen

For each detected object, provide:
- "label": exact class name from the list above
- "confidence": how certain you are (0.0 to 1.0)  
- "box_2d": bounding box [ymin, xmin, ymax, xmax] normalized 0-1000

Detect everything you can see that matches the valid classes. Don't be conservative - include objects even if you're only moderately confident.

Return as JSON array:
[
  {
    "label": "tesla_screen",
    "confidence": 0.95,
    "box_2d": [100, 200, 300, 400],
  },
  {
    "label": "tesla_screen", 
    "confidence": 0.80,
    "box_2d": [50, 150, 250, 350],
  }
]
"""

from google import genai
from google.genai import types

client = genai.Client(api_key=token)

with open('carscrape/2020_Model_Y_1_10.jpg', 'rb') as f:
      image_bytes = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
      types.Part.from_bytes(
        data=image_bytes,
        mime_type='image/jpeg',
      ),
      prompt
    ]
)

print(response.text)


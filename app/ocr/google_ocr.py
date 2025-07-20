import io

# Ensure the service account path is provided via ``GOOGLE_CREDENTIALS_PATH``
import os

from google.cloud import vision
from google.oauth2 import service_account

GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

if not GOOGLE_CREDENTIALS_PATH:
    raise RuntimeError("GOOGLE_CREDENTIALS_PATH not set in environment")

credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_CREDENTIALS_PATH
)
client = vision.ImageAnnotatorClient(credentials=credentials)


def extract_text_from_image_google(file_bytes: bytes) -> str:
    image = vision.Image(content=file_bytes)
    response = client.text_detection(image=image)
    annotations = response.text_annotations
    if not annotations:
        return ""
    return annotations[0].description  # Full extracted text

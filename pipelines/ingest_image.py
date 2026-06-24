import os
import base64
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image

from config import SUPPORTED_IMAGE_FORMATS, GPT_VISION_MODEL
from pipelines.utils import ensure_dir, append_log

load_dotenv()

client = OpenAI()
IMAGES_DIR = "raw/images"


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_mime_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def _get_image_size(path: str) -> tuple:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return (0, 0)


def ingest_image(image_path: str) -> None:
    image_name = Path(image_path).name
    ext = Path(image_path).suffix.lower()

    if ext not in SUPPORTED_IMAGE_FORMATS:
        print(f"[SKIP] Unsupported image format: {image_name}")
        return

    print(f"[IMAGE] Processing {image_name}...")

    width, height = _get_image_size(image_path)
    encoded = encode_image(image_path)
    mime_type = _get_mime_type(image_path)

    prompt = """You are analyzing an image for a knowledge wiki. Provide:

1. **Description**: A detailed description of what is shown in the image.
2. **OCR Text**: Any visible text extracted from the image.
3. **Relevance Classification**: Classify as exactly one of:
   - **Evidence-bearing**: Contains data, evidence, or information critical to understanding the subject
   - **Illustrative**: Helps illustrate a concept but not strictly necessary
   - **Decorative**: Purely decorative with no informational value
   - **Irrelevant**: Not related to the subject matter

Format your response as structured Markdown."""

    try:
        response = client.responses.create(
            model=GPT_VISION_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded}",
                        },
                    ],
                }
            ],
        )

        caption_text = response.output_text

        out_dir = "processed/images"
        ensure_dir(out_dir)

        safe_name = Path(image_name).stem
        out_file = f"{out_dir}/{safe_name}.caption.md"

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"# Image: {image_name}\n\n")
            if width and height:
                f.write(f"**Dimensions:** {width}x{height}\n\n")
            f.write(caption_text)

        print(f"[IMAGE] Saved caption: {out_file}")
        append_log(f"Ingested image: {image_name}")

    except Exception as e:
        print(f"[ERROR] Failed to process image {image_name}: {e}")
        append_log(f"ERROR: Failed to process image {image_name}: {e}")


def process_images() -> None:
    images_dir = Path(IMAGES_DIR)

    if not images_dir.exists():
        print(f"[WARN] Images directory not found: {IMAGES_DIR}")
        return

    files_found = False

    for filename in os.listdir(str(images_dir)):
        path = str(images_dir / filename)
        ext = Path(path).suffix.lower()

        if ext in SUPPORTED_IMAGE_FORMATS:
            files_found = True
            ingest_image(path)
        else:
            print(f"[SKIP] Unknown image format: {filename}")

    if not files_found:
        print(f"[INFO] No images found in {IMAGES_DIR}")


if __name__ == "__main__":
    process_images()

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DOCUMENTS_DIR = "raw/documents"
IMAGES_DIR = "raw/images"
VIDEOS_DIR = "raw/videos"

PROCESSED_DIR = "processed"
PROCESSED_DOCUMENTS_DIR = "processed/documents"
PROCESSED_IMAGES_DIR = "processed/images"
PROCESSED_VIDEOS_DIR = "processed/videos"

WIKI_DIR = "wiki"
WIKI_SOURCES_DIR = "wiki/sources"
WIKI_CONCEPTS_DIR = "wiki/concepts"
WIKI_ENTITIES_DIR = "wiki/entities"
WIKI_IMAGES_DIR = "wiki/images"

GPT_VISION_MODEL = "gpt-4o"
GPT_MINI_MODEL = "gpt-4.1-mini"
WHISPER_MODEL = "whisper-1"

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
SUPPORTED_VIDEO_FORMATS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}

from functools import lru_cache
from pathlib import Path
import cv2
from ultralytics import YOLO
from .config import YOLO_MODEL, MODEL_DIR

@lru_cache(maxsize=2)
def load_yolo(model_name: str = YOLO_MODEL):
    candidate = Path(model_name)
    if not candidate.is_absolute():
        local_candidate = MODEL_DIR / candidate
        if local_candidate.exists():
            model_name = str(local_candidate)
    return YOLO(model_name)

@lru_cache(maxsize=1)
def load_face_detector():
    # OpenCV ships this Haar cascade with the cv2 package.
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        raise RuntimeError("Could not load OpenCV face detector cascade")
    return detector

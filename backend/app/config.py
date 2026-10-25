from pathlib import Path
import os

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

def _resolve_data_dir() -> Path:
    raw = os.getenv("DATA_DIR", "../data")
    p = Path(raw)
    return (BACKEND_DIR / p).resolve() if not p.is_absolute() else p.resolve()

DATA_DIR = _resolve_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
REPORT_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "highway_ai.sqlite3"

MODEL_DIR = Path(os.getenv("MODEL_DIR", str(PROJECT_DIR / "models"))).resolve()
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolo11n.pt")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
PROCESS_EVERY_N_FRAMES = max(1, int(os.getenv("PROCESS_EVERY_N_FRAMES", "2")))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))

for folder in (UPLOAD_DIR, PROCESSED_DIR, SNAPSHOT_DIR, REPORT_DIR, MODEL_DIR):
    folder.mkdir(parents=True, exist_ok=True)

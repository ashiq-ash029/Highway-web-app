import csv
import json
import time
import threading
from pathlib import Path
import cv2
import numpy as np
from .config import (
    UPLOAD_DIR, PROCESSED_DIR, SNAPSHOT_DIR, REPORT_DIR,
    PROCESS_EVERY_N_FRAMES, CONFIDENCE_THRESHOLD
)
from .database import get_conn
from .detector import load_yolo, load_face_detector

# COCO class IDs used by common YOLO models: person, bicycle, car, motorcycle,
# bus, and truck. Other classes are intentionally omitted for this highway MVP.
ROAD_CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
_lock = threading.Lock()

def run_job(job_id: int, video_id: int, video_path: str, request_options: dict):
    # Keep processing jobs sequential on this local prototype to reduce RAM use.
    with _lock:
        _process(job_id, video_id, video_path, request_options)

def _process(job_id: int, video_id: int, video_path: str, options: dict):
    started = time.perf_counter()
    source = Path(video_path)
    output_path = PROCESSED_DIR / f"video_{video_id}_job_{job_id}.mp4"
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        _set_failed(job_id, video_id, "Could not open uploaded video")
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    every_n = max(1, int(options.get("every_n_frames") or PROCESS_EVERY_N_FRAMES))
    conf = float(options.get("confidence") if options.get("confidence") is not None else CONFIDENCE_THRESHOLD)
    detect_faces = bool(options.get("detect_faces", True))
    save_snapshots = bool(options.get("save_snapshots", True))

    # Prefer a broadly supported MP4V codec for a local Windows MVP.
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"),
        source_fps if source_fps > 0 else 25.0, (width, height)
    )
    if not writer.isOpened():
        cap.release()
        _set_failed(job_id, video_id, "Could not create output video; check codec and disk space")
        return

    try:
        model = load_yolo()
        face_detector = load_face_detector() if detect_faces else None
        frame_index = 0
        processed_frames = 0
        detections_total = {"person": 0, "bicycle": 0, "car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "face": 0}
        saved_snapshot_keys = set()
        metric_last = time.perf_counter()
        metric_frames = 0
        current_fps = 0.0
        records = []

        with get_conn() as conn:
            conn.execute(
                "UPDATE jobs SET status='processing', started_at=CURRENT_TIMESTAMP, total_frames=? WHERE id=?",
                (total_frames, job_id)
            )
            conn.execute("UPDATE videos SET status='processing' WHERE id=?", (video_id,))

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            should_infer = (frame_index % every_n == 0)
            timestamp = frame_index / source_fps if source_fps > 0 else 0.0

            if should_infer:
                result = model.predict(frame, conf=conf, verbose=False, device="cpu")[0]
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0].item())
                        if cls_id not in ROAD_CLASSES:
                            continue
                        category = ROAD_CLASSES[cls_id]
                        score = float(box.conf[0].item())
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(width, x2), min(height, y2)
                        detections_total[category] += 1
                        label = f"{category} {score:.2f}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 80), 2)
                        cv2.putText(frame, label, (x1, max(20, y1 - 7)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 220, 80), 2)
                        snap_path = None
                        key = ("object", category)
                        if save_snapshots and key not in saved_snapshot_keys and x2 > x1 and y2 > y1:
                            crop = frame[y1:y2, x1:x2]
                            if crop.size:
                                p = SNAPSHOT_DIR / f"video_{video_id}_{category}_sample.jpg"
                                cv2.imwrite(str(p), crop)
                                snap_path = str(p)
                                saved_snapshot_keys.add(key)
                        records.append((job_id, video_id, frame_index, timestamp, "object", category, score,
                                        x1, y1, x2, y2, snap_path))

                if face_detector is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                    for (fx, fy, fw, fh) in faces:
                        detections_total["face"] += 1
                        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (220, 100, 40), 2)
                        cv2.putText(frame, "face", (fx, max(20, fy - 7)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 100, 40), 2)
                        snap_path = None
                        key = ("face", "face")
                        if save_snapshots and key not in saved_snapshot_keys:
                            crop = frame[fy:fy+fh, fx:fx+fw]
                            if crop.size:
                                p = SNAPSHOT_DIR / f"video_{video_id}_face_sample.jpg"
                                cv2.imwrite(str(p), crop)
                                snap_path = str(p)
                                saved_snapshot_keys.add(key)
                        records.append((job_id, video_id, frame_index, timestamp, "face", "face", 1.0,
                                        fx, fy, fx + fw, fy + fh, snap_path))

                processed_frames += 1
                metric_frames += 1
                now = time.perf_counter()
                if now - metric_last >= 1.0:
                    current_fps = metric_frames / max(now - metric_last, 1e-6)
                    metric_frames = 0
                    metric_last = now
                    elapsed = now - started
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE jobs SET progress=?, processed_frames=?, processing_fps=?, elapsed_seconds=? WHERE id=?",
                            (min(99.0, (frame_index + 1) / max(total_frames, 1) * 100),
                             processed_frames, current_fps, elapsed, job_id)
                        )
                        conn.execute(
                            "INSERT INTO metrics(job_id, elapsed_seconds, processed_frames, fps) VALUES(?,?,?,?)",
                            (job_id, elapsed, processed_frames, current_fps)
                        )

            # The output keeps the original frame cadence; skipped frames are unannotated.
            writer.write(frame)
            frame_index += 1

        elapsed = max(time.perf_counter() - started, 1e-6)
        average_fps = processed_frames / elapsed
        cap.release()
        writer.release()

        with get_conn() as conn:
            if records:
                conn.executemany("""
                    INSERT INTO detections(job_id, video_id, frame_number, timestamp_seconds, category,
                    class_name, confidence, x1, y1, x2, y2, snapshot_path)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """, records)
            summary = {
                "frame_level_detections": detections_total,
                "frames_read": frame_index,
                "frames_analyzed": processed_frames,
                "source_fps": source_fps,
                "average_processing_fps": average_fps,
                "elapsed_seconds": elapsed,
                "note": "Counts are frame-level detections, not unique tracked objects."
            }
            conn.execute("""
                UPDATE jobs SET status='completed', progress=100, finished_at=CURRENT_TIMESTAMP,
                processed_frames=?, processing_fps=?, average_fps=?, elapsed_seconds=?,
                output_path=?, summary_json=? WHERE id=?
            """, (processed_frames, current_fps, average_fps, elapsed, str(output_path),
                  json.dumps(summary), job_id))
            conn.execute("""
                UPDATE videos SET status='completed', duration_seconds=?, width=?, height=?,
                source_fps=?, frame_count=? WHERE id=?
            """, (frame_index / source_fps if source_fps > 0 else 0, width, height, source_fps, total_frames, video_id))

        # Write a per-job CSV report.
        csv_path = REPORT_DIR / f"job_{job_id}_detections.csv"
        with get_conn() as conn:
            rows = conn.execute("SELECT frame_number,timestamp_seconds,category,class_name,confidence,x1,y1,x2,y2,snapshot_path FROM detections WHERE job_id=? ORDER BY frame_number", (job_id,)).fetchall()
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer_csv = csv.writer(f)
            writer_csv.writerow(["frame_number","timestamp_seconds","category","class_name","confidence","x1","y1","x2","y2","snapshot_path"])
            writer_csv.writerows([tuple(row) for row in rows])

    except Exception as exc:
        cap.release()
        writer.release()
        _set_failed(job_id, video_id, str(exc))
        raise

def _set_failed(job_id: int, video_id: int, message: str):
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status='failed', error=?, finished_at=CURRENT_TIMESTAMP WHERE id=?", (message[:1000], job_id))
        conn.execute("UPDATE videos SET status='failed', error=? WHERE id=?", (message[:1000], video_id))

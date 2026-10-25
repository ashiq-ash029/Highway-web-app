import json
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from .config import UPLOAD_DIR, PROCESSED_DIR, SNAPSHOT_DIR, REPORT_DIR, MAX_UPLOAD_MB
from .database import init_db, get_conn
from .processor import run_job
from .schemas import ProcessRequest

app = FastAPI(title="Highway AI Monitoring API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Highway AI Monitoring API", "storage": "local"}

@app.post("/api/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    original_name = Path(file.filename or "upload.mp4").name
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file extension. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    stored_name = f"upload_{__import__('uuid').uuid4().hex}{ext}"
    dest = UPLOAD_DIR / stored_name
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"File exceeds configured limit of {MAX_UPLOAD_MB} MB")
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    # Verify that OpenCV can open the file and obtain metadata.
    import cv2
    cap = cv2.VideoCapture(str(dest))
    if not cap.isOpened():
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file is not a readable video")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frames / fps if fps > 0 else 0
    cap.release()

    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO videos(original_name, stored_name, file_path, duration_seconds, width, height, source_fps, frame_count)
            VALUES(?,?,?,?,?,?,?,?)
        """, (original_name, stored_name, str(dest), duration, width, height, fps, frames))
        video_id = cur.lastrowid
    return {"id": video_id, "original_name": original_name, "size_bytes": size,
            "duration_seconds": duration, "width": width, "height": height,
            "source_fps": fps, "frame_count": frames, "status": "uploaded"}

@app.get("/api/videos")
def list_videos():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT v.*, (SELECT COUNT(*) FROM jobs j WHERE j.video_id=v.id) AS job_count
            FROM videos v ORDER BY v.id DESC
        """).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/videos/{video_id}")
def get_video(video_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Video not found")
    return dict(row)

@app.post("/api/videos/{video_id}/process")
def process_video(video_id: int, background_tasks: BackgroundTasks, options: ProcessRequest):
    with get_conn() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(404, "Video not found")
        active = conn.execute("SELECT id FROM jobs WHERE video_id=? AND status IN ('queued','processing')", (video_id,)).fetchone()
        if active:
            raise HTTPException(409, "This video already has an active processing job")
        cur = conn.execute("INSERT INTO jobs(video_id,status,total_frames) VALUES(?,?,?)",
                           (video_id, "queued", video["frame_count"] or 0))
        job_id = cur.lastrowid
    background_tasks.add_task(run_job, job_id, video_id, video["file_path"], options.model_dump())
    return {"job_id": job_id, "video_id": video_id, "status": "queued"}

@app.get("/api/jobs")
def list_jobs():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT j.*, v.original_name FROM jobs j JOIN videos v ON v.id=j.video_id
            ORDER BY j.id DESC LIMIT 100
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["summary"] = json.loads(d.pop("summary_json") or "{}")
        except json.JSONDecodeError:
            d["summary"] = {}
        result.append(d)
    return result

@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT j.*,v.original_name FROM jobs j JOIN videos v ON v.id=j.video_id WHERE j.id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    d = dict(row)
    d["summary"] = json.loads(d.pop("summary_json") or "{}")
    return d

@app.get("/api/videos/{video_id}/detections")
def get_detections(video_id: int, limit: int = Query(500, ge=1, le=5000)):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM detections WHERE video_id=? ORDER BY frame_number LIMIT ?
        """, (video_id, limit)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/videos/{video_id}/live-preview")
def live_preview(video_id: int, confidence: float = Query(0.35, ge=0.1, le=0.9), detect_faces: bool = Query(True)):
    """Stream AI-annotated frames from an uploaded video as an MJPEG response.

    This is a live preview endpoint; it does not replace the saved processing job.
    The browser displays the stream in an <img> element while inference runs.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT file_path FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Video not found")
    source_path = Path(row["file_path"])
    if not source_path.exists():
        raise HTTPException(404, "Uploaded video file is missing from local storage")

    def frames():
        import time
        import cv2
        from .detector import load_yolo, load_face_detector
        road_classes = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        cap = cv2.VideoCapture(str(source_path))
        if not cap.isOpened():
            return
        model = load_yolo()
        face_model = load_face_detector() if detect_faces else None
        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        frame_period = 1.0 / source_fps if source_fps > 0 else 1.0 / 20.0
        last_sent = time.perf_counter()
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                # Downscale very large frames to make CPU inference more practical.
                h, w = frame.shape[:2]
                if w > 960:
                    new_h = max(1, int(h * 960 / w))
                    frame = cv2.resize(frame, (960, new_h))
                result = model.predict(frame, conf=confidence, verbose=False, device="cpu")[0]
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0].item())
                        if cls_id not in road_classes:
                            continue
                        score = float(box.conf[0].item())
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        name = road_classes[cls_id]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 80), 2)
                        cv2.putText(frame, f"{name} {score:.2f}", (x1, max(20, y1 - 7)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 220, 80), 2)
                if face_model is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    for (fx, fy, fw, fh) in face_model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)):
                        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (220, 100, 40), 2)
                        cv2.putText(frame, "face", (fx, max(20, fy - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 100, 40), 2)
                now = time.perf_counter()
                live_fps = 1.0 / max(now - last_sent, 1e-6)
                last_sent = now
                cv2.putText(frame, f"LIVE AI PREVIEW | processing {live_fps:.1f} FPS", (16, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 255), 2)
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
                # Don't wait if inference itself is already slower than the source video.
                delay = frame_period - (time.perf_counter() - now)
                if delay > 0:
                    time.sleep(min(delay, 0.05))
        finally:
            cap.release()

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"})

@app.get("/api/videos/{video_id}/output")
def get_output(video_id: int):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT output_path FROM jobs WHERE video_id=? AND status='completed' AND output_path IS NOT NULL
            ORDER BY id DESC LIMIT 1
        """, (video_id,)).fetchone()
    if not row or not Path(row["output_path"]).is_file():
        raise HTTPException(404, "Processed video is not available yet")
    return FileResponse(row["output_path"], media_type="video/mp4", filename=Path(row["output_path"]).name)

@app.get("/api/videos/{video_id}/download-report")
def download_report(video_id: int):
    with get_conn() as conn:
        job = conn.execute("SELECT id FROM jobs WHERE video_id=? AND status='completed' ORDER BY id DESC LIMIT 1", (video_id,)).fetchone()
    if not job:
        raise HTTPException(404, "No completed report for this video")
    from .config import REPORT_DIR
    path = REPORT_DIR / f"job_{job['id']}_detections.csv"
    if not path.is_file():
        raise HTTPException(404, "Report not found")
    return FileResponse(path, media_type="text/csv", filename=path.name)

@app.delete("/api/videos/{video_id}")
def delete_video(video_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Video not found")
        jobs = conn.execute("SELECT output_path,id FROM jobs WHERE video_id=?", (video_id,)).fetchall()
        # Refuse to delete while processing, avoiding races with the worker.
        if conn.execute("SELECT 1 FROM jobs WHERE video_id=? AND status IN ('queued','processing')", (video_id,)).fetchone():
            raise HTTPException(409, "Cannot delete a video while it is processing")
        source_path = Path(row["file_path"])
        output_paths = [(Path(j["output_path"]) if j["output_path"] else None, j["id"]) for j in jobs]
        conn.execute("DELETE FROM videos WHERE id=?", (video_id,))
    source_path.unlink(missing_ok=True)
    for output, job_id in output_paths:
        if output:
            output.unlink(missing_ok=True)
        (REPORT_DIR / f"job_{job_id}_detections.csv").unlink(missing_ok=True)
    for p in SNAPSHOT_DIR.glob(f"video_{video_id}_*"):
        p.unlink(missing_ok=True)
    return {"deleted": True, "video_id": video_id}

@app.get("/api/faces")
def list_faces():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT d.*,v.original_name FROM detections d JOIN videos v ON v.id=d.video_id
            WHERE d.category='face' ORDER BY d.id DESC LIMIT 500
        """).fetchall()
    return [dict(r) for r in rows]

@app.delete("/api/faces/{detection_id}")
def delete_face(detection_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM detections WHERE id=? AND category='face'", (detection_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Face record not found")
        crop = Path(row["snapshot_path"]) if row["snapshot_path"] else None
        conn.execute("DELETE FROM detections WHERE id=?", (detection_id,))
    if crop:
        crop.unlink(missing_ok=True)
    return {"deleted": True, "id": detection_id}

@app.get("/api/metrics")
def metrics():
    with get_conn() as conn:
        videos = conn.execute("SELECT COUNT(*) n FROM videos").fetchone()["n"]
        completed = conn.execute("SELECT COUNT(*) n FROM jobs WHERE status='completed'").fetchone()["n"]
        jobs_processing = conn.execute("SELECT COUNT(*) n FROM jobs WHERE status IN ('queued','processing')").fetchone()["n"]
        totals = conn.execute("""
            SELECT class_name, COUNT(*) count FROM detections GROUP BY class_name
        """).fetchall()
        latest = conn.execute("""
            SELECT average_fps, elapsed_seconds FROM jobs WHERE status='completed' ORDER BY id DESC LIMIT 1
        """).fetchone()
    return {"videos_uploaded": videos, "jobs_completed": completed, "jobs_active": jobs_processing,
            "detections_by_class": {r["class_name"]: r["count"] for r in totals},
            "latest_average_fps": latest["average_fps"] if latest else 0,
            "latest_elapsed_seconds": latest["elapsed_seconds"] if latest else 0}

# Highway AI Video Monitoring System

Local-first Windows project for uploaded highway videos.

## Features
- Upload and store videos locally
- YOLO-based vehicle/person detection
- OpenCV face detection (detection only, not identity recognition)
- Annotated output video
- FPS and processing metrics
- SQLite metadata, detection summaries and job history
- Local snapshots and CSV export
- React + Vite dashboard
- Delete video records and related files

## Requirements
- Windows 10/11
- Python 3.10 or 3.11 recommended
- Node.js LTS
- VS Code

## Folder layout
```text
HighwayAI/
  backend/
    app/
      main.py
      config.py
      database.py
      schemas.py
      detector.py
      processor.py
    requirements.txt
    .env.example
  frontend/
    package.json
    index.html
    vite.config.ts
    tsconfig.json
    src/
      main.tsx
      App.tsx
      api.ts
      styles.css
  data/
    uploads/
    processed/
    snapshots/
    reports/
  models/
  .gitignore
  README.md
```

## 1. Start backend
Open PowerShell in `C:\\HighwayAI`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
uvicorn app.main:app --app-dir backend --reload
```

The first YOLO run may download the configured model (`yolo11n.pt`) from the model provider. An internet connection may be needed for this first download. Model performance depends on laptop hardware.

Backend API docs: http://127.0.0.1:8000/docs

## 2. Start frontend
Open a second PowerShell terminal in `C:\\HighwayAI`:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally http://localhost:5173.

## How it works
1. Upload a supported video.
2. Click Process.
3. Backend reads frames with OpenCV and runs YOLO on sampled frames.
4. OpenCV Haar cascade face detector runs on sampled frames.
5. Results are drawn into an annotated MP4.
6. The database saves video/job metadata, counts, and performance metrics.
7. Selected object/face crops are saved in `data/snapshots`.

This starter keeps a maximum of one saved crop per class per video for each detection category to avoid saving every repeated frame. It is a simple MVP policy, not a best-frame tracker. You can extend it with ByteTrack and top-K quality selection later.

## Notes
- Face detection locates faces; it does not identify people.
- Do not expose the local API to public networks without authentication and additional security.
- Large video files can use substantial disk space. Delete files you no longer need.
- This is a learning MVP. Test with short videos before using large files.
## Live AI preview (new)

1. Start the backend and frontend as described above.
2. Upload a highway video. The app opens the Video library and selects the uploaded video.
3. In the Selected video panel, choose **Start live AI preview**.
4. The browser receives a continuous MJPEG stream with YOLO vehicle/person boxes and optional face boxes.
5. Choose **Stop live AI preview** to close the stream. Choose **Save full processed video** when you also want a saved MP4 and CSV report.

The live preview is a temporary stream and does not itself save a processed MP4 or detections to the database. It runs on CPU and may be slower than the original video, especially on laptops with 8 GB RAM. The first preview may pause while the YOLO model loads/downloads. Face detection locates faces only; it does not identify people.


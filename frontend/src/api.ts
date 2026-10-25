const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = body.detail || message
    } catch { /* response was not JSON */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export type VideoRecord = {
  id: number
  original_name: string
  uploaded_at: string
  duration_seconds: number | null
  width: number | null
  height: number | null
  source_fps: number | null
  frame_count: number | null
  status: string
  error?: string | null
}

export type JobRecord = {
  id: number
  video_id: number
  original_name: string
  status: string
  progress: number
  processed_frames: number
  total_frames: number
  processing_fps: number
  average_fps: number
  elapsed_seconds: number
  error?: string | null
  summary?: Record<string, unknown>
}

export type Metrics = {
  videos_uploaded: number
  jobs_completed: number
  jobs_active: number
  detections_by_class: Record<string, number>
  latest_average_fps: number
  latest_elapsed_seconds: number
}

export const api = {
  health: () => request<{status: string}>('/api/health'),
  metrics: () => request<Metrics>('/api/metrics'),
  videos: () => request<VideoRecord[]>('/api/videos'),
  jobs: () => request<JobRecord[]>('/api/jobs'),
  upload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{id: number; original_name: string; status: string}>('/api/videos/upload', { method: 'POST', body: form })
  },
  process: (id: number, options: {confidence: number; every_n_frames: number; detect_faces: boolean; save_snapshots: boolean}) =>
    request<{job_id: number; status: string}>(`/api/videos/${id}/process`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(options)
    }),
  deleteVideo: (id: number) => request<{deleted: boolean}>(`/api/videos/${id}`, {method: 'DELETE'}),
  outputUrl: (id: number) => `${API_BASE}/api/videos/${id}/output`,
  livePreviewUrl: (id: number, confidence: number, detectFaces: boolean) => `${API_BASE}/api/videos/${id}/live-preview?confidence=${confidence}&detect_faces=${detectFaces ? 'true' : 'false'}`,
  reportUrl: (id: number) => `${API_BASE}/api/videos/${id}/download-report`,
  faces: () => request<any[]>('/api/faces'),
  deleteFace: (id: number) => request<{deleted: boolean}>(`/api/faces/${id}`, {method: 'DELETE'})
}

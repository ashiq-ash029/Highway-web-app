import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, BarChart3, BrainCircuit, CheckCircle2, ChevronRight, CircleHelp,
  Clock3, Database, Download, FileVideo, Gauge, HardDrive, LayoutDashboard,
  LoaderCircle, Play, RefreshCw, ScanFace, Search, Settings, ShieldCheck,
  Trash2, Upload, Video, Users, XCircle
} from 'lucide-react'
import { api, type JobRecord, type Metrics, type VideoRecord } from './api'

type Page = 'Dashboard' | 'Upload video' | 'Video library' | 'Processing jobs' | 'Face records' | 'Reports & analytics' | 'Settings'

const nav: {label: Page; icon: typeof LayoutDashboard}[] = [
  {label:'Dashboard', icon:LayoutDashboard},
  {label:'Upload video', icon:Upload},
  {label:'Video library', icon:Video},
  {label:'Processing jobs', icon:Activity},
  {label:'Face records', icon:ScanFace},
  {label:'Reports & analytics', icon:BarChart3},
  {label:'Settings', icon:Settings},
]

function fmtDuration(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return '—'
  const seconds = Math.max(0, Math.round(value))
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}
function fmtBytes(value: number) {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(0)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export default function App() {
  const [page, setPage] = useState<Page>('Dashboard')
  const [videos, setVideos] = useState<VideoRecord[]>([])
  const [jobs, setJobs] = useState<JobRecord[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [faces, setFaces] = useState<any[]>([])
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null)
  const [livePreviewVideo, setLivePreviewVideo] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [query, setQuery] = useState('')
  const [confidence, setConfidence] = useState(0.35)
  const [everyN, setEveryN] = useState(2)
  const [detectFaces, setDetectFaces] = useState(true)
  const [saveSnapshots, setSaveSnapshots] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [apiOnline, setApiOnline] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [v, j, m, f] = await Promise.all([api.videos(), api.jobs(), api.metrics(), api.faces()])
      setVideos(v); setJobs(j); setMetrics(m); setFaces(f); setApiOnline(true)
    } catch (e) {
      setApiOnline(false)
      setError(e instanceof Error ? e.message : 'Could not connect to the backend')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 3000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const filteredVideos = useMemo(() => videos.filter(v => v.original_name.toLowerCase().includes(query.toLowerCase())), [videos, query])
  const selected = videos.find(v => v.id === selectedVideo) || null
  const latestJob = jobs.find(j => j.video_id === selectedVideo) || jobs[0] || null

  async function upload() {
    if (!file) { setError('Choose a video file first.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.upload(file)
      setSelectedVideo(result.id)
      setNotice(`Uploaded ${result.original_name}.`)
      setFile(null)
      await refresh()
      setPage('Video library')
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setBusy(false) }
  }

  async function processVideo(id: number) {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api.process(id, {confidence, every_n_frames:everyN, detect_faces:detectFaces, save_snapshots:saveSnapshots})
      setSelectedVideo(id)
      setNotice(`Processing job #${result.job_id} started.`)
      await refresh()
      setPage('Processing jobs')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not start processing') }
    finally { setBusy(false) }
  }

  async function deleteVideo(id: number) {
    if (!window.confirm('Delete this video, its processed output, detections, and associated snapshots?')) return
    setError(''); setNotice('')
    try { await api.deleteVideo(id); if (selectedVideo === id) setSelectedVideo(null); setNotice('Video and associated records deleted.'); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Delete failed') }
  }

  async function deleteFace(id: number) {
    if (!window.confirm('Delete this face detection record and its saved crop, if any?')) return
    try { await api.deleteFace(id); setNotice('Face record deleted.'); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Delete failed') }
  }

  const detectionCounts = metrics?.detections_by_class || {}
  const faceCount = detectionCounts.face || 0
  const vehicleCount = ['car','motorcycle','bus','truck','bicycle'].reduce((n, k) => n + (detectionCounts[k] || 0), 0)
  const personCount = detectionCounts.person || 0

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><BrainCircuit size={23}/></div><div><strong>Highway AI</strong><small>VIDEO INTELLIGENCE</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(item => { const Icon = item.icon; return <button key={item.label} className={`nav-item ${page === item.label ? 'active' : ''}`} onClick={() => {setPage(item.label); setError('')}}><Icon size={18}/><span>{item.label}</span>{page === item.label && <ChevronRight size={15} className="nav-chevron"/>}</button> })}</nav>
      <div className="sidebar-bottom"><div className="local-badge"><span className="green-dot"/><div><strong>Local storage</strong><small>Files stay on this PC</small></div></div><div className="side-foot"><ShieldCheck size={14}/> Local-first prototype</div></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <strong>{page}</strong></div><div className="top-actions"><span className={`api-status ${apiOnline ? 'online' : 'offline'}`}><span className="status-dot"/>{apiOnline ? 'Backend connected' : 'Backend offline'}</span><button className="icon-button" title="Refresh data" onClick={() => void refresh()}><RefreshCw size={17}/></button><div className="avatar">AI</div></div></header>
      <div className="content">
        {error && <div className="alert error"><XCircle size={17}/><span>{error}</span><button onClick={() => setError('')}><XCircle size={15}/></button></div>}
        {notice && <div className="alert success"><CheckCircle2 size={17}/><span>{notice}</span><button onClick={() => setNotice('')}><XCircle size={15}/></button></div>}

        {page === 'Dashboard' && <section>
          <div className="page-heading"><div><div className="eyebrow">OVERVIEW</div><h1>Highway monitoring dashboard</h1><p>Analyze uploaded road footage and review AI detection performance.</p></div><button className="primary" onClick={() => setPage('Upload video')}><Upload size={17}/> Upload video</button></div>
          <div className="stat-grid">
            <Stat icon={<FileVideo/>} label="Videos uploaded" value={metrics?.videos_uploaded ?? '—'} tone="blue"/>
            <Stat icon={<CheckCircle2/>} label="Jobs completed" value={metrics?.jobs_completed ?? '—'} tone="green"/>
            <Stat icon={<Gauge/>} label="Latest average FPS" value={metrics ? metrics.latest_average_fps.toFixed(1) : '—'} tone="purple"/>
            <Stat icon={<Activity/>} label="Active jobs" value={metrics?.jobs_active ?? '—'} tone="orange"/>
          </div>
          <div className="two-col">
            <div className="panel"><div className="panel-head"><div><h2>Detection summary</h2><p>Frame-level detections across completed jobs</p></div><BarChart3 size={19}/></div>
              <div className="detection-list">{[['Vehicles',vehicleCount,'car'],['People',personCount,'person'],['Faces',faceCount,'face']].map(([label,val,key]) => <div className="detection-row" key={String(key)}><div className="detection-name"><span className={`legend ${key}`}/>{label}</div><strong>{val}</strong></div>)}</div>
              <div className="info-note"><CircleHelp size={15}/> Counts represent detections across analyzed frames, not unique vehicles or people.</div>
            </div>
            <div className="panel"><div className="panel-head"><div><h2>Recent processing</h2><p>Latest video analysis jobs</p></div><button className="text-button" onClick={() => setPage('Processing jobs')}>View all <ChevronRight size={14}/></button></div>
              {jobs.slice(0,5).length === 0 ? <Empty icon={<Activity/>} title="No processing jobs yet" desc="Upload a highway video and start analysis."/> : <div className="job-list">{jobs.slice(0,5).map(job => <div className="job-row" key={job.id}><div className="job-icon"><FileVideo size={17}/></div><div className="job-info"><strong>{job.original_name}</strong><small>Job #{job.id} · {job.processed_frames}/{job.total_frames || '?'} frames</small><div className="progress"><span style={{width:`${job.progress}%`}}/></div></div><Status value={job.status}/></div>)}</div>}
            </div>
          </div>
          <div className="panel table-panel"><div className="panel-head"><div><h2>Recent videos</h2><p>Locally stored video files</p></div><button className="text-button" onClick={() => setPage('Video library')}>Open library <ChevronRight size={14}/></button></div><VideoTable videos={videos.slice(0,5)} onProcess={processVideo} onDelete={deleteVideo} busy={busy}/></div>
        </section>}

        {page === 'Upload video' && <section>
          <div className="page-heading"><div><div className="eyebrow">VIDEO INGESTION</div><h1>Upload highway video</h1><p>Choose a video stored on your computer for local AI analysis.</p></div></div>
          <div className="upload-layout"><div className="panel upload-panel"><label className="dropzone"><input type="file" accept="video/mp4,video/avi,video/quicktime,video/x-matroska,video/webm,.mkv,.avi,.mov,.mp4,.webm" onChange={e => setFile(e.target.files?.[0] || null)}/><div className="upload-circle"><Upload size={25}/></div><h2>{file ? file.name : 'Select a highway video'}</h2><p>{file ? fmtBytes(file.size) : 'Click to browse files on this computer'}</p><span className="file-types">MP4 · AVI · MOV · MKV · WEBM</span></label>
            <div className="upload-foot"><span><HardDrive size={15}/> Stored locally in data/uploads</span><span>Max size configured by backend</span></div>
            <button className="primary full" onClick={() => void upload()} disabled={!file || busy}>{busy ? <LoaderCircle className="spin" size={17}/> : <Upload size={17}/>} {busy ? 'Uploading…' : 'Upload video'}</button>
          </div>
          <div className="panel"><div className="panel-head"><div><h2>Processing configuration</h2><p>Used when starting the next job</p></div><Settings size={19}/></div>
            <label className="form-label">Detection confidence <strong>{confidence.toFixed(2)}</strong><input type="range" min="0.1" max="0.9" step="0.05" value={confidence} onChange={e => setConfidence(Number(e.target.value))}/><small>Higher values may reduce false detections but miss some objects.</small></label>
            <label className="form-label">Analyze every Nth frame<select value={everyN} onChange={e => setEveryN(Number(e.target.value))}><option value="1">Every frame (slower)</option><option value="2">Every 2nd frame</option><option value="3">Every 3rd frame</option><option value="5">Every 5th frame (faster)</option></select><small>Skipped frames are retained in the output video but are not analyzed.</small></label>
            <label className="toggle-row"><span><strong>Face detection</strong><small>Locate visible faces in sampled frames</small></span><input type="checkbox" checked={detectFaces} onChange={e => setDetectFaces(e.target.checked)}/></label>
            <label className="toggle-row"><span><strong>Save sample crops</strong><small>Save limited example crops locally</small></span><input type="checkbox" checked={saveSnapshots} onChange={e => setSaveSnapshots(e.target.checked)}/></label>
          </div></div>
        </section>}

        {page === 'Video library' && <section><div className="page-heading"><div><div className="eyebrow">LOCAL FILE MANAGEMENT</div><h1>Video library</h1><p>Manage uploaded videos and launch AI processing.</p></div><button className="primary" onClick={() => setPage('Upload video')}><Upload size={17}/> Upload video</button></div>
          <div className="panel"><div className="toolbar"><div className="searchbox"><Search size={17}/><input placeholder="Search video filenames…" value={query} onChange={e => setQuery(e.target.value)}/></div><span className="muted">{filteredVideos.length} videos</span></div><VideoTable videos={filteredVideos} onProcess={processVideo} onDelete={deleteVideo} busy={busy}/></div>
          {selected && <div className="panel detail-panel"><div className="panel-head"><div><h2>Selected video</h2><p>{selected.original_name}</p></div><button className="icon-button" onClick={() => setSelectedVideo(null)}><XCircle size={17}/></button></div><div className="detail-grid"><Detail label="Duration" value={fmtDuration(selected.duration_seconds)}/><Detail label="Resolution" value={`${selected.width || '—'} × ${selected.height || '—'}`}/><Detail label="Original FPS" value={(selected.source_fps || 0).toFixed(2)}/><Detail label="Frames" value={selected.frame_count ?? '—'}/></div><div className="action-row"><button className="secondary" onClick={() => setLivePreviewVideo(livePreviewVideo === selected.id ? null : selected.id)}><Video size={16}/>{livePreviewVideo === selected.id ? 'Stop live AI preview' : 'Start live AI preview'}</button><button className="secondary" onClick={() => void processVideo(selected.id)} disabled={busy}><Play size={16}/> Save full processed video</button><a className="secondary link-button" href={api.reportUrl(selected.id)}><Download size={16}/> Download CSV report</a><a className="secondary link-button" href={api.outputUrl(selected.id)} target="_blank" rel="noreferrer"><Video size={16}/> Open processed video</a></div>{livePreviewVideo === selected.id && <div className="live-preview-wrap"><div className="panel-head"><div><h3>Live AI preview</h3><p>AI boxes are drawn while the uploaded video is read. CPU performance depends on video size and laptop speed.</p></div><span className="live-pill"><span/> LIVE</span></div><img className="live-preview-image" src={api.livePreviewUrl(selected.id, confidence, detectFaces)} alt="Live AI object and face detection preview"/><p className="muted">This preview is temporary. Use “Save full processed video” to create a processed video and report for later viewing.</p></div>}</div>}
        </section>}

        {page === 'Processing jobs' && <section><div className="page-heading"><div><div className="eyebrow">WORKER STATUS</div><h1>Processing jobs</h1><p>Track analysis progress, FPS, and job errors.</p></div><button className="secondary" onClick={() => void refresh()}><RefreshCw size={16}/> Refresh</button></div><div className="panel">{jobs.length === 0 ? <Empty icon={<Activity/>} title="No jobs yet" desc="Start processing a video from the library."/> : <div className="table-wrap"><table><thead><tr><th>Job</th><th>Video</th><th>Status</th><th>Progress</th><th>Frames analyzed</th><th>Current FPS</th><th>Average FPS</th><th>Elapsed</th></tr></thead><tbody>{jobs.map(j => <tr key={j.id}><td>#{j.id}</td><td className="file-cell">{j.original_name}</td><td><Status value={j.status}/>{j.error && <small className="error-text">{j.error}</small>}</td><td><div className="progress wide"><span style={{width:`${j.progress}%`}}/></div><small>{Number(j.progress || 0).toFixed(0)}%</small></td><td>{j.processed_frames}/{j.total_frames || '—'}</td><td>{Number(j.processing_fps || 0).toFixed(1)}</td><td>{Number(j.average_fps || 0).toFixed(1)}</td><td>{fmtDuration(j.elapsed_seconds)}</td></tr>)}</tbody></table></div>}</div><div className="info-note standalone"><CircleHelp size={15}/> This prototype processes one job at a time. FPS is measured by the backend, not simulated.</div></section>}

        {page === 'Face records' && <section><div className="page-heading"><div><div className="eyebrow">PRIVACY-SENSITIVE RECORDS</div><h1>Face detection records</h1><p>Review and delete saved face detections. No identity recognition is performed.</p></div></div><div className="panel"><div className="table-wrap"><table><thead><tr><th>Record</th><th>Source video</th><th>Frame</th><th>Timestamp</th><th>Confidence</th><th>Saved crop</th><th>Action</th></tr></thead><tbody>{faces.map(f => <tr key={f.id}><td>#{f.id}</td><td className="file-cell">{f.original_name}</td><td>{f.frame_number}</td><td>{Number(f.timestamp_seconds).toFixed(2)}s</td><td>{Number(f.confidence).toFixed(2)}</td><td>{f.snapshot_path ? 'Yes' : 'No'}</td><td><button className="icon-button danger" onClick={() => void deleteFace(f.id)} title="Delete record"><Trash2 size={16}/></button></td></tr>)}</tbody></table>{faces.length === 0 && <Empty icon={<ScanFace/>} title="No face records" desc="Run face detection on an uploaded video to see results here."/>}</div></div></section>}

        {page === 'Reports & analytics' && <section><div className="page-heading"><div><div className="eyebrow">ANALYTICS</div><h1>Reports & analytics</h1><p>Summary of completed detections and processing performance.</p></div></div><div className="stat-grid"><Stat icon={<Video/>} label="Uploaded videos" value={metrics?.videos_uploaded ?? 0} tone="blue"/><Stat icon={<CheckCircle2/>} label="Completed jobs" value={metrics?.jobs_completed ?? 0} tone="green"/><Stat icon={<Gauge/>} label="Latest avg. FPS" value={(metrics?.latest_average_fps ?? 0).toFixed(1)} tone="purple"/><Stat icon={<Clock3/>} label="Latest elapsed" value={fmtDuration(metrics?.latest_elapsed_seconds)} tone="orange"/></div><div className="panel"><div className="panel-head"><div><h2>Detection totals by class</h2><p>Counts are detections across frames, not unique tracked objects.</p></div></div>{Object.entries(detectionCounts).length === 0 ? <Empty icon={<BarChart3/>} title="No report data yet" desc="Complete a processing job to generate analytics."/> : <div className="bar-list">{Object.entries(detectionCounts).map(([name,count]) => <div className="bar-row" key={name}><div><span>{name}</span><strong>{count}</strong></div><div className="bar-track"><span style={{width:`${Math.min(100, Number(count) / Math.max(1,...Object.values(detectionCounts)) * 100)}%`}}/></div></div>)}</div>}</div><div className="panel"><div className="panel-head"><div><h2>Export reports</h2><p>Download a CSV report for a video with completed processing.</p></div></div><div className="report-list">{videos.map(v => <div className="report-row" key={v.id}><FileVideo size={18}/><div><strong>{v.original_name}</strong><small>{v.status} · {fmtDuration(v.duration_seconds)}</small></div><a className="icon-button" href={api.reportUrl(v.id)} title="Download CSV"><Download size={17}/></a></div>)}</div></div></section>}

        {page === 'Settings' && <section><div className="page-heading"><div><div className="eyebrow">CONFIGURATION</div><h1>Application settings</h1><p>Configure detection behaviour for new processing jobs.</p></div></div><div className="panel settings-panel"><div className="panel-head"><div><h2>AI processing defaults</h2><p>These settings are applied by the frontend when starting a job.</p></div><BrainCircuit size={20}/></div><label className="form-label">Default confidence threshold <strong>{confidence.toFixed(2)}</strong><input type="range" min="0.1" max="0.9" step="0.05" value={confidence} onChange={e => setConfidence(Number(e.target.value))}/></label><label className="form-label">Frame sampling<select value={everyN} onChange={e => setEveryN(Number(e.target.value))}><option value="1">Every frame</option><option value="2">Every 2nd frame</option><option value="3">Every 3rd frame</option><option value="5">Every 5th frame</option></select></label><label className="toggle-row"><span><strong>Face detection enabled</strong><small>Detect visible faces in sampled frames</small></span><input type="checkbox" checked={detectFaces} onChange={e => setDetectFaces(e.target.checked)}/></label><label className="toggle-row"><span><strong>Save sample crops</strong><small>Store a limited sample for each class in local storage</small></span><input type="checkbox" checked={saveSnapshots} onChange={e => setSaveSnapshots(e.target.checked)}/></label><div className="info-note"><HardDrive size={15}/> Local storage folders are configured in backend/app/config.py. File size limit is configured in backend/.env.</div><div className="info-note"><ShieldCheck size={15}/> This starter has no login system. Keep it bound to localhost and do not expose it to the internet without adding authentication and authorization.</div></div></section>}
      </div>
      <footer className="footer"><span>Highway AI Monitoring · Local prototype</span><span><span className={`status-dot ${apiOnline ? 'green-dot' : ''}`}/> {apiOnline ? 'API connected' : 'Waiting for API'}</span></footer>
    </main>
  </div>
}

function Stat({icon,label,value,tone}:{icon:React.ReactNode;label:string;value:React.ReactNode;tone:string}) {
  return <div className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div></div>
}
function Status({value}:{value:string}) {
  const normalized = value.toLowerCase()
  return <span className={`status-pill ${normalized}`}><span className="status-dot"/>{value}</span>
}
function Empty({icon,title,desc}:{icon:React.ReactNode;title:string;desc:string}) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><strong>{title}</strong><p>{desc}</p></div>
}
function Detail({label,value}:{label:string;value:React.ReactNode}) {
  return <div className="detail-item"><small>{label}</small><strong>{value}</strong></div>
}
function VideoTable({videos,onProcess,onDelete,busy}:{videos:VideoRecord[];onProcess:(id:number)=>void;onDelete:(id:number)=>void;busy:boolean}) {
  if (!videos.length) return <Empty icon={<FileVideo/>} title="No videos found" desc="Upload a highway video to get started."/>
  return <div className="table-wrap"><table><thead><tr><th>Video</th><th>Duration</th><th>Resolution</th><th>Source FPS</th><th>Status</th><th>Actions</th></tr></thead><tbody>{videos.map(v => <tr key={v.id}><td><div className="video-name"><div className="video-mini"><FileVideo size={17}/></div><div><strong>{v.original_name}</strong><small>Uploaded {new Date(v.uploaded_at).toLocaleString()}</small></div></div></td><td>{fmtDuration(v.duration_seconds)}</td><td>{v.width || '—'} × {v.height || '—'}</td><td>{Number(v.source_fps || 0).toFixed(1)}</td><td><Status value={v.status}/></td><td><div className="table-actions"><button className="icon-button" title="Start processing" disabled={busy || v.status === 'processing'} onClick={() => onProcess(v.id)}><Play size={16}/></button><button className="icon-button danger" title="Delete video" disabled={v.status === 'processing'} onClick={() => onDelete(v.id)}><Trash2 size={16}/></button></div></td></tr>)}</tbody></table></div>
}

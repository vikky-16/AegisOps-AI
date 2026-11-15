"""
Real-Time Logging Router
Provides Server-Sent Events (SSE) at /logs/stream, WebSockets at /ws/logs,
test log triggers, and an embedded zero-dependency live logs dashboard.
"""

import json
import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field

from backend.app.logger import realtime_logger

router = APIRouter(tags=["Real-Time Logs"])


class TestLogRequest(BaseModel):
    level: str = Field(default="info", description="info, warn, error, or unhandled")
    message: str = Field(default="Test real-time log event", description="Log message text")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional metadata object")


@router.get("/logs/history")
@router.get("/api/logs/history")
async def get_log_history():
    """Returns the current in-memory rolling history buffer (up to 300 entries)."""
    return {
        "count": len(realtime_logger.buffer),
        "capacity": 300,
        "logs": realtime_logger.get_history()
    }


@router.get("/logs/stream")
@router.get("/api/logs/stream")
async def stream_logs_sse(request: Request):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Sends rolling history buffer first, then continuously streams live logs.
    """
    async def event_generator():
        # 1. Subscribe to real-time events
        q = await realtime_logger.subscribe_sse()
        try:
            # 2. Emit initial 300-entry history buffer
            history = realtime_logger.get_history()
            initial_payload = {
                "type": "history",
                "count": len(history),
                "data": history
            }
            yield f"event: history\ndata: {json.dumps(initial_payload)}\n\n"

            # 3. Stream incoming logs live as they are emitted
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                try:
                    # Timeout after 15s to send keep-alive ping
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: log\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
        finally:
            realtime_logger.unsubscribe_sse(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.websocket("/ws/logs")
@router.websocket("/logs/ws")
@router.websocket("/api/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    """
    WebSocket streaming endpoint.
    Sends rolling history buffer immediately on connect, then broadcasts new logs.
    """
    await websocket.accept()
    realtime_logger.subscribe_ws(websocket)
    try:
        # Send history buffer first
        history = realtime_logger.get_history()
        await websocket.send_text(json.dumps({
            "type": "history",
            "count": len(history),
            "data": history
        }))

        # Keep connection open and handle incoming pings
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_logger.unsubscribe_ws(websocket)
    except Exception:
        realtime_logger.unsubscribe_ws(websocket)


@router.post("/api/logs/test-event")
@router.get("/api/logs/test-event")
async def trigger_test_log(
    level: str = Query(default="info"),
    message: Optional[str] = Query(default=None),
    req: Optional[TestLogRequest] = None
):
    """
    Test endpoint to trigger sample INFO, WARN, ERROR, or unhandled exceptions.
    Helps verify live streaming and failure capture instantly.
    """
    log_level = (req.level if req else level).lower()
    log_msg = (req.message if req and req.message else message) or f"Live test {log_level.upper()} event generated"
    log_meta = req.meta if req and req.meta else {"test": True, "source": "test_endpoint"}

    if log_level == "unhandled":
        # Intentionally raise an unhandled exception to test middleware & exception capture
        raise RuntimeError(f"Simulated unhandled exception for testing real-time failure capture: {log_msg}")

    if log_level == "error":
        try:
            # Generate a realistic error with traceback
            raise ValueError(f"Simulated critical failure: {log_msg}")
        except Exception:
            entry = realtime_logger.error(log_msg, exc_info=True, **log_meta)
    elif log_level in ("warn", "warning"):
        entry = realtime_logger.warn(log_msg, **log_meta)
    else:
        entry = realtime_logger.info(log_msg, **log_meta)

    return {
        "success": True,
        "emitted_log": entry.to_dict(),
        "total_buffer_count": len(realtime_logger.buffer)
    }


@router.get("/admin/logs", response_class=HTMLResponse)
@router.get("/logs/live", response_class=HTMLResponse)
async def standalone_logs_dashboard():
    """
    Embedded standalone real-time log streaming dashboard.
    Works independently with zero external build tools required.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AegisOps AI - Live Real-Time Logs</title>
  <style>
    :root {
      --bg: #0B0F19;
      --card-bg: #111827;
      --border: #1F2937;
      --text: #F3F4F6;
      --text-muted: #9CA3AF;
      --info: #38BDF8;
      --info-bg: rgba(56, 189, 248, 0.1);
      --warn: #FBBF24;
      --warn-bg: rgba(251, 191, 36, 0.1);
      --error: #F87171;
      --error-bg: rgba(248, 113, 113, 0.15);
      --accent: #6366F1;
      --code-bg: #030712;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #06B6D4, #6366F1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      color: white;
      font-size: 16px;
    }
    .title h1 { font-size: 15px; font-weight: 700; color: #fff; }
    .title p { font-size: 11px; color: var(--text-muted); }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-family: monospace;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.15);
      color: #34D399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-badge.disconnected {
      background: rgba(239, 68, 68, 0.15);
      color: #F87171;
      border-color: rgba(239, 68, 68, 0.3);
    }
    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: currentColor;
    }
    .toolbar {
      background: #0d1322;
      border-bottom: 1px solid var(--border);
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      flex-shrink: 0;
    }
    .filters {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .filter-btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s ease;
    }
    .filter-btn.active {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    .search-box {
      background: #111827;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 12px;
      width: 220px;
      outline: none;
    }
    .search-box:focus { border-color: #38BDF8; }
    .controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn:hover { background: #334155; }
    .btn.active { background: #0284c7; color: white; border-color: #0284c7; }
    .btn-test { background: rgba(99, 102, 241, 0.2); border-color: rgba(99, 102, 241, 0.4); color: #A5B4FC; }
    .btn-test:hover { background: rgba(99, 102, 241, 0.35); }
    .btn-error { background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.4); color: #FCA5A5; }
    .btn-error:hover { background: rgba(239, 68, 68, 0.35); }

    main {
      flex: 1;
      overflow-y: auto;
      padding: 16px 24px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .log-row {
      display: flex;
      flex-direction: column;
      padding: 6px 10px;
      border-radius: 6px;
      background: rgba(17, 24, 39, 0.5);
      border-left: 3px solid transparent;
      transition: background 0.1s;
    }
    .log-row:hover { background: rgba(30, 41, 59, 0.6); }
    .log-row.info { border-left-color: var(--info); }
    .log-row.warn { border-left-color: var(--warn); background: rgba(251, 191, 36, 0.04); }
    .log-row.error { border-left-color: var(--error); background: rgba(239, 68, 68, 0.06); }
    .log-main {
      display: flex;
      align-items: baseline;
      gap: 10px;
      cursor: pointer;
    }
    .timestamp {
      color: #64748B;
      font-size: 11px;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
      flex-shrink: 0;
    }
    .badge.info { background: var(--info-bg); color: var(--info); }
    .badge.warn { background: var(--warn-bg); color: var(--warn); }
    .badge.error { background: var(--error-bg); color: var(--error); }
    .message {
      color: #E2E8F0;
      word-break: break-word;
      flex: 1;
    }
    .log-row.error .message { color: #FCA5A5; font-weight: 600; }
    .log-row.warn .message { color: #FDE68A; }
    .details {
      margin-top: 6px;
      padding: 8px;
      background: var(--code-bg);
      border-radius: 4px;
      border: 1px solid var(--border);
      font-size: 11px;
      color: #CBD5E1;
      display: none;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    .details.open { display: block; }
    .stack-trace {
      margin-top: 6px;
      color: #F87171;
      font-family: inherit;
    }
    .empty-state {
      margin: auto;
      text-align: center;
      color: var(--text-muted);
      font-family: sans-serif;
      font-size: 13px;
    }
    .stats-bar {
      padding: 6px 24px;
      background: #080c14;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
      flex-shrink: 0;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <div class="title">
        <h1>AegisOps Real-Time Live Logs</h1>
        <p>Live Streaming Server Logs (SSE / WebSocket) • 300-Item Buffer</p>
      </div>
    </div>
    <div id="statusBadge" class="status-badge">
      <span class="pulse-dot"></span>
      <span id="statusText">CONNECTING...</span>
    </div>
  </header>

  <div class="toolbar">
    <div class="filters">
      <button class="filter-btn active" data-level="all">All Logs (<span id="countAll">0</span>)</button>
      <button class="filter-btn" data-level="info">Info (<span id="countInfo">0</span>)</button>
      <button class="filter-btn" data-level="warn">Warn (<span id="countWarn">0</span>)</button>
      <button class="filter-btn" data-level="error">Errors (<span id="countError">0</span>)</button>
      <input type="text" id="searchBox" class="search-box" placeholder="Filter logs...">
    </div>

    <div class="controls">
      <button id="simToggleBtn" class="btn" style="background: linear-gradient(135deg, #059669, #0891b2); color: #fff; border: none;">▶ Start Simulator</button>
      <button id="autoscrollBtn" class="btn active">Auto-Scroll: ON</button>
      <button id="clearBtn" class="btn">Clear View</button>
      <button id="testInfoBtn" class="btn btn-test">+ Test Info</button>
      <button id="testWarnBtn" class="btn btn-test">+ Test Warn</button>
      <button id="testErrorBtn" class="btn btn-error">+ Trigger Error</button>
    </div>
  </div>

  <main id="logsContainer">
    <div id="emptyState" class="empty-state">Waiting for logs...</div>
  </main>

  <div class="stats-bar">
    <span id="bufferInfo">Buffer: 0 / 300 items</span>
    <span id="simStatusText">Simulator: Inactive</span>
    <span>Connected to /logs/stream</span>
  </div>

  <script>
    const logsContainer = document.getElementById('logsContainer');
    const emptyState = document.getElementById('emptyState');
    const statusBadge = document.getElementById('statusBadge');
    const statusText = document.getElementById('statusText');
    const autoscrollBtn = document.getElementById('autoscrollBtn');
    const clearBtn = document.getElementById('clearBtn');
    const searchBox = document.getElementById('searchBox');
    const bufferInfo = document.getElementById('bufferInfo');

    const countAll = document.getElementById('countAll');
    const countInfo = document.getElementById('countInfo');
    const countWarn = document.getElementById('countWarn');
    const countError = document.getElementById('countError');

    let allLogs = [];
    let activeLevel = 'all';
    let autoScroll = true;
    let searchQuery = '';

    function updateCounts() {
      let info = 0, warn = 0, error = 0;
      allLogs.forEach(l => {
        if (l.level === 'warn' || l.level === 'warning') warn++;
        else if (l.level === 'error' || l.level === 'critical') error++;
        else info++;
      });
      countAll.textContent = allLogs.length;
      countInfo.textContent = info;
      countWarn.textContent = warn;
      countError.textContent = error;
      bufferInfo.textContent = `Buffer: ${allLogs.length} / 300 items`;
    }

    function createLogRow(entry) {
      const row = document.createElement('div');
      const lvl = (entry.level || 'info').toLowerCase();
      const normLvl = (lvl === 'warn' || lvl === 'warning') ? 'warn' : (lvl === 'error' || lvl === 'critical') ? 'error' : 'info';
      row.className = `log-row ${normLvl}`;
      row.dataset.level = normLvl;
      row.dataset.text = (entry.message + ' ' + JSON.stringify(entry.meta || {})).toLowerCase();

      const timeStr = entry.timestamp ? (entry.timestamp.includes('T') ? entry.timestamp.split('T')[1].replace('Z','') : entry.timestamp) : new Date().toLocaleTimeString();
      
      const mainDiv = document.createElement('div');
      mainDiv.className = 'log-main';
      mainDiv.innerHTML = `
        <span class="timestamp">${timeStr}</span>
        <span class="badge ${normLvl}">${normLvl}</span>
        <span class="message">${escapeHtml(entry.message)}</span>
      `;

      const details = document.createElement('div');
      details.className = 'details';
      let metaContent = '';
      if (entry.meta && Object.keys(entry.meta).length > 0) {
        metaContent += 'Metadata: ' + JSON.stringify(entry.meta, null, 2);
      }
      if (entry.meta && entry.meta.stack_trace) {
        metaContent += '\\n\\nStack Trace:\\n' + entry.meta.stack_trace;
      }
      details.textContent = metaContent || 'No additional metadata';

      mainDiv.addEventListener('click', () => {
        details.classList.toggle('open');
      });

      row.appendChild(mainDiv);
      if (entry.meta && (Object.keys(entry.meta).length > 0 || entry.meta.stack_trace)) {
        row.appendChild(details);
      }

      return row;
    }

    function escapeHtml(str) {
      return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function renderLogs() {
      logsContainer.innerHTML = '';
      const filtered = allLogs.filter(l => {
        const lvl = (l.level === 'warn' || l.level === 'warning') ? 'warn' : (l.level === 'error' || l.level === 'critical') ? 'error' : 'info';
        if (activeLevel !== 'all' && lvl !== activeLevel) return false;
        if (searchQuery) {
          const matchStr = (l.message + ' ' + JSON.stringify(l.meta || {})).toLowerCase();
          if (!matchStr.includes(searchQuery)) return false;
        }
        return true;
      });

      if (filtered.length === 0) {
        logsContainer.appendChild(emptyState);
        emptyState.textContent = allLogs.length === 0 ? 'Waiting for logs...' : 'No logs match active filter.';
        return;
      }

      filtered.forEach(log => {
        logsContainer.appendChild(createLogRow(log));
      });

      if (autoScroll) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
      }
    }

    function appendLog(entry) {
      allLogs.push(entry);
      if (allLogs.length > 300) allLogs.shift();
      updateCounts();

      const lvl = (entry.level === 'warn' || entry.level === 'warning') ? 'warn' : (entry.level === 'error' || entry.level === 'critical') ? 'error' : 'info';
      const matchesLevel = (activeLevel === 'all' || activeLevel === lvl);
      const matchStr = (entry.message + ' ' + JSON.stringify(entry.meta || {})).toLowerCase();
      const matchesSearch = !searchQuery || matchStr.includes(searchQuery);

      if (matchesLevel && matchesSearch) {
        if (logsContainer.contains(emptyState)) {
          logsContainer.removeChild(emptyState);
        }
        const row = createLogRow(entry);
        logsContainer.appendChild(row);
        if (autoScroll) {
          logsContainer.scrollTop = logsContainer.scrollHeight;
        }
      }
    }

    // Connect SSE
    function connectSSE() {
      const evtSource = new EventSource('/logs/stream');

      evtSource.onopen = () => {
        statusBadge.className = 'status-badge';
        statusText.textContent = 'LIVE STREAMING';
      };

      evtSource.addEventListener('history', (e) => {
        try {
          const res = JSON.parse(e.data);
          allLogs = res.data || [];
          updateCounts();
          renderLogs();
        } catch (err) {
          console.error(err);
        }
      });

      evtSource.addEventListener('log', (e) => {
        try {
          const entry = JSON.parse(e.data);
          appendLog(entry);
        } catch (err) {
          console.error(err);
        }
      });

      evtSource.onerror = () => {
        statusBadge.className = 'status-badge disconnected';
        statusText.textContent = 'RECONNECTING...';
      };
    }

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeLevel = btn.dataset.level;
        renderLogs();
      });
    });

    // Search Box
    searchBox.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderLogs();
    });

    // Auto-Scroll Toggle
    autoscrollBtn.addEventListener('click', () => {
      autoScroll = !autoScroll;
      if (autoScroll) {
        autoscrollBtn.textContent = 'Auto-Scroll: ON';
        autoscrollBtn.classList.add('active');
        logsContainer.scrollTop = logsContainer.scrollHeight;
      } else {
        autoscrollBtn.textContent = 'Auto-Scroll: OFF';
        autoscrollBtn.classList.remove('active');
      }
    });

    // Clear View
    clearBtn.addEventListener('click', () => {
      allLogs = [];
      updateCounts();
      renderLogs();
    });

    // Test buttons
    document.getElementById('testInfoBtn').addEventListener('click', () => {
      fetch('/api/logs/test-event?level=info&message=Standard+operational+log+event', { method: 'POST' });
    });
    document.getElementById('testWarnBtn').addEventListener('click', () => {
      fetch('/api/logs/test-event?level=warn&message=High+latency+warning+threshold+exceeded+(420ms)', { method: 'POST' });
    });
    document.getElementById('testErrorBtn').addEventListener('click', () => {
      fetch('/api/logs/test-event?level=error&message=Database+connection+pool+exhausted+failure', { method: 'POST' });
    });

    // Simulator Toggle & Status
    const simToggleBtn = document.getElementById('simToggleBtn');
    const simStatusText = document.getElementById('simStatusText');
    let isSimRunning = false;

    async function pollSimulator() {
      try {
        const res = await fetch('/dev/logs/simulate/status');
        if (res.ok) {
          const st = await res.json();
          isSimRunning = st.is_running;
          if (isSimRunning) {
            simToggleBtn.textContent = '⏹ Stop Simulator (' + st.log_rate_per_sec + '/s)';
            simToggleBtn.style.background = 'rgba(239, 68, 68, 0.2)';
            simToggleBtn.style.border = '1px solid rgba(239, 68, 68, 0.4)';
            simToggleBtn.style.color = '#FCA5A5';
            simStatusText.textContent = 'Simulator: ACTIVE (' + st.log_rate_per_sec + '/s, ' + st.total_emitted + ' sent, ' + st.total_errors + ' errs, ' + st.total_healed + ' healed)';
          } else {
            simToggleBtn.textContent = '▶ Start Simulator';
            simToggleBtn.style.background = 'linear-gradient(135deg, #059669, #0891b2)';
            simToggleBtn.style.border = 'none';
            simToggleBtn.style.color = '#fff';
            simStatusText.textContent = 'Simulator: Inactive';
          }
        }
      } catch (e) {}
    }

    simToggleBtn.addEventListener('click', async () => {
      simToggleBtn.disabled = true;
      try {
        const url = isSimRunning ? '/dev/logs/simulate/stop' : '/dev/logs/simulate/start?rate=8.0&failures=5.0';
        await fetch(url, { method: 'POST' });
        await pollSimulator();
      } finally {
        simToggleBtn.disabled = false;
      }
    });

    setInterval(pollSimulator, 2500);
    pollSimulator();

    connectSSE();
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal,
  Activity,
  Play,
  Pause,
  Trash2,
  Search,
  AlertCircle,
  AlertTriangle,
  Info,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Zap,
  Radio,
  Copy,
  Check,
  Cpu,
  RefreshCw
} from 'lucide-react';

interface StructuredLog {
  timestamp: string;
  level: string;
  message: string;
  meta?: Record<string, any>;
}

interface SimulatorStatus {
  is_running: boolean;
  log_rate_per_sec: number;
  failure_rate_per_min: number;
  max_logs?: number | null;
  total_emitted: number;
  total_infos: number;
  total_warns: number;
  total_errors: number;
  total_healed: number;
}

export const LogsDashboard: React.FC = () => {
  const [logs, setLogs] = useState<StructuredLog[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connectionType, setConnectionType] = useState<string>('SSE');
  const [isAutoScroll, setIsAutoScroll] = useState<boolean>(true);
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedIndices, setExpandedIndices] = useState<Set<number>>(new Set());
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [isEmitting, setIsEmitting] = useState<boolean>(false);

  // Simulator controls state
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatus | null>(null);
  const [isTogglingSim, setIsTogglingSim] = useState<boolean>(false);

  const logsEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const baseUrl = window.location.port === '5173' ? 'http://127.0.0.1:8000' : '';

  // Auto-scroll handler
  useEffect(() => {
    if (isAutoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isAutoScroll]);

  // Fetch simulator status periodically
  const fetchSimulatorStatus = async () => {
    try {
      const res = await fetch(`${baseUrl}/dev/logs/simulate/status`);
      if (res.ok) {
        const data = await res.json();
        setSimulatorStatus(data);
      }
    } catch (e) {
      // Handled silently
    }
  };

  useEffect(() => {
    fetchSimulatorStatus();
    const interval = setInterval(fetchSimulatorStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleSimulator = async () => {
    setIsTogglingSim(true);
    try {
      const endpoint = simulatorStatus?.is_running
        ? `${baseUrl}/dev/logs/simulate/stop`
        : `${baseUrl}/dev/logs/simulate/start?rate=8.0&failures=5.0`;
      const res = await fetch(endpoint, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.status) {
          setSimulatorStatus(data.status);
        }
      }
    } catch (e) {
      console.error('Failed to toggle simulator:', e);
    } finally {
      setIsTogglingSim(false);
      fetchSimulatorStatus();
    }
  };

  // Connect to SSE stream
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let ws: WebSocket | null = null;

    const connectSSE = () => {
      const streamUrl = window.location.port === '5173'
        ? 'http://127.0.0.1:8000/logs/stream'
        : '/logs/stream';

      try {
        eventSource = new EventSource(streamUrl);
        setConnectionType('SSE');

        eventSource.onopen = () => {
          setIsConnected(true);
        };

        eventSource.addEventListener('history', (e) => {
          try {
            const payload = JSON.parse(e.data);
            if (payload && Array.isArray(payload.data)) {
              setLogs(payload.data);
            }
          } catch (err) {
            console.error('Error parsing history payload:', err);
          }
        });

        eventSource.addEventListener('log', (e) => {
          try {
            const entry = JSON.parse(e.data) as StructuredLog;
            setLogs((prev) => {
              const updated = [...prev, entry];
              return updated.length > 300 ? updated.slice(updated.length - 300) : updated;
            });
          } catch (err) {
            console.error('Error parsing live log event:', err);
          }
        });

        eventSource.onerror = () => {
          setIsConnected(false);
        };
      } catch (e) {
        connectWS();
      }
    };

    const connectWS = () => {
      const wsUrl = window.location.port === '5173'
        ? 'ws://127.0.0.1:8000/ws/logs'
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/logs`;

      try {
        ws = new WebSocket(wsUrl);
        setConnectionType('WebSocket');

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'history' && Array.isArray(msg.data)) {
              setLogs(msg.data);
            } else if (msg.type === 'log' && msg.data) {
              setLogs((prev) => {
                const updated = [...prev, msg.data];
                return updated.length > 300 ? updated.slice(updated.length - 300) : updated;
              });
            }
          } catch (err) {
            console.error('Error parsing WS message:', err);
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
        };
      } catch (e) {
        console.error('WebSocket connection failed:', e);
      }
    };

    connectSSE();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const toggleExpand = (index: number) => {
    setExpandedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleTriggerTest = async (level: string, message?: string) => {
    setIsEmitting(true);
    try {
      await fetch(`${baseUrl}/api/logs/test-event?level=${level}${message ? `&message=${encodeURIComponent(message)}` : ''}`, {
        method: 'POST',
      });
    } catch (e) {
      // Ignored
    } finally {
      setIsEmitting(false);
    }
  };

  // Filter and search
  const filteredLogs = logs.filter((log) => {
    const lvl = (log.level || 'info').toLowerCase();
    const normLvl = lvl === 'warning' ? 'warn' : lvl === 'critical' ? 'error' : lvl;

    if (filterLevel !== 'all' && normLvl !== filterLevel) {
      return false;
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      const matchMsg = (log.message || '').toLowerCase().includes(query);
      const matchMeta = JSON.stringify(log.meta || {}).toLowerCase().includes(query);
      return matchMsg || matchMeta;
    }

    return true;
  });

  const countInfo = logs.filter((l) => (l.level || '').toLowerCase() === 'info').length;
  const countWarn = logs.filter((l) => ['warn', 'warning'].includes((l.level || '').toLowerCase())).length;
  const countError = logs.filter((l) => ['error', 'critical'].includes((l.level || '').toLowerCase())).length;

  const getLevelBadge = (level: string) => {
    const lvl = (level || 'info').toLowerCase();
    if (lvl === 'error' || lvl === 'critical') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
          <AlertCircle className="h-3 w-3" />
          ERROR
        </span>
      );
    }
    if (lvl === 'warn' || lvl === 'warning') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
          <AlertTriangle className="h-3 w-3" />
          WARN
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
        <Info className="h-3 w-3" />
        INFO
      </span>
    );
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto flex flex-col h-[calc(100vh-100px)]">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-900/60 p-4 rounded-2xl border border-slate-800/80 backdrop-blur-md flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Terminal className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">Live Real-Time Logs Stream</h2>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold flex items-center gap-1.5 ${
                isConnected
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'}`} />
                {isConnected ? `STREAMING (${connectionType})` : 'CONNECTING...'}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Live zero-polling event stream with 300-item memory ring buffer and automated error capture.
            </p>
          </div>
        </div>

        {/* Traffic Simulator Controls & Test Generator Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Continuous Simulator Toggle */}
          <button
            onClick={handleToggleSimulator}
            disabled={isTogglingSim}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-md ${
              simulatorStatus?.is_running
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
                : 'bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white shadow-emerald-500/20'
            } disabled:opacity-50`}
            title="Toggle continuous production traffic & failure generator"
          >
            <Cpu className={`h-3.5 w-3.5 ${simulatorStatus?.is_running ? 'animate-spin text-rose-400' : 'text-emerald-200'}`} />
            <span>
              {simulatorStatus?.is_running
                ? `Stop Simulator (${simulatorStatus.log_rate_per_sec}/s)`
                : '▶ Start Traffic Simulator'}
            </span>
          </button>

          <button
            onClick={() => handleTriggerTest('info', 'GET /api/v1/users 200 OK - 32ms')}
            disabled={isEmitting}
            className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1 disabled:opacity-50"
            title="Emit a test INFO log"
          >
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
            <span>+ Test Info</span>
          </button>

          <button
            onClick={() => handleTriggerTest('warn', 'Slow query on database-cluster (1420ms)')}
            disabled={isEmitting}
            className="px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs font-semibold border border-amber-500/30 transition flex items-center gap-1 disabled:opacity-50"
            title="Emit a test WARN log"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            <span>+ Test Warn</span>
          </button>

          <button
            onClick={() => handleTriggerTest('error', '500 Internal Server Error in payment processor')}
            disabled={isEmitting}
            className="px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-bold border border-rose-500/40 shadow-lg shadow-rose-500/10 transition flex items-center gap-1 disabled:opacity-50"
            title="Trigger an error with full stack trace"
          >
            <Zap className="h-3.5 w-3.5 text-rose-400" />
            <span>+ Trigger Error</span>
          </button>
        </div>
      </div>

      {/* Simulator Metrics Sub-Bar (When Active) */}
      {simulatorStatus?.is_running && (
        <div className="px-4 py-2 bg-slate-900/80 rounded-xl border border-indigo-500/30 flex items-center justify-between text-xs text-slate-300">
          <div className="flex items-center gap-2 font-mono">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
            <span className="font-bold text-emerald-400">TRAFFIC SIMULATOR ACTIVE</span>
            <span className="text-slate-500">|</span>
            <span>Speed: <strong className="text-white">{simulatorStatus.log_rate_per_sec} logs/sec</strong></span>
            <span className="text-slate-500">|</span>
            <span>Failures: <strong className="text-amber-400">~{simulatorStatus.failure_rate_per_min}/min</strong></span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span>Emitted: <strong className="text-white">{simulatorStatus.total_emitted.toLocaleString()}</strong></span>
            <span>Errors: <strong className="text-rose-400">{simulatorStatus.total_errors}</strong></span>
            <span>Healed: <strong className="text-cyan-400">{simulatorStatus.total_healed}</strong></span>
          </div>
        </div>
      )}

      {/* Toolbar & Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-900/40 p-3 rounded-xl border border-slate-800/80 flex-shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Level Filter Pills */}
          <button
            onClick={() => setFilterLevel('all')}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
              filterLevel === 'all'
                ? 'bg-indigo-600 text-white font-bold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            All Logs ({logs.length})
          </button>

          <button
            onClick={() => setFilterLevel('info')}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
              filterLevel === 'info'
                ? 'bg-cyan-600 text-white font-bold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Info ({countInfo})
          </button>

          <button
            onClick={() => setFilterLevel('warn')}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
              filterLevel === 'warn'
                ? 'bg-amber-600 text-white font-bold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Warn ({countWarn})
          </button>

          <button
            onClick={() => setFilterLevel('error')}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
              filterLevel === 'error'
                ? 'bg-rose-600 text-white font-bold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Errors ({countError})
          </button>

          {/* Search Box */}
          <div className="relative ml-2">
            <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search message or metadata..."
              className="pl-8 pr-3 py-1 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-52"
            />
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsAutoScroll(!isAutoScroll)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
              isAutoScroll
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}
            title="Toggle Auto-Scroll"
          >
            {isAutoScroll ? <Play className="h-3 w-3 fill-cyan-300" /> : <Pause className="h-3 w-3" />}
            <span>Auto-Scroll: {isAutoScroll ? 'ON' : 'PAUSED'}</span>
          </button>

          <button
            onClick={() => setLogs([])}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-slate-700 transition"
            title="Clear view buffer"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Live Logs Stream Console */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto bg-slate-950/90 rounded-2xl border border-slate-800/90 p-4 font-mono text-xs space-y-1.5 shadow-inner"
      >
        {filteredLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2 py-16">
            <Radio className="h-8 w-8 animate-pulse text-slate-600" />
            <p className="text-xs">
              {logs.length === 0 ? 'Listening for real-time logs...' : 'No logs match the current search / filter.'}
            </p>
          </div>
        ) : (
          filteredLogs.map((log, idx) => {
            const isExpanded = expandedIndices.has(idx);
            const lvl = (log.level || 'info').toLowerCase();
            const isErr = lvl === 'error' || lvl === 'critical';
            const isWarn = lvl === 'warn' || lvl === 'warning';
            const hasMeta = log.meta && Object.keys(log.meta).length > 0;
            const isHealed = log.meta?.healed_trace;

            const timeFormatted = log.timestamp
              ? log.timestamp.includes('T')
                ? log.timestamp.split('T')[1].replace('Z', '')
                : log.timestamp
              : new Date().toLocaleTimeString();

            return (
              <div
                key={idx}
                className={`rounded-lg p-2.5 transition border ${
                  isErr
                    ? 'bg-rose-950/20 border-rose-900/40 hover:bg-rose-950/30'
                    : isHealed
                    ? 'bg-cyan-950/20 border-cyan-800/40 hover:bg-cyan-950/30'
                    : isWarn
                    ? 'bg-amber-950/15 border-amber-900/30 hover:bg-amber-950/20'
                    : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-900'
                }`}
              >
                <div
                  className="flex items-start gap-2.5 cursor-pointer"
                  onClick={() => hasMeta && toggleExpand(idx)}
                >
                  {hasMeta ? (
                    <button className="mt-0.5 text-slate-500 hover:text-slate-300">
                      {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    </button>
                  ) : (
                    <span className="w-3.5" />
                  )}

                  <span className="text-slate-500 text-[11px] select-none whitespace-nowrap">
                    {timeFormatted}
                  </span>

                  <div>{getLevelBadge(log.level)}</div>

                  <span className={`flex-1 break-all ${
                    isErr ? 'text-rose-200 font-semibold' : isHealed ? 'text-cyan-200 font-medium' : isWarn ? 'text-amber-200' : 'text-slate-200'
                  }`}>
                    {log.message}
                  </span>

                  {log.meta?.trace_id && (
                    <span className="px-1.5 py-0.5 rounded bg-slate-950 text-[10px] text-slate-400 font-mono border border-slate-800">
                      {log.meta.trace_id}
                    </span>
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCopy(JSON.stringify(log, null, 2), idx);
                    }}
                    className="text-slate-600 hover:text-slate-400 p-1"
                    title="Copy Log JSON"
                  >
                    {copiedIndex === idx ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  </button>
                </div>

                {/* Expandable Meta & Stack Trace Accordion */}
                {isExpanded && hasMeta && (
                  <div className="mt-2.5 pt-2.5 border-t border-slate-800/80 pl-6 space-y-2 text-[11px]">
                    {log.meta?.stack_trace && (
                      <div className="bg-slate-950 p-2.5 rounded-lg border border-rose-900/40 text-rose-300 overflow-x-auto whitespace-pre font-mono">
                        <p className="text-[10px] font-bold uppercase text-rose-400 mb-1 flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />
                          Stack Trace
                        </p>
                        {log.meta.stack_trace}
                      </div>
                    )}

                    <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-slate-400 overflow-x-auto">
                      <p className="text-[10px] font-bold uppercase text-slate-500 mb-1">Metadata JSON</p>
                      <pre className="text-cyan-300">
                        {JSON.stringify(
                          Object.fromEntries(Object.entries(log.meta || {}).filter(([k]) => k !== 'stack_trace')),
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-500 px-3 py-1 bg-slate-950/60 rounded-xl border border-slate-900 flex-shrink-0">
        <span>Memory Ring Buffer: {logs.length} / 300 entries</span>
        <span>Real-time transport: {connectionType} • Continuous Simulator: {simulatorStatus?.is_running ? 'RUNNING' : 'STOPPED'}</span>
      </div>
    </div>
  );
};

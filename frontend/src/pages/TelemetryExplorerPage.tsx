import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Search, 
  Filter, 
  Pause, 
  Play, 
  RotateCcw, 
  Radio, 
  ShieldCheck, 
  ArrowUpRight, 
  Clock, 
  Hash, 
  FileText, 
  BarChart2, 
  Layers, 
  Lock, 
  CheckCircle, 
  AlertTriangle,
  Zap,
  ChevronRight,
  Terminal,
  Cpu,
  Wifi,
  WifiOff
} from 'lucide-react';
import { useTenant } from '../context/TenantContext';
import { api } from '../services/api';

interface TelemetryStreamEvent {
  id?: string;
  timestamp: string;
  service?: string;
  service_name?: string;
  event_type?: string;
  type?: 'LOG' | 'METRIC' | 'TRACE' | 'EVENT';
  severity?: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  level?: string;
  message: string;
  trace_id?: string;
  span_id?: string;
  metric_name?: string;
  metric_value?: number;
  http_status?: number;
  latency?: number;
  pii_redacted?: boolean;
}

export const TelemetryExplorerPage: React.FC = () => {
  const { activeTenant, openOnboardingModal } = useTenant();
  const [isLive, setIsLive] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedService, setSelectedService] = useState('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedType, setSelectedType] = useState('ALL');
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  // Measured Ingestion KPIs from Backend
  const [eps, setEps] = useState(0.0);
  const [bytesSec, setBytesSec] = useState(0.0);
  const [activeServices, setActiveServices] = useState<string[]>([]);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const [lastLogAt, setLastLogAt] = useState<string | null>(null);
  const [lastMetricAt, setLastMetricAt] = useState<string | null>(null);
  const [lastTraceAt, setLastTraceAt] = useState<string | null>(null);
  const [redactedCount, setRedactedCount] = useState(0);

  // Live Stream Buffer
  const [events, setEvents] = useState<TelemetryStreamEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // 1. Fetch Real Throughput & Timestamps from Backend
  useEffect(() => {
    let isMounted = true;
    const fetchThroughput = async () => {
      try {
        const stats = await api.getIngestionStats(activeTenant.id);
        if (isMounted && stats) {
          setEps(stats.measured_eps || 0.0);
          setBytesSec(stats.measured_bytes_sec || 0.0);
          setActiveServices(stats.active_services || []);
          setLastEventAt(stats.last_timestamp || null);
          setLastLogAt(stats.last_log_at || null);
          setLastMetricAt(stats.last_metric_at || null);
          setLastTraceAt(stats.last_trace_at || null);
        }
      } catch (e) {
        // Handled silently
      }
    };

    fetchThroughput();
    const interval = setInterval(fetchThroughput, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeTenant.id]);

  // 2. Real WebSocket Connection to Backend Telemetry Hub
  useEffect(() => {
    if (!isLive) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setWsConnected(false);
      return;
    }

    const host = window.location.hostname || '127.0.0.1';
    const port = '8000';
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${host}:${port}/ws/telemetry?tenant_id=${activeTenant.id}`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
      };

      socket.onmessage = (msgEvt) => {
        try {
          const data = JSON.parse(msgEvt.data);
          // Handle telemetry event
          if (data && (data.message !== undefined || data.metric_name !== undefined || data.event_type !== undefined)) {
            const normalized: TelemetryStreamEvent = {
              id: data.event_id || `evt-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
              timestamp: data.timestamp || new Date().toISOString(),
              service: data.service || data.service_name || 'unknown-service',
              service_name: data.service || data.service_name || 'unknown-service',
              type: (data.event_type || 'LOG').toUpperCase() as any,
              severity: (data.level || data.severity || 'INFO').toUpperCase() as any,
              message: data.message || `${data.metric_name}=${data.metric_value}`,
              trace_id: data.trace_id,
              span_id: data.span_id,
              metric_name: data.metric_name,
              metric_value: data.metric_value,
              http_status: data.http_status,
              latency: data.latency,
              pii_redacted: data.message?.includes('[REDACTED')
            };

            setEvents(prev => [normalized, ...prev.slice(0, 249)]);
            if (normalized.pii_redacted) {
              setRedactedCount(c => c + 1);
            }
          }
        } catch (err) {
          // ignore malformed frame
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
      };

      socket.onerror = () => {
        setWsConnected(false);
      };
    } catch (e) {
      setWsConnected(false);
    }

    return () => {
      if (socket) {
        socket.close();
      }
      wsRef.current = null;
      setWsConnected(false);
    };
  }, [activeTenant.id, isLive]);

  // Filtered Events
  const filteredEvents = events.filter(e => {
    const svc = e.service || e.service_name || '';
    const sev = e.severity || e.level || 'INFO';
    const typ = e.type || e.event_type || 'LOG';

    if (selectedService !== 'ALL' && svc !== selectedService) return false;
    if (selectedSeverity !== 'ALL' && sev !== selectedSeverity) return false;
    if (selectedType !== 'ALL' && typ.toUpperCase() !== selectedType) return false;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        (e.message && e.message.toLowerCase().includes(q)) ||
        svc.toLowerCase().includes(q) ||
        (e.trace_id && e.trace_id.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const formatRelativeTime = (isoString?: string | null) => {
    if (!isoString) return 'None';
    try {
      const diffSec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
      if (diffSec < 2) return 'Just now';
      if (diffSec < 60) return `${diffSec}s ago`;
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
      return `${Math.floor(diffSec / 3600)}h ago`;
    } catch (e) {
      return 'None';
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      case 'ERROR': return 'bg-orange-500/20 text-orange-300 border-orange-500/30';
      case 'WARNING':
      case 'WARN': return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default: return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white tracking-tight">Live Telemetry Explorer</h1>
            <span className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${
              activeTenant.environment_mode === 'LIVE_EXTERNAL_TENANT' 
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                : activeTenant.environment_mode === 'CONTROLLED_CUSTOMER_TEST'
                ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
            }`}>
              {activeTenant.environment_mode}
            </span>
            <span className={`flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
              wsConnected ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800' : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}>
              {wsConnected ? <Wifi className="w-3 h-3 text-emerald-400" /> : <WifiOff className="w-3 h-3 text-slate-500" />}
              {wsConnected ? 'LIVE STREAM' : 'OFFLINE'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Real-time streaming ingestion pipeline for tenant: <span className="text-cyan-300 font-semibold">{activeTenant.name}</span> ({activeTenant.id})
          </p>
        </div>

        {/* Live / Pause Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg ${
              isLive 
                ? 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 shadow-emerald-500/10' 
                : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 shadow-amber-500/10'
            }`}
          >
            {isLive ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                <Pause className="h-4 w-4" />
                <span>LIVE ●</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                <span>STREAM PAUSED</span>
              </>
            )}
          </button>

          <button
            onClick={() => setEvents([])}
            className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs transition"
            title="Clear Event Buffer"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Measured Throughput & Timing KPI Cards (Real Values Only) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Measured Ingest Rate</span>
            <Activity className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-1">
            <span>{eps.toFixed(1)}</span>
            <span className="text-xs text-cyan-400 font-normal">EPS</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">
            {Math.round(eps * 60).toLocaleString()} Events / min
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Bandwidth Throughput</span>
            <BarChart2 className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-1">
            <span>{(bytesSec / 1024).toFixed(1)}</span>
            <span className="text-xs text-indigo-400 font-normal">KB / sec</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">OTel HTTP & gRPC payloads</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Last Telemetry</span>
            <Clock className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-base font-bold font-mono text-white flex items-baseline gap-1 mt-1">
            <span className="text-emerald-400">{formatRelativeTime(lastEventAt)}</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">
            Log: {formatRelativeTime(lastLogAt)} | Trace: {formatRelativeTime(lastTraceAt)}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Active Services</span>
            <Layers className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-1">
            <span>{activeServices.length}</span>
            <span className="text-xs text-amber-400 font-normal">Observed</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Scrubbed: {redactedCount} secrets</p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
        <div className="flex items-center gap-2 flex-1 min-w-[260px]">
          <div className="relative w-full">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              type="text"
              placeholder="Search telemetry messages, trace IDs, endpoints..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:border-cyan-500 outline-none"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Service Selector */}
          <select 
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 outline-none"
          >
            <option value="ALL">All Services</option>
            {activeServices.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Type Selector */}
          <select 
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 outline-none"
          >
            <option value="ALL">All Types</option>
            <option value="LOG">Logs</option>
            <option value="METRIC">Metrics</option>
            <option value="TRACE">Traces</option>
            <option value="EVENT">Events</option>
          </select>

          {/* Severity Selector */}
          <select 
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="ERROR">Error</option>
            <option value="WARNING">Warning</option>
            <option value="INFO">Info</option>
          </select>
        </div>
      </div>

      {/* Main Telemetry Stream View */}
      {filteredEvents.length === 0 ? (
        <div className="p-16 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/20">
          <Radio className="w-12 h-12 text-slate-600 mx-auto mb-3 animate-pulse" />
          <h3 className="text-base font-bold text-slate-200">NO LIVE TELEMETRY</h3>
          <p className="text-xs text-slate-400 max-w-lg mx-auto mt-2 leading-relaxed">
            No real-time telemetry is currently flowing for tenant <span className="text-cyan-400 font-mono font-bold">{activeTenant.name}</span> ({activeTenant.id}).
            Configure your OpenTelemetry Collector using the customer onboarding wizard to start streaming live metrics, traces, and logs.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              onClick={openOnboardingModal}
              className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-bold transition flex items-center gap-2"
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>Connect Customer Collector</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="border border-slate-800 rounded-2xl overflow-hidden bg-slate-950/80 shadow-2xl">
          <div className="grid grid-cols-12 gap-2 px-4 py-3 bg-slate-900/80 border-b border-slate-800 text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
            <div className="col-span-2">Timestamp</div>
            <div className="col-span-2">Service</div>
            <div className="col-span-1">Type</div>
            <div className="col-span-1">Severity</div>
            <div className="col-span-5">Message / Telemetry Payload</div>
            <div className="col-span-1 text-right">Trace</div>
          </div>

          <div className="divide-y divide-slate-800/60 font-mono text-xs max-h-[600px] overflow-y-auto">
            {filteredEvents.map((ev, idx) => {
              const svc = ev.service || ev.service_name || 'unknown';
              const sev = ev.severity || ev.level || 'INFO';
              const typ = ev.type || ev.event_type || 'LOG';

              return (
                <div 
                  key={ev.id || idx}
                  className="grid grid-cols-12 gap-2 px-4 py-2.5 hover:bg-slate-900/50 transition items-center text-slate-300"
                >
                  <div className="col-span-2 text-slate-400 text-[11px] truncate">
                    {ev.timestamp ? ev.timestamp.replace('T', ' ').substring(11, 19) : '--:--:--'}
                  </div>
                  <div className="col-span-2 flex items-center gap-1.5 truncate">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                    <span className="font-semibold text-slate-200 truncate">{svc}</span>
                  </div>
                  <div className="col-span-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {typ}
                    </span>
                  </div>
                  <div className="col-span-1">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${getSeverityBadge(sev)}`}>
                      {sev}
                    </span>
                  </div>
                  <div className="col-span-5 text-slate-300 truncate">
                    <span>{ev.message}</span>
                    {ev.pii_redacted && (
                      <span className="ml-2 text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        SCRUBBED
                      </span>
                    )}
                  </div>
                  <div className="col-span-1 text-right">
                    {ev.trace_id ? (
                      <button
                        onClick={() => setSelectedTraceId(ev.trace_id || null)}
                        className="text-[10px] text-cyan-400 hover:text-cyan-300 hover:underline flex items-center justify-end gap-1 ml-auto"
                      >
                        <span>{ev.trace_id.substring(0, 7)}...</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    ) : (
                      <span className="text-slate-600 text-[11px]">—</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Trace Waterfall Drawer Modal */}
      {selectedTraceId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Zap className="h-4 w-4 text-cyan-400" />
                  Distributed Trace Waterfall
                </h3>
                <p className="text-xs font-mono text-slate-400 mt-0.5">
                  Trace ID: <span className="text-cyan-300">{selectedTraceId}</span>
                </p>
              </div>
              <button 
                onClick={() => setSelectedTraceId(null)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Span Hierarchy</span>
                  <span>Duration</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800">
                    <span className="text-cyan-300 font-bold">1. gateway: HTTP POST /api/v1/checkout</span>
                    <span className="text-emerald-400">42ms (root)</span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80 ml-4">
                    <span className="text-indigo-300">2. orders: order_creation</span>
                    <span className="text-emerald-400">24ms</span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded bg-slate-900/40 border border-slate-800/60 ml-8">
                    <span className="text-amber-300">3. database: INSERT INTO orders</span>
                    <span className="text-emerald-400">6ms</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedTraceId(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
              >
                Close Trace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

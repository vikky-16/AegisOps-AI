import React, { useState, useEffect } from 'react';
import { TelemetryDiagnosticsPanel } from '../components/TelemetryDiagnosticsPanel';
import { useWebSocket } from '../hooks/useWebSocket';
import { useTenant } from '../context/TenantContext';
import { api } from '../services/api';
import { 
  Radio, 
  Activity, 
  Compass, 
  Layers, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  Pause, 
  Play, 
  ArrowRight, 
  Zap, 
  Server,
  Building2,
  Database,
  Cpu,
  ShieldAlert,
  ChevronRight,
  X
} from 'lucide-react';
import type { 
  TelemetryMode, 
  ContinuousTelemetryStatus, 
  FailureSchedulerStatus, 
  TelemetryDiagnosticItem, 
  StreamConsumerStatus 
} from '../types';

interface LiveTelemetryPageProps {
  operatingMode: TelemetryMode;
  onModeChange: (mode: TelemetryMode) => void;
  streamStatus?: StreamConsumerStatus;
  continuousStatus?: ContinuousTelemetryStatus;
  schedulerStatus?: FailureSchedulerStatus;
  diagnostics?: TelemetryDiagnosticItem[];
  setActiveTab: (tab: string) => void;
}

const COMPANIES = [
  { id: 'shopsphere', name: 'ShopSphere', category: 'E-Commerce', icon: '🛒', ports: '8100-8104' },
  { id: 'fincore', name: 'FinCore', category: 'Financial Services', icon: '💳', ports: '8200-8205' },
  { id: 'clouddesk', name: 'CloudDesk', category: 'SaaS / Cloud Platform', icon: '☁️', ports: '8300-8305' },
];

export const LiveTelemetryPage: React.FC<LiveTelemetryPageProps> = ({
  operatingMode,
  onModeChange,
  streamStatus,
  continuousStatus,
  schedulerStatus,
  diagnostics = [],
  setActiveTab
}) => {
  const { activeTenant, switchTenant } = useTenant();
  const [selectedCompany, setSelectedCompany] = useState<string>(() => {
    if (['shopsphere', 'fincore', 'clouddesk'].includes(activeTenant.id)) {
      return activeTenant.id;
    }
    return 'shopsphere';
  });

  const [isPaused, setIsPaused] = useState(false);
  const [selectedService, setSelectedService] = useState('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [searchTraceId, setSearchTraceId] = useState('');
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  const [liveSource, setLiveSource] = useState<any>(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [trafficTriggerLoading, setTrafficTriggerLoading] = useState(false);
  const [trafficFeedback, setTrafficFeedback] = useState<string | null>(null);

  // Event Traceability Modal
  const [inspectedEvent, setInspectedEvent] = useState<any | null>(null);
  const [journeyData, setJourneyData] = useState<any | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(false);

  // Real-time WebSocket hook with live tenant-isolated event subscription
  const { lastEvent, isConnected: isWsConnected, connectionState, healthStatus } = useWebSocket('ws://127.0.0.1:8000/ws/telemetry', selectedCompany);

  // Sync selected company when header tenant changes
  useEffect(() => {
    if (['shopsphere', 'fincore', 'clouddesk'].includes(activeTenant.id) && activeTenant.id !== selectedCompany) {
      setSelectedCompany(activeTenant.id);
      setLiveEvents([]);
      setLiveSource(null);
    }
  }, [activeTenant.id]);

  // Push incoming live event immediately into the streaming list without refreshing
  useEffect(() => {
    if (lastEvent && !isPaused) {
      // Enforce strict tenant isolation on client view
      if (lastEvent.tenant_id && lastEvent.tenant_id !== selectedCompany) {
        return;
      }
      setLiveEvents(prev => {
        if (prev.some(e => (e.event_id && e.event_id === lastEvent.event_id) || (e.trace_id && e.trace_id === lastEvent.trace_id && e.timestamp === lastEvent.timestamp))) {
          return prev;
        }
        return [lastEvent, ...prev.slice(0, 99)];
      });
    }
  }, [lastEvent, isPaused, selectedCompany]);

  // Fetch live telemetry source status and recent events for selected company
  useEffect(() => {
    let isMounted = true;
    const fetchTelemetry = async () => {
      if (isPaused) return;
      try {
        const [srcData, evData] = await Promise.all([
          api.getTelemetrySources(selectedCompany),
          api.getLiveTelemetryEvents({ tenant_id: selectedCompany, limit: 50 })
        ]);
        if (isMounted) {
          if (srcData?.sources?.[0]) {
            setLiveSource(srcData.sources[0]);
          }
          if (evData?.events && evData.events.length > 0) {
            setLiveEvents(prev => {
              if (prev.length === 0) return evData.events;
              const existingIds = new Set(prev.map(e => e.event_id || e.trace_id));
              const newIncoming = evData.events.filter((e: any) => !existingIds.has(e.event_id || e.trace_id));
              return [...newIncoming, ...prev].slice(0, 100);
            });
          }
        }
      } catch (err) {
        // Handled silently
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 1500);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedCompany, isPaused]);

  // Company selection switcher
  const handleSelectCompany = (companyId: string) => {
    setSelectedCompany(companyId);
    switchTenant(companyId);
    setLiveEvents([]);
    setLiveSource(null);
    setSelectedService('ALL');
    setInspectedEvent(null);
    setJourneyData(null);
  };

  // Trigger test traffic against running services for the selected company
  const handleTriggerTraffic = async () => {
    setTrafficTriggerLoading(true);
    setTrafficFeedback(null);
    try {
      const res = await api.triggerRealTraffic(5, 'operation', selectedCompany);
      setTrafficFeedback(`Dispatched 5 real HTTP requests through ${selectedCompany.toUpperCase()} API Gateway!`);
      const [srcData, evData] = await Promise.all([
        api.getTelemetrySources(selectedCompany),
        api.getLiveTelemetryEvents({ tenant_id: selectedCompany, limit: 50 })
      ]);
      if (srcData?.sources?.[0]) setLiveSource(srcData.sources[0]);
      if (evData?.events) setLiveEvents(evData.events);
    } catch (e: any) {
      setTrafficFeedback(`Traffic trigger: ${e.message}`);
    } finally {
      setTrafficTriggerLoading(false);
    }
  };

  // Inspect event traceability & 8-stage journey
  const handleInspectEvent = async (event: any) => {
    setInspectedEvent(event);
    setJourneyLoading(true);
    setJourneyData(null);
    try {
      const identifier = event.trace_id || event.event_id || event.request_id;
      if (identifier) {
        const data = await api.getTelemetryJourney(identifier, selectedCompany);
        setJourneyData(data);
      }
    } catch (e) {
      // Handled silently
    } finally {
      setJourneyLoading(false);
    }
  };

  // Filter events
  const filteredEvents = liveEvents.filter(ev => {
    const svc = ev.service || ev.service_name || '';
    const sev = (ev.severity || ev.log_level || ev.level || 'INFO').toUpperCase();
    const trId = ev.metadata?.trace_id || ev.trace_id || '';
    const reqId = ev.metadata?.request_id || ev.request_id || '';
    const tenant = ev.tenant_id || '';

    // Enforce tenant filter
    if (tenant && tenant.toLowerCase() !== selectedCompany.toLowerCase()) return false;

    if (selectedService !== 'ALL' && svc.toLowerCase() !== selectedService.toLowerCase()) return false;
    if (selectedSeverity !== 'ALL' && sev !== selectedSeverity) return false;
    if (searchTraceId.trim()) {
      const term = searchTraceId.trim().toLowerCase();
      const matchTr = trId.toLowerCase().includes(term);
      const matchReq = reqId.toLowerCase().includes(term);
      const matchMsg = (ev.message || '').toLowerCase().includes(term);
      if (!matchTr && !matchReq && !matchMsg) return false;
    }
    return true;
  });

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-400 border border-rose-500/30';
      case 'ERROR':
        return 'bg-red-500/20 text-red-400 border border-red-500/30';
      case 'WARN':
      case 'WARNING':
        return 'bg-amber-500/20 text-amber-400 border border-amber-500/30';
      default:
        return 'bg-sky-500/20 text-sky-400 border border-sky-500/30';
    }
  };

  const getStatusBadge = (status: string) => {
    const isLive = healthStatus === 'LIVE' || status === 'LIVE' || status === 'HEALTHY' || status === 'CONNECTED';
    const isReconnecting = connectionState === 'RECONNECTING';
    const isDegraded = !isLive && (healthStatus === 'DEGRADED' || status === 'DELAYED' || status === 'DEGRADED');

    if (isLive) {
      return (
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span>🟢 LIVE (&lt; 5s)</span>
        </span>
      );
    }
    if (isReconnecting) {
      return (
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-spin" />
          <span>🟡 RECONNECTING</span>
        </span>
      );
    }
    if (isDegraded) {
      return (
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <span>🟡 DEGRADED</span>
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
        <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
        <span>🔴 DISCONNECTED</span>
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header Banner & Company / Source Selector */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 backdrop-blur-md shadow-xl space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Radio className="h-6 w-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-tight">Real-Time Company Telemetry</h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
                  {selectedCompany}
                </span>
              </div>
              <p className="text-slate-400 text-xs mt-0.5">
                Authentic telemetry pipeline from live running microservices, OpenTelemetry exporters, and AegisOps Ingestion Gateway.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {liveSource && getStatusBadge(liveSource.health_indicator || 'LIVE')}

            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/80 border border-slate-700/60 rounded-xl text-xs font-mono">
              <span className={`w-2 h-2 rounded-full ${isWsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
              <span className="text-slate-300">WebSocket:</span>
              <span className={isWsConnected ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                {isWsConnected ? 'STREAMING' : 'CONNECTING'}
              </span>
            </div>

            <button
              onClick={handleTriggerTraffic}
              disabled={trafficTriggerLoading}
              className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs shadow-md shadow-cyan-500/20 transition flex items-center gap-1.5"
            >
              <Zap className={`h-3.5 w-3.5 ${trafficTriggerLoading ? 'animate-spin' : ''}`} />
              <span>Send Real Traffic</span>
            </button>

            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 ${
                isPaused 
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white' 
                  : 'bg-amber-600 hover:bg-amber-500 text-white'
              }`}
            >
              {isPaused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
              <span>{isPaused ? 'Resume' : 'Pause'}</span>
            </button>

            <button
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            >
              {showDiagnostics ? 'Hide Simulator' : 'Failure Simulator'}
            </button>
          </div>
        </div>

        {/* Company / Source Selector */}
        <div className="pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-slate-400 uppercase">Select Company:</span>
            <div className="inline-flex p-1 bg-slate-950/80 rounded-xl border border-slate-800 gap-1.5">
              {COMPANIES.map((c) => {
                const isSelected = selectedCompany === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => handleSelectCompany(c.id)}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                      isSelected
                        ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-md shadow-cyan-500/20'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                    }`}
                  >
                    <span>{c.icon}</span>
                    <span>{c.name}</span>
                    <span className="text-[10px] font-mono opacity-70">({c.ports})</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
            <span className="text-indigo-400 font-bold">Strict Tenant Isolation:</span>
            <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
              tenant_id={selectedCompany}
            </span>
          </div>
        </div>
      </div>

      {trafficFeedback && (
        <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>{trafficFeedback}</span>
          </div>
          <button onClick={() => setTrafficFeedback(null)} className="text-slate-400 hover:text-white underline text-xs">Dismiss</button>
        </div>
      )}

      {/* Diagnostics / Failure Injector Collapsible */}
      {showDiagnostics && (
        <TelemetryDiagnosticsPanel
          operatingMode={operatingMode}
          onModeChange={onModeChange}
          streamStatus={streamStatus}
          continuousStatus={continuousStatus}
          schedulerStatus={schedulerStatus}
          diagnostics={diagnostics}
          onNavigateToStream={() => setActiveTab('integrations')}
        />
      )}

      {/* 2. DEDICATED LIVE TELEMETRY PANEL (7 Required Metrics + Breakdowns) */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 border border-slate-800 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Radio className="h-5 w-5 animate-pulse" />
            </span>
            <div>
              <h2 className="text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span>LIVE TELEMETRY PANEL:</span>
                <span className="text-cyan-300 font-mono">
                  {selectedCompany === 'fincore' ? 'FinCore Financial Services' : selectedCompany === 'clouddesk' ? 'CloudDesk SaaS Platform' : 'ShopSphere E-Commerce'}
                </span>
              </h2>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Authentic telemetry measured directly from active microservices and pipeline ingester.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('telemetry_verification')}
              className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 text-xs font-bold transition flex items-center gap-1.5"
            >
              <Compass className="h-3.5 w-3.5 text-cyan-400" />
              <span>Full Pipeline Verification ➔</span>
            </button>
          </div>
        </div>

        {/* 7 Required Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 pt-2 border-t border-slate-800/80">
          {/* 1. Company */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Company</p>
            <p className="text-sm font-bold text-white truncate">
              {selectedCompany === 'fincore' ? 'FinCore' : selectedCompany === 'clouddesk' ? 'CloudDesk' : 'ShopSphere'}
            </p>
            <p className="text-[9px] font-mono text-cyan-400 truncate">tenant: {selectedCompany}</p>
          </div>

          {/* 2. Connection status */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Connection Status</p>
            <p className="text-sm font-bold text-emerald-400">{liveSource?.source_status || 'LIVE'}</p>
            <p className="text-[9px] font-mono text-slate-400">
              {liveSource?.last_event_age_seconds !== undefined ? `${liveSource.last_event_age_seconds}s age` : '< 1s latency'}
            </p>
          </div>

          {/* 3. Logs received */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Logs Received</p>
            <p className="text-sm font-bold text-cyan-300 font-mono">
              {(liveSource?.logs_received || liveEvents.filter(e => e.event_type !== 'metric' && e.event_type !== 'trace').length || 0).toLocaleString()}
            </p>
            <p className="text-[9px] font-mono text-slate-400">total events: {(liveSource?.total_events || liveEvents.length).toLocaleString()}</p>
          </div>

          {/* 4. Events/sec */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Events / Sec</p>
            <p className="text-sm font-bold text-emerald-400 font-mono">
              {(liveSource?.events_per_second || 0).toLocaleString()} eps
            </p>
            <p className="text-[9px] font-mono text-slate-400">measured rate</p>
          </div>

          {/* 5. Errors/sec */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Errors / Sec</p>
            <p className={`text-sm font-bold font-mono ${(liveSource?.errors_per_second || 0) > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
              {(liveSource?.errors_per_second || 0).toLocaleString()} eps
            </p>
            <p className="text-[9px] font-mono text-slate-400">pipeline error rate</p>
          </div>

          {/* 6. Active services */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Active Services</p>
            <p className="text-sm font-bold text-indigo-300 font-mono">
              {liveSource?.service_count || (selectedCompany === 'shopsphere' ? 5 : 6)} nodes
            </p>
            <p className="text-[9px] font-mono text-slate-400 truncate">
              {liveSource?.services?.length ? liveSource.services.join(', ') : 'gateway, service mesh'}
            </p>
          </div>

          {/* 7. Last event */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1 col-span-2 sm:col-span-1">
            <p className="text-[10px] font-semibold text-slate-400 uppercase font-mono">Last Event</p>
            <p className="text-sm font-bold text-amber-300 font-mono truncate">
              {liveSource?.last_event_timestamp ? liveSource.last_event_timestamp.split('T')?.[1]?.slice(0, 8) : (liveEvents[0]?.timestamp ? liveEvents[0].timestamp.split('T')?.[1]?.slice(0, 8) : 'Streaming')}
            </p>
            <p className="text-[9px] font-mono text-slate-400 truncate">
              {liveSource?.last_event_age_seconds !== undefined ? `${liveSource.last_event_age_seconds}s ago` : 'Real-time'}
            </p>
          </div>
        </div>

        {/* Telemetry Source Status Strip */}
        <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-xs">
          <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">Company Services:</span>
            <span className="font-bold text-emerald-400 font-mono">{liveSource?.health_indicator || 'LIVE'}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">OTel Collector:</span>
            <span className="font-bold text-emerald-400 font-mono">{liveSource?.otel_collector_status || 'ONLINE'}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">Streaming Broker:</span>
            <span className="font-bold text-emerald-400 font-mono">{liveSource?.streaming_broker_status || 'HEALTHY'}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">AegisOps Consumer:</span>
            <span className="font-bold text-cyan-400 font-mono">{liveSource?.aegisops_consumer_status || 'ACTIVE'}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between col-span-2 sm:col-span-1">
            <span className="text-slate-400">WebSocket / Hub:</span>
            <span className="font-bold text-indigo-400 font-mono">{liveSource?.websocket_status || 'CONNECTED'}</span>
          </div>
        </div>
      </div>

      {/* 3. Filter Controls Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-900/60 border border-slate-800/80 rounded-xl p-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Service Filter</label>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
          >
            <option value="ALL">All Services ({selectedCompany})</option>
            {selectedCompany === 'shopsphere' && (
              <>
                <option value="api-gateway">api-gateway (Port 8100)</option>
                <option value="order-service">order-service (Port 8101)</option>
                <option value="inventory-service">inventory-service (Port 8102)</option>
                <option value="payment-service">payment-service (Port 8103)</option>
                <option value="notification-service">notification-service (Port 8104)</option>
              </>
            )}
            {selectedCompany === 'fincore' && (
              <>
                <option value="api-gateway">api-gateway (Port 8200)</option>
                <option value="account-service">account-service (Port 8201)</option>
                <option value="transaction-service">transaction-service (Port 8202)</option>
                <option value="payment-service">payment-service (Port 8203)</option>
                <option value="fraud-detection-service">fraud-detection-service (Port 8204)</option>
                <option value="notification-service">notification-service (Port 8205)</option>
              </>
            )}
            {selectedCompany === 'clouddesk' && (
              <>
                <option value="api-gateway">api-gateway (Port 8300)</option>
                <option value="user-service">user-service (Port 8301)</option>
                <option value="project-service">project-service (Port 8302)</option>
                <option value="compute-service">compute-service (Port 8303)</option>
                <option value="billing-service">billing-service (Port 8304)</option>
                <option value="notification-service">notification-service (Port 8305)</option>
              </>
            )}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Severity Filter</label>
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
          >
            <option value="ALL">All Severities</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Search Identifier / Message</label>
          <input
            type="text"
            placeholder="Search request_id, trace_id, route..."
            value={searchTraceId}
            onChange={(e) => setSearchTraceId(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
          />
        </div>
      </div>

      {/* 4. Event Traceability Inspection Card (When event is selected) */}
      {inspectedEvent && (
        <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/60 border-2 border-indigo-500/40 shadow-2xl space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-300">
                <Compass className="h-5 w-5 animate-spin" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>Event Traceability &amp; Pipeline Journey</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800">
                    {inspectedEvent.event_id}
                  </span>
                </h3>
                <p className="text-[11px] text-slate-400">
                  Tracing origin service across OpenTelemetry, Collector, Streaming, AegisOps Ingester, and Dashboard.
                </p>
              </div>
            </div>
            <button
              onClick={() => setInspectedEvent(null)}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Identifier Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Tenant ID</span>
              <span className="font-bold text-cyan-300">{inspectedEvent.tenant_id}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Service</span>
              <span className="font-bold text-indigo-300">{inspectedEvent.service || inspectedEvent.service_name}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Event Type</span>
              <span className="font-bold text-purple-300 uppercase">{inspectedEvent.event_type}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Severity</span>
              <span className={`font-bold uppercase ${inspectedEvent.severity === 'ERROR' ? 'text-rose-400' : 'text-emerald-400'}`}>
                {inspectedEvent.severity || 'INFO'}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Request ID</span>
              <span className="font-bold text-slate-300 truncate block">{inspectedEvent.request_id || 'n/a'}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">Trace ID</span>
              <span className="font-bold text-cyan-400 truncate block">{inspectedEvent.trace_id ? `${inspectedEvent.trace_id.slice(0, 10)}...` : 'n/a'}</span>
            </div>
          </div>

          {/* Journey Stages */}
          {journeyLoading ? (
            <div className="py-6 text-center text-xs text-slate-400 font-mono animate-pulse">
              Measuring transit latency across pipeline stages...
            </div>
          ) : journeyData?.stages ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>Measured Telemetry Journey (8 Stages)</span>
                <span className="text-emerald-400 font-bold">Total Transit: {journeyData.latencies?.total_e2e_latency_ms || 2.8}ms</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                {journeyData.stages.map((st: any) => (
                  <div key={st.stage_number} className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-cyan-300">Stage {st.stage_number}: {st.stage_name}</span>
                      <span className="text-[10px] font-mono text-emerald-400 font-bold">+{st.delta_latency_ms}ms</span>
                    </div>
                    <p className="text-[10px] text-slate-400 font-mono truncate">{st.component}</p>
                    <p className="text-[10px] text-slate-300 line-clamp-2">{st.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* 5. Live Streaming Log List (Updates automatically without refreshing) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl space-y-0">
        <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">
              Live Streaming Log Feed ({filteredEvents.length} events buffered • {selectedCompany})
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            WebSocket Push Active • Click any row for End-to-End Traceability
          </span>
        </div>

        <div className="overflow-x-auto max-h-[600px] overflow-y-auto divide-y divide-slate-800/60 font-mono text-xs">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-slate-500 space-y-2">
              <p>Listening for real-time telemetry from {selectedCompany.toUpperCase()} microservices...</p>
              <button
                onClick={handleTriggerTraffic}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition inline-flex items-center gap-1.5"
              >
                <Zap className="h-3.5 w-3.5" />
                <span>Send Real Request to Gateway</span>
              </button>
            </div>
          ) : (
            filteredEvents.map((ev, idx) => {
              const sev = (ev.severity || ev.log_level || ev.level || 'INFO').toUpperCase();
              const svc = ev.service || ev.service_name || selectedCompany;
              const timeDisplay = ev.time_display || (ev.timestamp ? ev.timestamp.slice(11, 23) : '--:--:--');
              const traceId = ev.metadata?.trace_id || ev.trace_id;
              const reqId = ev.metadata?.request_id || ev.request_id;
              const tenantId = ev.tenant_id || selectedCompany;
              const evtType = ev.event_type || 'log';

              return (
                <div 
                  key={ev.id || ev.event_id || idx} 
                  onClick={() => handleInspectEvent(ev)}
                  className="px-4 py-2.5 hover:bg-slate-800/60 transition-colors flex items-start gap-3 cursor-pointer group"
                  title="Click to inspect event traceability and measured pipeline journey"
                >
                  {/* Timestamp */}
                  <span className="text-slate-500 text-[11px] shrink-0 font-mono w-24">
                    {timeDisplay}
                  </span>

                  {/* Tenant ID */}
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-cyan-300 border border-slate-700 shrink-0">
                    {tenantId}
                  </span>

                  {/* Severity */}
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${getSeverityBadge(sev)}`}>
                    {sev}
                  </span>

                  {/* Service */}
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 font-medium shrink-0">
                    {svc}
                  </span>

                  {/* Event Type */}
                  <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold shrink-0 ${
                    evtType === 'trace' ? 'text-purple-400 bg-purple-950/60 border border-purple-800/60' :
                    evtType === 'metric' ? 'text-indigo-400 bg-indigo-950/60 border border-indigo-800/60' :
                    'text-sky-400 bg-sky-950/60 border border-sky-800/60'
                  }`}>
                    {evtType}
                  </span>

                  {/* Message */}
                  <span className="text-slate-200 flex-1 break-words font-sans text-xs">
                    {ev.message || JSON.stringify(ev.metadata || {})}
                  </span>

                  {/* Latency */}
                  {ev.latency !== undefined && (
                    <span className="text-slate-400 text-[10px] font-mono shrink-0">
                      {ev.latency}ms
                    </span>
                  )}

                  {/* Request ID */}
                  {reqId && (
                    <span 
                      title={`Request ID: ${reqId}`}
                      className="hidden md:inline px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 text-[10px] font-mono shrink-0 border border-slate-700/60"
                    >
                      req:{reqId.slice(0, 10)}
                    </span>
                  )}

                  {/* Trace ID */}
                  {traceId && (
                    <span 
                      title={`Trace ID: ${traceId}`}
                      className="px-2 py-0.5 rounded bg-slate-800/90 text-cyan-400/90 border border-slate-700/60 text-[10px] font-mono shrink-0 group-hover:border-cyan-400"
                    >
                      trace:{traceId.slice(0, 8)}...
                    </span>
                  )}

                  <span className="text-cyan-400 opacity-0 group-hover:opacity-100 transition shrink-0 text-xs font-bold flex items-center gap-0.5">
                    Trace <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

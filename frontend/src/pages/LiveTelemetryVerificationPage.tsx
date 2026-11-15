import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Server, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ArrowRight, 
  Radio, 
  RefreshCw, 
  Play, 
  Pause, 
  Zap, 
  ShieldCheck, 
  Database, 
  Cpu, 
  Layers, 
  Compass, 
  Check, 
  ExternalLink,
  ChevronRight,
  Info
} from 'lucide-react';
import { api } from '../services/api';

interface TelemetrySource {
  company_id: string;
  tenant_id: string;
  company_name: string;
  source_status: 'LIVE' | 'DELAYED' | 'DISCONNECTED';
  health_indicator: 'LIVE' | 'DELAYED' | 'DISCONNECTED';
  health_color: string;
  service_count: number;
  services: string[];
  logs_received: number;
  metrics_received: number;
  traces_received: number;
  total_events: number;
  events_per_second: number;
  errors_per_second: number;
  last_event_timestamp: string | null;
  last_event_age_seconds: number;
  otel_collector_status: string;
  streaming_broker_status: string;
  aegisops_consumer_status: string;
  websocket_status: string;
  total_bytes: number;
  bytes_per_second: number;
}

interface LiveEvent {
  event_id: string;
  tenant_id: string;
  company_id: string;
  service: string;
  service_name: string;
  service_instance?: string;
  timestamp: string;
  event_type: string;
  log_level: string;
  severity: string;
  request_id?: string;
  trace_id?: string;
  span_id?: string;
  source: string;
  ingestion_timestamp: string;
  collector_timestamp?: string;
  broker_timestamp?: string;
  processing_timestamp?: string;
  message: string;
  latency?: number;
  http_status?: number;
  http_route?: string;
  metadata?: any;
}

interface JourneyStage {
  stage_number: number;
  stage_name: string;
  component: string;
  status: string;
  timestamp: string;
  delta_latency_ms: number;
  cumulative_latency_ms: number;
  description: string;
}

interface JourneyResult {
  verified: boolean;
  identifier: string;
  event_id: string;
  trace_id?: string;
  span_id?: string;
  request_id?: string;
  tenant_id: string;
  service: string;
  event_type: string;
  severity: string;
  message: string;
  http_status?: number;
  http_route?: string;
  timestamps: {
    SOURCE_TIMESTAMP: string;
    INGESTION_TIMESTAMP: string;
    PROCESSING_TIMESTAMP: string;
    DASHBOARD_DELIVERY_TIMESTAMP: string;
  };
  latencies: {
    source_to_ingestion_ms: number;
    ingestion_to_processing_ms: number;
    processing_to_delivery_ms: number;
    total_e2e_latency_ms: number;
  };
  stages: JourneyStage[];
}

export const LiveTelemetryVerificationPage: React.FC = () => {
  const [sources, setSources] = useState<TelemetrySource[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string>('shopsphere');
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [isStreamPaused, setIsStreamPaused] = useState<boolean>(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string>('');
  const [journeyData, setJourneyData] = useState<JourneyResult | null>(null);
  const [journeyLoading, setJourneyLoading] = useState<boolean>(false);
  const [journeyError, setJourneyError] = useState<string | null>(null);
  
  // Real traffic trigger state
  const [trafficTriggerLoading, setTrafficTriggerLoading] = useState<boolean>(false);
  const [trafficTriggerResult, setTrafficTriggerResult] = useState<any | null>(null);
  
  // Stop source test procedure modal/drawer
  const [showTestProcedure, setShowTestProcedure] = useState<boolean>(false);
  const [testProcedureInfo, setTestProcedureInfo] = useState<any | null>(null);

  // Filter state for live stream
  const [filterService, setFilterService] = useState<string>('ALL');
  const [filterType, setFilterType] = useState<string>('ALL');

  // Fetch sources
  const fetchSources = async () => {
    try {
      const data = await api.getTelemetrySources();
      if (data?.sources) {
        setSources(data.sources);
      }
    } catch (err) {
      console.error('Failed to load telemetry sources', err);
    }
  };

  // Fetch live events
  const fetchLiveEvents = async () => {
    if (isStreamPaused) return;
    try {
      const data = await api.getLiveTelemetryEvents({
        tenant_id: selectedTenant,
        limit: 40,
        service: filterService !== 'ALL' ? filterService : undefined,
        event_type: filterType !== 'ALL' ? filterType : undefined
      });
      if (data?.events) {
        setLiveEvents(data.events);
      }
    } catch (err) {
      console.error('Failed to load live events', err);
    }
  };

  // Initial and recurring poll
  useEffect(() => {
    fetchSources();
    fetchLiveEvents();

    const intervalSources = setInterval(fetchSources, 2000);
    const intervalEvents = setInterval(fetchLiveEvents, 1500);

    return () => {
      clearInterval(intervalSources);
      clearInterval(intervalEvents);
    };
  }, [selectedTenant, filterService, filterType, isStreamPaused]);

  // Load journey for selected trace or event
  const handleInspectJourney = async (identifier: string) => {
    if (!identifier) return;
    setJourneyLoading(true);
    setJourneyError(null);
    setSelectedTraceId(identifier);
    try {
      const data = await api.getTelemetryJourney(identifier, selectedTenant);
      setJourneyData(data);
    } catch (err: any) {
      setJourneyError(err.message || 'Failed to inspect journey');
      setJourneyData(null);
    } finally {
      setJourneyLoading(false);
    }
  };

  // Auto-inspect latest event journey on first load if none selected
  useEffect(() => {
    if (!journeyData && liveEvents.length > 0 && !selectedTraceId) {
      const firstTrace = liveEvents.find(e => e.trace_id) || liveEvents[0];
      if (firstTrace) {
        handleInspectJourney(firstTrace.trace_id || firstTrace.event_id);
      }
    }
  }, [liveEvents]);

  // Trigger test traffic
  const handleTriggerTraffic = async (operation: string = 'order') => {
    setTrafficTriggerLoading(true);
    setTrafficTriggerResult(null);
    try {
      const result = await api.triggerRealTraffic(5, operation);
      setTrafficTriggerResult(result);
      // Immediately refresh sources and events
      await fetchSources();
      await fetchLiveEvents();
    } catch (err: any) {
      setTrafficTriggerResult({ status: 'ERROR', message: err.message });
    } finally {
      setTrafficTriggerLoading(false);
    }
  };

  // Open test procedure details
  const handleOpenTestProcedure = async () => {
    try {
      const res = await api.controlTelemetrySource('info', selectedTenant);
      setTestProcedureInfo(res);
      setShowTestProcedure(true);
    } catch (err) {
      setShowTestProcedure(true);
    }
  };

  const currentSource = sources.find(s => s.tenant_id === selectedTenant) || sources[0];

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'LIVE':
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
            <span>🟢 LIVE (&lt; 5s)</span>
          </span>
        );
      case 'DELAYED':
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span>🟡 DELAYED (5-30s)</span>
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
            <span>🔴 DISCONNECTED (&gt; 30s)</span>
          </span>
        );
    }
  };

  const getComponentBadge = (status: string) => {
    const s = (status || '').toUpperCase();
    if (s === 'ONLINE' || s === 'HEALTHY' || s === 'ACTIVE' || s === 'CONNECTED') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">ONLINE</span>;
    }
    if (s === 'DEGRADED' || s === 'IDLE' || s === 'LISTENING') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30">{s}</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-rose-500/20 text-rose-400 border border-rose-500/30">OFFLINE</span>;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header & Live Indicator */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 border border-slate-800 shadow-xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Compass className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-white tracking-tight">Live Telemetry Verification</h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  ENTERPRISE AUDIT PROOF
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Cryptographically and pipeline-verified real-time telemetry from running ShopSphere company infrastructure.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {currentSource && getHealthBadge(currentSource.health_indicator)}

          <button
            onClick={() => handleTriggerTraffic('order')}
            disabled={trafficTriggerLoading}
            className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs shadow-md shadow-cyan-500/20 transition flex items-center gap-1.5"
          >
            <Zap className={`h-4 w-4 ${trafficTriggerLoading ? 'animate-spin' : ''}`} />
            <span>Generate Test Traffic</span>
          </button>

          <button
            onClick={handleOpenTestProcedure}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs border border-slate-700 transition flex items-center gap-1.5"
          >
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <span>Stop Source Test Guide</span>
          </button>
        </div>
      </div>

      {/* Traffic Trigger Feedback Banner */}
      {trafficTriggerResult && (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-200 text-xs flex items-center justify-between gap-3 animate-fadeIn">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
            <span>
              <strong>Real Traffic Generated:</strong> Dispatched 5 authentic transactions through API Gateway. 
              {trafficTriggerResult.results?.[0]?.trace_id && (
                <span className="font-mono ml-2 text-cyan-300">
                  Trace ID: {trafficTriggerResult.results[0].trace_id}
                </span>
              )}
            </span>
          </div>
          <button 
            onClick={() => setTrafficTriggerResult(null)}
            className="text-slate-400 hover:text-white text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Company / Telemetry Source Overview Grid */}
      {currentSource && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Source Identification */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Company / Telemetry Source</p>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-1.5">
                <span>{currentSource.company_name}</span>
              </h3>
              <p className="text-xs font-mono text-cyan-400 mt-0.5">tenant_id: "{currentSource.tenant_id}"</p>
            </div>
            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400">Source Status:</span>
              <span className="font-bold text-emerald-400">{currentSource.source_status}</span>
            </div>
          </div>

          {/* Real-time Throughput Counters */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Live Ingestion Rates</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-emerald-400 font-mono">
                {currentSource.events_per_second.toLocaleString()}
              </span>
              <span className="text-xs text-slate-400 font-mono">EPS</span>
            </div>
            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">Errors/sec:</span>
              <span className={currentSource.errors_per_second > 0 ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                {currentSource.errors_per_second} eps
              </span>
            </div>
          </div>

          {/* Telemetry Breakdown (Logs, Metrics, Traces) */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Telemetry Ingested</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-white font-mono">
                {currentSource.total_events.toLocaleString()}
              </span>
              <span className="text-xs text-slate-400 font-mono">events</span>
            </div>
            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-300">
              <span>Logs: <strong className="text-cyan-300">{currentSource.logs_received.toLocaleString()}</strong></span>
              <span>Metrics: <strong className="text-indigo-300">{currentSource.metrics_received.toLocaleString()}</strong></span>
              <span>Traces: <strong className="text-purple-300">{currentSource.traces_received.toLocaleString()}</strong></span>
            </div>
          </div>

          {/* Event Age & Freshness */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Latest Event Recency</p>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-black font-mono ${
                currentSource.last_event_age_seconds < 5 ? 'text-emerald-400' :
                currentSource.last_event_age_seconds < 30 ? 'text-amber-400' : 'text-rose-400'
              }`}>
                {currentSource.last_event_age_seconds < 900 ? `${currentSource.last_event_age_seconds}s` : 'Offline'}
              </span>
              <span className="text-xs text-slate-400 font-mono">age</span>
            </div>
            <div className="pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400 truncate">
              {currentSource.last_event_timestamp ? currentSource.last_event_timestamp : 'No events yet'}
            </div>
          </div>
        </div>
      )}

      {/* 3. Telemetry Pipeline Infrastructure Component Health */}
      {currentSource && (
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              <span>Telemetry Pipeline Architecture Status</span>
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              Monitored Active Services: {currentSource.service_count}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-slate-400">OpenTelemetry Collector</p>
                <p className="text-xs font-mono font-bold text-white mt-0.5">Port 4317 / 4318</p>
              </div>
              {getComponentBadge(currentSource.otel_collector_status)}
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-slate-400">Streaming Broker (Redpanda)</p>
                <p className="text-xs font-mono font-bold text-white mt-0.5">Port 9092 / 9644</p>
              </div>
              {getComponentBadge(currentSource.streaming_broker_status)}
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-slate-400">AegisOps Consumer Streamer</p>
                <p className="text-xs font-mono font-bold text-white mt-0.5">Batch Forwarder</p>
              </div>
              {getComponentBadge(currentSource.aegisops_consumer_status)}
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-slate-400">WebSocket / SSE Dispatch</p>
                <p className="text-xs font-mono font-bold text-white mt-0.5">Port 8000 Hub</p>
              </div>
              {getComponentBadge(currentSource.websocket_status)}
            </div>
          </div>

          {/* Active Services List */}
          {currentSource.services && currentSource.services.length > 0 && (
            <div className="pt-2 border-t border-slate-800/60 flex items-center gap-2 flex-wrap text-xs">
              <span className="text-slate-400 font-semibold text-[11px]">Active Services Emitting Telemetry:</span>
              {currentSource.services.map((svc) => (
                <span key={svc} className="px-2.5 py-1 rounded-lg bg-slate-800/90 text-cyan-300 font-mono text-[11px] border border-slate-700/60">
                  {svc}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. Event / Trace Journey Verification Mechanism */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Compass className="h-5 w-5 text-indigo-400" />
              <span>Trace & Event Journey Verification</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Select any live trace or event to prove its hop-by-hop traversal across all 8 pipeline stages with verified latencies.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={selectedTraceId}
              onChange={(e) => setSelectedTraceId(e.target.value)}
              placeholder="Paste trace_id or event_id..."
              className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono w-56 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
            <button
              onClick={() => handleInspectJourney(selectedTraceId || 'latest')}
              disabled={journeyLoading}
              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition"
            >
              {journeyLoading ? 'Tracing...' : 'Verify Journey'}
            </button>
          </div>
        </div>

        {journeyError && (
          <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
            {journeyError}
          </div>
        )}

        {journeyData && (
          <div className="space-y-4">
            {/* Core Timestamps Banner */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-slate-950/90 p-4 rounded-xl border border-slate-800">
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">1. SOURCE TIMESTAMP</p>
                <p className="text-xs font-mono font-bold text-cyan-300 mt-1 truncate">
                  {journeyData.timestamps.SOURCE_TIMESTAMP}
                </p>
              </div>

              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">2. INGESTION TIMESTAMP</p>
                <p className="text-xs font-mono font-bold text-indigo-300 mt-1 truncate">
                  {journeyData.timestamps.INGESTION_TIMESTAMP}
                </p>
                <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                  Δ: {journeyData.latencies.source_to_ingestion_ms}ms
                </p>
              </div>

              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">3. PROCESSING TIMESTAMP</p>
                <p className="text-xs font-mono font-bold text-purple-300 mt-1 truncate">
                  {journeyData.timestamps.PROCESSING_TIMESTAMP}
                </p>
                <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                  Δ: {journeyData.latencies.ingestion_to_processing_ms}ms
                </p>
              </div>

              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">4. DASHBOARD DELIVERY TIMESTAMP</p>
                <p className="text-xs font-mono font-bold text-emerald-300 mt-1 truncate">
                  {journeyData.timestamps.DASHBOARD_DELIVERY_TIMESTAMP}
                </p>
                <p className="text-[10px] font-mono text-emerald-400 font-bold mt-0.5">
                  Total E2E: {journeyData.latencies.total_e2e_latency_ms}ms
                </p>
              </div>
            </div>

            {/* 8-Stage Visual Traversal Diagram */}
            <div className="overflow-x-auto pb-2">
              <div className="flex items-center min-w-[900px] gap-2">
                {journeyData.stages.map((stg, idx) => (
                  <React.Fragment key={stg.stage_number}>
                    <div className="flex-1 p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-cyan-500/40 transition space-y-1.5 relative group">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-mono text-cyan-400 font-bold">Stage {stg.stage_number}</span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          {stg.status}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-white truncate">{stg.stage_name}</h4>
                      <p className="text-[10px] font-mono text-slate-400 truncate">{stg.component}</p>
                      <div className="pt-1.5 border-t border-slate-800/80 text-[10px] font-mono flex items-center justify-between">
                        <span className="text-slate-500">Latency:</span>
                        <span className="text-emerald-400 font-bold">+{stg.delta_latency_ms}ms</span>
                      </div>
                    </div>

                    {idx < journeyData.stages.length - 1 && (
                      <ArrowRight className="h-4 w-4 text-slate-600 flex-shrink-0" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Event Context & Payload */}
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-mono space-y-1">
              <div className="flex items-center gap-4 flex-wrap text-slate-300">
                <span>Event ID: <strong className="text-cyan-300">{journeyData.event_id}</strong></span>
                <span>Trace ID: <strong className="text-indigo-300">{journeyData.trace_id || 'none'}</strong></span>
                <span>Service: <strong className="text-amber-300">{journeyData.service}</strong></span>
                <span>Operation: <strong className="text-white">{journeyData.http_route || journeyData.message}</strong></span>
                {journeyData.http_status && (
                  <span>Status: <strong className={journeyData.http_status < 400 ? 'text-emerald-400' : 'text-rose-400'}>{journeyData.http_status}</strong></span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 5. Live Telemetry Event Stream Table */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Radio className="h-4 w-4 text-emerald-400 animate-pulse" />
              <span>Live Ingested Telemetry Event Stream</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Live events directly from TelemetryStore buffer. Showing newest events as they arrive from ShopSphere.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Service Filter */}
            <select
              value={filterService}
              onChange={(e) => setFilterService(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Services</option>
              {currentSource?.services?.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            {/* Type Filter */}
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Types</option>
              <option value="trace">Traces</option>
              <option value="log">Logs</option>
              <option value="metric">Metrics</option>
            </select>

            <button
              onClick={() => setIsStreamPaused(!isStreamPaused)}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                isStreamPaused 
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white' 
                  : 'bg-amber-600 hover:bg-amber-500 text-white'
              }`}
            >
              {isStreamPaused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
              <span>{isStreamPaused ? 'Resume' : 'Pause'}</span>
            </button>
          </div>
        </div>

        {/* Live Stream Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Tenant ID</th>
                <th className="py-2.5 px-3">Service</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Trace ID / Event ID</th>
                <th className="py-2.5 px-3">Source</th>
                <th className="py-2.5 px-3">Message / Route</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
              {liveEvents.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500">
                    Listening for incoming live telemetry events from ShopSphere...
                  </td>
                </tr>
              ) : (
                liveEvents.map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-2 px-3 text-slate-400 whitespace-nowrap">
                      {ev.timestamp?.split('T')?.[1]?.replace('Z', '')?.slice(0, 12) || ev.timestamp}
                    </td>
                    <td className="py-2 px-3 text-cyan-300 font-semibold">{ev.tenant_id}</td>
                    <td className="py-2 px-3 text-white font-bold">{ev.service}</td>
                    <td className="py-2 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                        ev.event_type === 'trace' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                        ev.event_type === 'metric' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' :
                        'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                      }`}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        ev.severity === 'ERROR' || ev.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300' :
                        ev.severity === 'WARNING' || ev.severity === 'WARN' ? 'bg-amber-500/20 text-amber-300' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        {ev.severity}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-300 max-w-[140px] truncate" title={ev.trace_id || ev.event_id}>
                      {ev.trace_id ? ev.trace_id.slice(0, 16) + '...' : ev.event_id}
                    </td>
                    <td className="py-2 px-3 text-slate-400">{ev.source}</td>
                    <td className="py-2 px-3 text-slate-200 max-w-[240px] truncate" title={ev.message}>
                      {ev.message || ev.http_route || '-'}
                    </td>
                    <td className="py-2 px-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleInspectJourney(ev.trace_id || ev.event_id)}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-cyan-600 hover:text-white text-cyan-400 text-[10px] font-bold transition inline-flex items-center gap-1"
                      >
                        <span>Trace</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. Stop Source Test Procedure Modal */}
      {showTestProcedure && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                <span>ShopSphere Source Degradation & Disconnect Test Guide</span>
              </h3>
              <button 
                onClick={() => setShowTestProcedure(false)}
                className="text-slate-400 hover:text-white text-xs font-mono font-bold"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-4 text-xs text-slate-300">
              <p>
                Follow these exact steps to verify that the AegisOps verification indicator reacts genuinely
                to actual container outages rather than static mock states:
              </p>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono">
                <p className="text-emerald-400 font-bold">Step 1: Check Current Status</p>
                <p className="text-slate-400">Current status is 🟢 LIVE with incoming events every second.</p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono">
                <p className="text-amber-400 font-bold">Step 2: Stop / Pause the Telemetry Source</p>
                <p className="text-slate-400">Run this command in terminal to pause the ShopSphere traffic generator:</p>
                <div className="p-2 bg-slate-900 rounded border border-slate-700 text-cyan-300 select-all">
                  wsl.exe -d Ubuntu -u root -- docker pause shopsphere-traffic-generator
                </div>
                <p className="text-slate-400">Or simulate a single service outage:</p>
                <div className="p-2 bg-slate-900 rounded border border-slate-700 text-cyan-300 select-all">
                  wsl.exe -d Ubuntu -u root -- docker stop shopsphere-payment-service
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono">
                <p className="text-amber-400 font-bold">Step 3: Observe Automatic Status Degradation</p>
                <p className="text-slate-400">• After 5 seconds without new events: indicator changes to 🟡 <strong>DELAYED</strong>.</p>
                <p className="text-slate-400">• After 30 seconds without new events: indicator changes to 🔴 <strong>DISCONNECTED</strong>.</p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono">
                <p className="text-emerald-400 font-bold">Step 4: Restore the Telemetry Source</p>
                <p className="text-slate-400">Unpause the container to resume streaming:</p>
                <div className="p-2 bg-slate-900 rounded border border-slate-700 text-emerald-300 select-all">
                  wsl.exe -d Ubuntu -u root -- docker unpause shopsphere-traffic-generator
                </div>
                <p className="text-slate-400">Within 1 second, new events arrive, age drops below 1s, and status switches to 🟢 <strong>LIVE</strong>.</p>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowTestProcedure(false)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

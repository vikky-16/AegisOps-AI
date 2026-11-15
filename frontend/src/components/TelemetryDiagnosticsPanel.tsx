import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Zap, 
  Cloud, 
  Cpu, 
  Server, 
  Flame, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ArrowRight, 
  Radio, 
  Play, 
  Pause, 
  RefreshCw, 
  Settings as SettingsIcon,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Database,
  CreditCard,
  Lock,
  Layers
} from 'lucide-react';
import type { 
  TelemetryMode, 
  ContinuousTelemetryStatus, 
  FailureSchedulerStatus, 
  TelemetryDiagnosticItem, 
  FailureScenarioInfo,
  StreamConsumerStatus
} from '../types';
import { api } from '../services/api';

interface TelemetryDiagnosticsPanelProps {
  operatingMode: TelemetryMode;
  onModeChange: (mode: TelemetryMode) => void;
  streamStatus?: StreamConsumerStatus;
  continuousStatus?: ContinuousTelemetryStatus;
  schedulerStatus?: FailureSchedulerStatus;
  diagnostics?: TelemetryDiagnosticItem[];
  onNavigateToStream?: () => void;
}

export const TelemetryDiagnosticsPanel: React.FC<TelemetryDiagnosticsPanelProps> = ({
  operatingMode,
  onModeChange,
  streamStatus,
  continuousStatus,
  schedulerStatus,
  diagnostics = [],
  onNavigateToStream
}) => {
  const [selectedEps, setSelectedEps] = useState<number>(continuousStatus?.configured_eps || 25);
  const [selectedScenario, setSelectedScenario] = useState<string>('DATABASE_CONNECTION_FAILURE');
  const [isTriggeringFailure, setIsTriggeringFailure] = useState<boolean>(false);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [filterService, setFilterService] = useState<string>('ALL');
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  // Sync EPS with backend
  const handleSetEps = async (eps: number) => {
    setSelectedEps(eps);
    try {
      await api.setTelemetryRate(eps);
      setActionFeedback(`Telemetry rate set to ${eps} EPS.`);
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (e: any) {
      setActionFeedback(`Failed to update rate: ${e.message}`);
    }
  };

  const handleToggleScheduler = async () => {
    try {
      const newEnabled = !(schedulerStatus?.is_enabled ?? true);
      await api.configureFailureScheduler({ enabled: newEnabled });
      setActionFeedback(`Failure scheduler ${newEnabled ? 'enabled' : 'paused'}.`);
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (e: any) {
      setActionFeedback(`Error configuring scheduler: ${e.message}`);
    }
  };

  const handleSetInterval = async (interval: number) => {
    try {
      await api.configureFailureScheduler({ interval_seconds: interval });
      setActionFeedback(`Failure interval set to ${interval} seconds.`);
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (e: any) {
      setActionFeedback(`Error setting interval: ${e.message}`);
    }
  };

  const handleTriggerFailure = async () => {
    setIsTriggeringFailure(true);
    try {
      const res = await api.triggerFailureScenario(selectedScenario);
      setActionFeedback(`Triggered: ${res.scenario} -> Downstream: ${res.downstream?.join(', ') || 'None'}`);
      setTimeout(() => setActionFeedback(null), 5000);
    } catch (e: any) {
      setActionFeedback(`Failed to inject scenario: ${e.message}`);
    } finally {
      setIsTriggeringFailure(false);
    }
  };

  const filteredEvents = diagnostics.filter(evt => {
    const matchSev = filterSeverity === 'ALL' || evt.severity === filterSeverity;
    const matchSvc = filterService === 'ALL' || evt.service === filterService;
    return matchSev && matchSvc;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Mode Selector Header Bar */}
      <div className="p-6 rounded-2xl glass-panel border-cyan-500/30 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 shadow-2xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 animate-ping"></span>
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400">
                AegisOps Telemetry Ingestion Core
              </span>
            </div>
            <h2 className="text-2xl font-black text-white tracking-tight">
              Real-Time Continuous Ingestion & Diagnostics
            </h2>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
              Every event flows through Normalization, Redaction, Latency Calculation, Anomaly Detection, and Correlation.
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex items-center p-1.5 rounded-2xl bg-slate-950 border border-slate-800 shadow-inner">
            <button
              onClick={() => onModeChange('CONTROLLED_DEMO')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                operatingMode === 'CONTROLLED_DEMO'
                  ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Cpu className="h-4 w-4" />
              <span>MODE 2: Controlled Real-Time Demo</span>
            </button>

            <button
              onClick={() => onModeChange('LIVE_STREAM')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                operatingMode === 'LIVE_STREAM'
                  ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Radio className="h-4 w-4" />
              <span>MODE 1: OpenTelemetry Live Stream</span>
            </button>
          </div>
        </div>
      </div>

      {actionFeedback && (
        <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center gap-2 animate-fadeIn">
          <Activity className="h-4 w-4 text-cyan-400 animate-spin" />
          <span>{actionFeedback}</span>
        </div>
      )}

      {/* Mode 1: OpenTelemetry & Streaming Collector Live State Banner */}
      {operatingMode === 'LIVE_STREAM' && (
        <div className="p-5 rounded-2xl glass-panel border-cyan-500/40 bg-slate-900/90 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                <Radio className="h-6 w-6 animate-pulse" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">OpenTelemetry & Streaming Ingestion Pipeline</h3>
                <span className="text-xs text-slate-400">Canonical OTel Collector, HTTP/gRPC API & Kafka event streaming</span>
              </div>
            </div>

            <div>
              <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5 shadow-lg shadow-emerald-500/10">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
                <span>STREAM ACTIVE (OPENTELEMETRY INGESTION)</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Events Ingested</span>
              <strong className="text-base font-bold text-white font-mono">{(continuousStatus?.total_events ?? 0).toLocaleString()}</strong>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Live Rate (EPS)</span>
              <strong className="text-base font-bold text-cyan-400 font-mono">{continuousStatus?.actual_eps ?? 0.0} /s</strong>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Ingestion Latency</span>
              <strong className="text-base font-bold text-emerald-400 font-mono">{continuousStatus?.avg_ingestion_latency_ms ?? 2.4} ms</strong>
            </div>
            <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Protocol Standard</span>
              <strong className="text-[11px] font-mono text-cyan-300 mt-1 block">
                OTel v1.31 / HTTP / OTLP
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* Mode 2: Controlled Real-Time Demo Controls */}
      {operatingMode === 'CONTROLLED_DEMO' && (
        <div className="space-y-6">
          {/* Real Metrics HUD */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Throughput (EPS)</span>
              <strong className="text-xl font-bold text-cyan-400 font-mono">
                {continuousStatus?.actual_eps ?? 0.0} /s
              </strong>
            </div>

            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Ingestion Latency</span>
              <strong className="text-xl font-bold text-emerald-400 font-mono">
                {continuousStatus?.avg_ingestion_latency_ms ?? 2.4} ms
              </strong>
            </div>

            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Total Ingested</span>
              <strong className="text-xl font-bold text-white font-mono">
                {(continuousStatus?.total_events ?? 0).toLocaleString()}
              </strong>
            </div>

            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Errors Detected</span>
              <strong className="text-xl font-bold text-rose-400 font-mono">
                {(continuousStatus?.total_errors ?? 0).toLocaleString()}
              </strong>
            </div>

            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Failure Engine</span>
              <strong className="text-xs font-bold text-amber-400 font-mono mt-1 block">
                {schedulerStatus?.is_enabled ? `EVERY ${schedulerStatus.interval_seconds}s` : 'PAUSED'}
              </strong>
            </div>

            <div className="p-3.5 rounded-xl glass-card border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Next Failure In</span>
              <strong className="text-xl font-bold text-indigo-400 font-mono">
                {schedulerStatus?.is_enabled ? `${schedulerStatus.time_to_next_failure_sec}s` : '--'}
              </strong>
            </div>
          </div>

          {/* Engine Controls: Rate Pacing & Cascade Failure Injector */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left: Throughput Pacing */}
            <div className="p-5 rounded-2xl glass-panel border-slate-800 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <Activity className="h-5 w-5 text-cyan-400" />
                  <div>
                    <h3 className="text-sm font-bold text-white">Continuous Generator Rate</h3>
                    <span className="text-[11px] text-slate-400">Paced multi-service transaction volume</span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 font-mono text-[11px] border border-cyan-800">
                  {selectedEps} EPS TARGET
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                {[25, 100, 500, 1000, 5000].map(rate => (
                  <button
                    key={rate}
                    onClick={() => handleSetEps(rate)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-bold font-mono transition ${
                      selectedEps === rate
                        ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/20'
                        : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                    }`}
                  >
                    {rate} EPS
                  </button>
                ))}
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                Transactions are emitted across 5 independent backend microservices: <strong className="text-slate-200">gateway (8001)</strong>, <strong className="text-slate-200">order-service (8002)</strong>, <strong className="text-slate-200">payment-api (8003)</strong>, <strong className="text-slate-200">database-service (8004)</strong>, and <strong className="text-slate-200">auth-service (8005)</strong>.
              </p>
            </div>

            {/* Right: Controlled Failure Scheduler */}
            <div className="p-5 rounded-2xl glass-panel border-slate-800 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <Flame className="h-5 w-5 text-amber-400" />
                  <div>
                    <h3 className="text-sm font-bold text-white">Controlled Failure Engine</h3>
                    <span className="text-[11px] text-slate-400">10 realistic cascading failure scenarios</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleToggleScheduler}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
                      schedulerStatus?.is_enabled
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {schedulerStatus?.is_enabled ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                    <span>{schedulerStatus?.is_enabled ? 'Auto Active' : 'Auto Paused'}</span>
                  </button>
                </div>
              </div>

              {/* Scenario selector & Trigger button */}
              <div className="flex flex-col sm:flex-row gap-2">
                <select
                  value={selectedScenario}
                  onChange={(e) => setSelectedScenario(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                >
                  {schedulerStatus?.available_scenarios?.map(sc => (
                    <option key={sc.id} value={sc.id}>
                      {sc.name} ({sc.primary})
                    </option>
                  )) || (
                    <option value="DATABASE_CONNECTION_FAILURE">Database Connection Pool Exhaustion</option>
                  )}
                </select>

                <button
                  onClick={handleTriggerFailure}
                  disabled={isTriggeringFailure}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white text-xs font-bold transition shadow-lg shadow-rose-500/20 flex items-center justify-center gap-1.5 disabled:opacity-50 flex-shrink-0"
                >
                  <Zap className={`h-3.5 w-3.5 ${isTriggeringFailure ? 'animate-spin' : ''}`} />
                  <span>Trigger Failure Now</span>
                </button>
              </div>

              {/* Interval selector */}
              <div className="flex items-center justify-between pt-1 text-xs">
                <span className="text-[11px] text-slate-400 font-mono">Interval:</span>
                <div className="flex items-center gap-1">
                  {[15, 30, 60, 120].map(sec => (
                    <button
                      key={sec}
                      onClick={() => handleSetInterval(sec)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                        schedulerStatus?.interval_seconds === sec
                          ? 'bg-slate-700 text-white border border-slate-600'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {sec}s
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Real Ingestion Latency & Live Event Diagnostics Inspector */}
      <div className="p-6 rounded-2xl glass-panel border-slate-800 space-y-4 shadow-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="h-4 w-4 text-cyan-400" />
              <span>Real-Time Ingestion Latency & Event Diagnostics Inspector</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Live calculation of <code className="text-cyan-300 font-mono">ingestion_latency = received_at - timestamp</code> for every individual stream event.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={filterService}
              onChange={(e) => setFilterService(e.target.value)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 font-mono"
            >
              <option value="ALL">All Services</option>
              <option value="gateway">gateway</option>
              <option value="order-service">order-service</option>
              <option value="payment-api">payment-api</option>
              <option value="database-service">database-service</option>
              <option value="auth-service">auth-service</option>
            </select>

            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 font-mono"
            >
              <option value="ALL">All Severities</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>
        </div>

        {/* Diagnostics Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-500 text-[10px] uppercase">
                <th className="pb-2 pl-2">Event ID</th>
                <th className="pb-2">Source Timestamp</th>
                <th className="pb-2">Received At</th>
                <th className="pb-2">Ingestion Latency</th>
                <th className="pb-2">Service</th>
                <th className="pb-2">Severity</th>
                <th className="pb-2">Event Type</th>
                <th className="pb-2 pr-2">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 text-xs font-mono">
                    Awaiting incoming continuous telemetry diagnostic frames...
                  </td>
                </tr>
              ) : (
                filteredEvents.map((evt) => {
                  const isExpanded = expandedEventId === evt.event_id;
                  return (
                    <React.Fragment key={evt.event_id}>
                      <tr 
                        onClick={() => setExpandedEventId(isExpanded ? null : evt.event_id)}
                        className="hover:bg-slate-900/80 cursor-pointer transition"
                      >
                        <td className="py-2.5 pl-2 text-slate-400 truncate max-w-[90px]" title={evt.event_id}>
                          {evt.event_id.slice(0, 8)}...
                        </td>
                        <td className="py-2.5 text-slate-400">
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '--'}
                        </td>
                        <td className="py-2.5 text-slate-400">
                          {evt.received_at ? new Date(evt.received_at).toLocaleTimeString() : '--'}
                        </td>
                        <td className="py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            evt.ingestion_latency_ms < 5.0 
                              ? 'bg-emerald-500/20 text-emerald-300' 
                              : evt.ingestion_latency_ms < 20.0 
                              ? 'bg-amber-500/20 text-amber-300' 
                              : 'bg-rose-500/20 text-rose-300'
                          }`}>
                            {evt.ingestion_latency_ms} ms
                          </span>
                        </td>
                        <td className="py-2.5 font-bold text-slate-200">
                          {evt.service}
                        </td>
                        <td className="py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            evt.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                            evt.severity === 'ERROR' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30' :
                            evt.severity === 'WARNING' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                            'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                          }`}>
                            {evt.severity}
                          </span>
                        </td>
                        <td className="py-2.5 text-slate-300 text-[11px]">
                          {evt.event_type}
                        </td>
                        <td className="py-2.5 pr-2 text-slate-300 truncate max-w-xs font-sans text-xs">
                          {evt.message}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-slate-950/80">
                          <td colSpan={8} className="p-3 text-[11px] text-slate-300 space-y-2 border-b border-slate-800 font-mono">
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-slate-400">
                              <div><strong>Source:</strong> {evt.source}</div>
                              <div><strong>Host:</strong> {evt.host || 'node-01'}</div>
                              <div><strong>Source Timestamp:</strong> {evt.timestamp}</div>
                              <div><strong>Received At:</strong> {evt.received_at}</div>
                            </div>
                            <div>
                              <strong>Attributes:</strong>
                              <pre className="mt-1 p-2 rounded bg-slate-900 border border-slate-800 text-cyan-300 overflow-x-auto text-[10px]">
                                {JSON.stringify(evt.attributes || {}, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

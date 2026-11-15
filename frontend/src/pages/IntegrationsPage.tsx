import React, { useState, useEffect } from 'react';
import { 
  Network, 
  Radio, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Key, 
  Send, 
  Copy, 
  Check, 
  RefreshCw, 
  ShieldCheck, 
  Activity, 
  Zap, 
  Database, 
  CreditCard, 
  Layers,
  Server,
  Lock,
  ArrowUpRight
} from 'lucide-react';
import type { ConnectorInfo } from '../types';
import { api } from '../services/api';

export const IntegrationsPage: React.FC = () => {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; message: string; success: boolean } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const connData = await api.getIntegrations();
      setConnectors(connData);
    } catch (e) {
      // Backend starting
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleTestConnection = async (connectorId: string) => {
    setTestingId(connectorId);
    try {
      const res = await api.testIntegration(connectorId);
      setTestResult({ id: connectorId, message: res.message, success: true });
      fetchData();
      setTimeout(() => setTestResult(null), 5000);
    } catch (e: any) {
      setTestResult({ id: connectorId, message: e.message || 'Connection test failed', success: false });
    } finally {
      setTestingId(null);
    }
  };

  const handleToggle = async (connectorId: string, currentEnabled: boolean) => {
    try {
      await api.toggleIntegration(connectorId, !currentEnabled);
      fetchData();
    } catch (e) {
      // Error toggling
    }
  };

  const handleCopyEndpoint = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Radio className="h-5 w-5 text-cyan-400" />
            <span>Telemetry Connectors & Ingestion Gateway</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Canonical telemetry streaming architecture: OpenTelemetry Collector, Kafka streaming bus, and HTTP telemetry endpoints.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span>Active Connectors: <strong className="text-cyan-400">{connectors.filter(c => c.enabled).length} / {connectors.length}</strong></span>
        </div>
      </div>

      {/* Security Banner */}
      <div className="p-4 rounded-xl glass-panel border-cyan-500/30 flex items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-cyan-400 flex-shrink-0" />
          <p className="text-slate-300">
            <strong className="text-white">Strict Least-Privilege & Credential Redaction:</strong> All incoming telemetry is automatically sanitized. Passwords, bearer tokens, connection strings, and private keys are redacted before persistence or stream broadcasting.
          </p>
        </div>
        <span className="px-2.5 py-1 rounded bg-slate-900 text-cyan-400 font-mono text-[10px] border border-slate-700 flex-shrink-0">
          OTel v1.31 / TLS Ingestion
        </span>
      </div>

      {testResult && (
        <div className={`p-4 rounded-xl text-xs font-semibold flex items-center gap-2 border ${
          testResult.success 
            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' 
            : 'bg-rose-500/20 border-rose-500/40 text-rose-300'
        }`}>
          {testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span>{testResult.message}</span>
        </div>
      )}

      {/* ============================================================================== */}
      {/* Featured Primary Ingestion Architecture: OpenTelemetry & Apache Kafka Backbone */}
      {/* ============================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* OpenTelemetry Gateway Card */}
        <div className="p-6 rounded-2xl glass-panel border-indigo-500/40 shadow-2xl space-y-4 bg-gradient-to-br from-slate-900/90 via-slate-900/60 to-indigo-950/20">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                <Activity className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-white">OpenTelemetry Collector</h3>
                  <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 font-mono text-[10px] border border-indigo-800">
                    OTLP 1.0 STANDARD
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  High-performance OTLP gRPC (4317) and HTTP (4318) trace, span, and metric gateway.
                </p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span>ACTIVE</span>
            </span>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">OTLP HTTP Endpoint</label>
            <div className="flex items-center justify-between p-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
              <span className="truncate pr-2">http://127.0.0.1:8000/api/otel/v1/traces</span>
              <button
                onClick={() => handleCopyEndpoint('otel', 'http://127.0.0.1:8000/api/otel/v1/traces')}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-indigo-400 transition"
                title="Copy Endpoint"
              >
                {copiedId === 'otel' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">gRPC Port</span>
              <strong className="text-indigo-300 font-mono">4317</strong>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">HTTP Port</span>
              <strong className="text-indigo-300 font-mono">4318</strong>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">Batch Buffer</span>
              <strong className="text-emerald-400 font-mono">256 items</strong>
            </div>
          </div>
        </div>

        {/* Apache Kafka Streaming Backbone Card */}
        <div className="p-6 rounded-2xl glass-panel border-cyan-500/40 shadow-2xl space-y-4 bg-gradient-to-br from-slate-900/90 via-slate-900/60 to-cyan-950/20">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                <Zap className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-white">Apache Kafka Streaming</h3>
                  <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 font-mono text-[10px] border border-cyan-800">
                    EVENT STREAMING
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Fault-tolerant event streaming backbone connecting collectors, normalizers, and AIOps engines.
                </p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
              <span>STREAM READY</span>
            </span>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Primary Broker & Consumer Group</label>
            <div className="flex items-center justify-between p-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
              <span className="truncate pr-2">kafka:9092 (Group: aegisops-processing-group)</span>
              <button
                onClick={() => handleCopyEndpoint('kafka', 'kafka:9092')}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-400 transition"
                title="Copy Broker"
              >
                {copiedId === 'kafka' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">Topics</span>
              <strong className="text-cyan-300 font-mono">10 Active</strong>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">Consumer Lag</span>
              <strong className="text-emerald-400 font-mono">0 msgs</strong>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <span className="text-[10px] text-slate-500 block uppercase font-mono">Avg Latency</span>
              <strong className="text-white font-mono">0.6 ms</strong>
            </div>
          </div>
        </div>
      </div>

      {/* ============================================================================== */}
      {/* Generic Telemetry Connectors Grid                                             */}
      {/* ============================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {connectors.map((c) => {
          const endpointUrl = `http://127.0.0.1:8000/api/integrations/${c.connector_id}/ingest`;
          const isTesting = testingId === c.connector_id;

          return (
            <div key={c.connector_id} className="p-5 rounded-2xl glass-panel border-slate-800 space-y-4 shadow-xl">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-cyan-400">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{c.name}</h3>
                    <span className="text-[10px] font-mono text-cyan-400">{c.type}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-1 ${
                    c.enabled 
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                      : 'bg-slate-800 text-slate-500'
                  }`}>
                    {c.enabled && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 inline-block animate-ping"></span>}
                    <span>{c.enabled ? 'ACTIVE' : 'DISABLED'}</span>
                  </span>

                  <button
                    onClick={() => handleToggle(c.connector_id, c.enabled)}
                    className="text-[11px] font-medium text-slate-400 hover:text-slate-200 underline underline-offset-2 ml-1"
                  >
                    {c.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-slate-300 leading-relaxed">{c.description}</p>

              {/* Ingestion Endpoint */}
              <div className="space-y-1">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Ingestion Endpoint (HTTP POST)</label>
                <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
                  <span className="truncate pr-2">{endpointUrl}</span>
                  <button
                    onClick={() => handleCopyEndpoint(c.connector_id, endpointUrl)}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-400 transition flex-shrink-0"
                    title="Copy Endpoint"
                  >
                    {copiedId === c.connector_id ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>

              {/* Telemetry Metrics */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase">Total Ingested</span>
                  <strong className="text-slate-100 font-mono">{c.total_events.toLocaleString()}</strong>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase">Rate (EPS)</span>
                  <strong className="text-cyan-400 font-mono">{c.event_rate_eps} /s</strong>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase">Auth Scheme</span>
                  <strong className="text-slate-300 font-mono text-[11px]">{c.auth_required ? 'Bearer Token' : 'Open Mesh'}</strong>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                <span className="text-[11px] text-slate-500 font-mono">
                  {c.last_event_at ? `Last Event: ${new Date(c.last_event_at).toLocaleTimeString()}` : 'No events yet'}
                </span>

                <button
                  onClick={() => handleTestConnection(c.connector_id)}
                  disabled={isTesting}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Send className={`h-3.5 w-3.5 text-cyan-400 ${isTesting ? 'animate-spin' : ''}`} />
                  <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

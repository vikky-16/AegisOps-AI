import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Radio, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldAlert, 
  Zap, 
  Search, 
  FileSearch, 
  Layers, 
  Play, 
  Cpu, 
  RotateCw,
  Clock,
  ArrowRight,
  ShieldCheck,
  Server
} from 'lucide-react';
import type { OperationFeedItem, Incident } from '../types';
import { api } from '../services/api';

interface OperationsCenterPageProps {
  incidents: Incident[];
  setActiveTab?: (tab: string) => void;
}

export const OperationsCenterPage: React.FC<OperationsCenterPageProps> = ({ incidents, setActiveTab }) => {
  const [feedItems, setFeedItems] = useState<OperationFeedItem[]>([]);
  const [filterPhase, setFilterPhase] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchFeed = async () => {
    setIsRefreshing(true);
    try {
      const data = await api.getOperationsFeed(60);
      setFeedItems(data);
    } catch (e) {
      // Backend starting
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchFeed();
    const interval = setInterval(fetchFeed, 2000);
    return () => clearInterval(interval);
  }, []);

  const activeIncidents = incidents.filter(i => i.status !== 'RESOLVED');

  const filteredFeed = feedItems.filter(item => {
    const matchesPhase = filterPhase === 'ALL' || item.phase.toLowerCase().includes(filterPhase.toLowerCase());
    const matchesSearch = !searchTerm || 
      item.message.toLowerCase().includes(searchTerm.toLowerCase()) || 
      item.service.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.phase.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesPhase && matchesSearch;
  });

  const getPhaseBadge = (phase: string, severity: string) => {
    if (phase.startsWith('OTEL') || phase.startsWith('STREAM')) {
      if (severity === 'CRITICAL' || phase.includes('ANOMALY') || phase.includes('ERROR')) {
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-400"></span>
            <span>{phase}</span>
          </span>
        );
      }
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
          {phase}
        </span>
      );
    }
    if (severity === 'CRITICAL' || phase.includes('ANOMALY') || phase.includes('FAIL')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
          {phase}
        </span>
      );
    }
    if (severity === 'WARNING' || phase.includes('APPROVAL') || phase.includes('CASCADE')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
          {phase}
        </span>
      );
    }
    if (phase.includes('VERIF') || phase.includes('RESOLV') || phase.includes('SUCCESS')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
          {phase}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
        {phase}
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Radio className="h-5 w-5 text-cyan-400 animate-pulse" />
            <span>Real-Time Autonomous Operations Center</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Continuous closed-loop telemetry analysis, multi-service cascade correlation, and autonomous runbook execution.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchFeed}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
          >
            <RotateCw className={`h-3.5 w-3.5 text-cyan-400 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh Stream</span>
          </button>
        </div>
      </div>

      {/* Autonomous Closed-Loop HUD Progression */}
      <div className="p-5 rounded-2xl glass-panel border-cyan-500/30 space-y-4 shadow-xl shadow-cyan-500/5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-cyan-400" />
            <span>Autonomous Closed-Loop Operational State</span>
          </span>
          <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/30 flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping inline-block"></span>
            <span>CONTINUOUS MONITORING ACTIVE</span>
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { step: '1. INGEST', desc: 'OTel, Syslog, Webhooks', icon: Server, color: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10' },
            { step: '2. DETECT', desc: 'Isolation Forest & Z-Score', icon: Activity, color: 'text-indigo-400 border-indigo-500/40 bg-indigo-500/10' },
            { step: '3. CORRELATE', desc: '20s Multi-Signal Window', icon: Layers, color: 'text-purple-400 border-purple-500/40 bg-purple-500/10' },
            { step: '4. ISOLATE RCA', desc: 'Topological Causality Path', icon: FileSearch, color: 'text-amber-400 border-amber-500/40 bg-amber-500/10' },
            { step: '5. REMEDIATE', desc: 'Allowlisted YAML Runbooks', icon: Zap, color: 'text-rose-400 border-rose-500/40 bg-rose-500/10' },
            { step: '6. VERIFY', desc: '4-Point Telemetry Probe', icon: CheckCircle2, color: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10' }
          ].map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} className={`p-3 rounded-xl border ${item.color} space-y-1.5`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold tracking-tight">{item.step}</span>
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <p className="text-[10px] text-slate-400 leading-tight">{item.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Active Investigations Feed if any */}
      {activeIncidents.length > 0 && (
        <div className="p-5 rounded-2xl glass-panel border-amber-500/40 space-y-4 shadow-xl shadow-amber-500/5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 animate-pulse" />
              <span>Active Autonomous Investigations ({activeIncidents.length})</span>
            </h3>
            {setActiveTab && (
              <button
                onClick={() => setActiveTab('incidents')}
                className="text-xs text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1"
              >
                <span>View All Details</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeIncidents.map((inc) => (
              <div key={inc.incident_id} className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-cyan-400">{inc.incident_id}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {inc.status}
                  </span>
                </div>
                <p className="text-xs font-bold text-white">{inc.title}</p>
                <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800">
                  <span>Root Cause: <strong className="text-slate-200">{inc.root_cause_service}</strong></span>
                  <span>Confidence: <strong className="text-emerald-400">{intToPct(inc.rca_confidence)}%</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Chronological Event Stream Ticker */}
      <div className="p-6 rounded-2xl glass-panel space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white">Live Real-Time Operations Event Stream</h3>
            <span className="text-xs text-slate-500 font-mono">({filteredFeed.length} events)</span>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search event messages..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <select
              value={filterPhase}
              onChange={(e) => setFilterPhase(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Phases</option>
              <option value="OTEL">OpenTelemetry Streams</option>
              <option value="TELEMETRY">Telemetry Ingest</option>
              <option value="ANOMALY">Anomalies</option>
              <option value="CASCADE">Correlation</option>
              <option value="RCA">Root Cause</option>
              <option value="RUNBOOK">Runbook Action</option>
              <option value="VERIF">Verification</option>
              <option value="APPROVAL">Approvals</option>
            </select>
          </div>
        </div>

        {/* Chronological Event Ticker List */}
        <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
          {filteredFeed.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              Waiting for incoming operational telemetry events...
            </div>
          ) : (
            filteredFeed.map((item) => (
              <div 
                key={item.id}
                className="p-3.5 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-start sm:items-center gap-3">
                  <span className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{item.time_display}</span>
                  </span>
                  <div>{getPhaseBadge(item.phase, item.severity)}</div>
                  <div className="font-semibold text-slate-200">{item.message}</div>
                </div>

                <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/60">
                    {item.service}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

function intToPct(val: number) {
  return Math.round(val <= 1.0 ? val * 100 : val);
}

import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Activity, 
  Database, 
  Server, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  Gauge, 
  Sparkles,
  Radio,
  Clock,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Flame,
  FileText,
  Boxes,
  Terminal
} from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import type { LogHubDatasetInfo, LogHubReplayStatus } from '../types';
import { api } from '../services/api';

interface ReplayPageProps {
  setActiveTab?: (tab: string) => void;
}

export const ReplayPage: React.FC<ReplayPageProps> = ({ setActiveTab }) => {
  const [datasets, setDatasets] = useState<LogHubDatasetInfo[]>([]);
  const [status, setStatus] = useState<LogHubReplayStatus>({
    status: 'IDLE',
    dataset: 'HDFS',
    events_available: 0,
    events_sent: 0,
    events_received: 0,
    events_processed: 0,
    processing_rate: 0.0,
    configured_eps: 1000,
    target_count: 100000,
    progress_percentage: 0.0,
    elapsed_seconds: 0.0,
    errors: 0,
    anomalies: 0,
    correlated_events: 0,
    incidents: 0,
    critical_incidents: 0,
    is_streaming: false,
    is_paused: false
  });

  const [selectedDataset, setSelectedDataset] = useState<string>('HDFS');
  const [targetCount, setTargetCount] = useState<number>(100000);
  const [configuredEps, setConfiguredEps] = useState<number>(1000);
  const [epsHistory, setEpsHistory] = useState<Array<{ time: string; eps: number }>>([]);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await api.getLogHubReplayStatus();
      setStatus(data);
      if (data.is_streaming) {
        setEpsHistory(prev => {
          const next = [...prev, { time: new Date().toLocaleTimeString(), eps: data.processing_rate }];
          return next.slice(-20);
        });
      }
    } catch (e) {}
  };

  const fetchDatasets = async () => {
    try {
      const data = await api.getLogHubDatasets();
      setDatasets(data);
    } catch (e) {}
  };

  useEffect(() => {
    fetchDatasets();
    fetchStatus();
    const interval = setInterval(fetchStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await api.startLogHubReplay(selectedDataset, targetCount, configuredEps);
      setFeedbackMessage(`LogHub Replay started: Streaming ${targetCount.toLocaleString()} records from '${selectedDataset}' at ${configuredEps} EPS`);
      fetchStatus();
      setTimeout(() => setFeedbackMessage(null), 4000);
    } catch (e: any) {
      setFeedbackMessage(`Error starting replay: ${e.message}`);
    }
  };

  const handlePause = async () => {
    try {
      await api.pauseLogHubReplay();
      fetchStatus();
    } catch (e) {}
  };

  const handleResume = async () => {
    try {
      await api.resumeLogHubReplay();
      fetchStatus();
    } catch (e) {}
  };

  const handleStop = async () => {
    try {
      await api.stopLogHubReplay();
      fetchStatus();
    } catch (e) {}
  };

  const handleReset = async () => {
    try {
      await api.resetLogHubReplay();
      setEpsHistory([]);
      fetchStatus();
      setFeedbackMessage('LogHub replay state and telemetry buffer reset successfully.');
      setTimeout(() => setFeedbackMessage(null), 4000);
    } catch (e) {}
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header & Architecture Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Terminal className="h-5 w-5 text-indigo-400 animate-pulse" />
            <span>Real-World LogHub Historical Telemetry Replay Subsystem</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Replays standardized LogHub real-world datasets (HDFS, Linux, OpenStack, BGL, Spark, ZooKeeper, Hadoop) as a live streaming source into the central AIOps pipeline.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
          >
            <RotateCcw className="h-3.5 w-3.5 text-indigo-400" />
            <span>Reset Replay State</span>
          </button>
        </div>
      </div>

      {feedbackMessage && (
        <div className="p-4 rounded-xl text-xs font-semibold bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          <span>{feedbackMessage}</span>
        </div>
      )}

      {/* 10 Live Diagnostic Counters HUD */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">1. Available</span>
          <strong className="text-white font-mono text-sm">{status.events_available.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Raw Records</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">2. Sent</span>
          <strong className="text-cyan-400 font-mono text-sm">{status.events_sent.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Stream Dispatch</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">3. Received</span>
          <strong className="text-indigo-400 font-mono text-sm">{status.events_received.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Ingestion Inbound</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">4. Processed</span>
          <strong className="text-emerald-400 font-mono text-sm">{status.events_processed.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Parsed & Indexed</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">5. Process Rate</span>
          <strong className="text-amber-400 font-mono text-sm">{status.processing_rate} /s</strong>
          <span className="text-[10px] text-slate-500 block">Throughput (EPS)</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">6. Errors</span>
          <strong className="text-rose-400 font-mono text-sm">{status.errors.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Error Severities</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">7. Anomalies</span>
          <strong className="text-amber-400 font-mono text-sm">{status.anomalies.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Z-Score & Isolation</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">8. Correlated</span>
          <strong className="text-purple-400 font-mono text-sm">{status.correlated_events.toLocaleString()}</strong>
          <span className="text-[10px] text-slate-500 block">Window Merged</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">9. Incidents</span>
          <strong className="text-rose-300 font-mono text-sm">{status.incidents}</strong>
          <span className="text-[10px] text-slate-500 block">Clusters Formed</span>
        </div>
        <div className="p-3 rounded-2xl glass-panel border-slate-800 text-center">
          <span className="text-[10px] text-slate-500 block uppercase font-mono">10. Critical</span>
          <strong className="text-rose-500 font-mono text-sm">{status.critical_incidents}</strong>
          <span className="text-[10px] text-slate-500 block">High Priority</span>
        </div>
      </div>

      {/* Real-Time Replay Control Banner */}
      <div className="p-6 rounded-2xl glass-panel border-indigo-500/40 space-y-5 shadow-2xl shadow-indigo-500/10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-indigo-400">
              <Gauge className={`h-6 w-6 ${status.is_streaming ? 'animate-spin' : ''}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-slate-400">REPLAY STATE:</span>
                <span className={`text-xs font-mono font-extrabold px-2.5 py-0.5 rounded-full ${
                  status.status === 'STREAMING' 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 animate-pulse' 
                    : status.status === 'PAUSED'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : status.status === 'COMPLETED'
                    ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                    : 'bg-slate-800 text-slate-400'
                }`}>
                  {status.status}
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Active Benchmark: <strong className="text-white font-mono">{status.dataset}</strong> ({status.events_processed.toLocaleString()} / {status.target_count.toLocaleString()} records @ {status.configured_eps} EPS)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-emerald-400 font-bold bg-emerald-500/10 px-3 py-1.5 rounded-xl border border-emerald-500/30">
              Elapsed: {status.elapsed_seconds}s
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-slate-400 font-mono">
            <span>Historical Telemetry Ingestion Progress</span>
            <span className="text-indigo-400 font-bold">{status.progress_percentage}%</span>
          </div>
          <div className="h-3 w-full rounded-full bg-slate-950 overflow-hidden border border-slate-800">
            <div 
              className="h-full bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-500 transition-all duration-300"
              style={{ width: `${status.progress_percentage}%` }}
            ></div>
          </div>
        </div>

        {/* Replay Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-2">
            {!status.is_streaming ? (
              <button
                onClick={handleStart}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-bold text-xs shadow-lg shadow-indigo-500/20 transition flex items-center gap-2"
              >
                <Play className="h-4 w-4" />
                <span>Start Replay ({targetCount.toLocaleString()} events @ {configuredEps} EPS)</span>
              </button>
            ) : (
              <>
                <button
                  onClick={handlePause}
                  className="px-4 py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-xs border border-amber-500/40 transition flex items-center gap-1.5"
                >
                  <Pause className="h-4 w-4" />
                  <span>Pause</span>
                </button>
                <button
                  onClick={handleStop}
                  className="px-4 py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-bold text-xs border border-rose-500/40 transition flex items-center gap-1.5"
                >
                  <Square className="h-4 w-4" />
                  <span>Stop</span>
                </button>
              </>
            )}

            {status.is_paused && (
              <button
                onClick={handleResume}
                className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition flex items-center gap-1.5"
              >
                <Play className="h-4 w-4" />
                <span>Resume Stream</span>
              </button>
            )}
          </div>

          {setActiveTab && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('incidents')}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-indigo-400 text-xs font-semibold border border-indigo-500/30 transition flex items-center gap-1.5"
              >
                <span>View Incident Center</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Volume & Rate Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Record Volume Selector */}
        <div className="p-5 rounded-2xl glass-panel space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Boxes className="h-4 w-4 text-indigo-400" />
            <span>Target Replay Volume</span>
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[10000, 50000, 100000].map((count) => (
              <button
                key={count}
                onClick={() => setTargetCount(count)}
                disabled={status.is_streaming}
                className={`py-2.5 px-2 rounded-xl text-xs font-mono font-bold transition border ${
                  targetCount === count 
                    ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/50 shadow-md shadow-indigo-500/10' 
                    : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                {count / 1000}K Records
              </button>
            ))}
          </div>
        </div>

        {/* Rate Selector */}
        <div className="p-5 rounded-2xl glass-panel space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Gauge className="h-4 w-4 text-emerald-400" />
            <span>Replay Speed (Events per Second)</span>
          </label>
          <div className="grid grid-cols-4 gap-2">
            {[100, 250, 500, 1000].map((rate) => (
              <button
                key={rate}
                onClick={() => setConfiguredEps(rate)}
                disabled={status.is_streaming}
                className={`py-2.5 px-2 rounded-xl text-xs font-mono font-bold transition border ${
                  configuredEps === rate 
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-md shadow-emerald-500/10' 
                    : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                {rate} EPS
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dataset Selection Cards Grid */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Select Real-World LogHub Benchmark Dataset
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {datasets.map((ds) => {
            const isSelected = selectedDataset === ds.id;

            return (
              <button
                key={ds.id}
                onClick={() => setSelectedDataset(ds.id)}
                disabled={status.is_streaming}
                className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between space-y-3 ${
                  isSelected 
                    ? 'bg-slate-900 border-indigo-500 shadow-xl shadow-indigo-500/10' 
                    : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white font-mono">{ds.id}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                      {ds.total_raw_records.toLocaleString()} rows
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">{ds.description}</p>
                </div>

                <div className="space-y-2 pt-2 border-t border-slate-800/80">
                  <div className="flex flex-wrap gap-1">
                    {ds.components.slice(0, 2).map((c, i) => (
                      <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 font-mono">
                        {c}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                    <span className="truncate max-w-[140px] text-[9px] text-slate-500">{ds.category}</span>
                    <span className={isSelected ? 'text-indigo-400 font-bold' : ''}>
                      {isSelected ? 'SELECTED' : 'Select'}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Real-time Throughput Area Chart */}
      {epsHistory.length > 0 && (
        <div className="p-5 rounded-2xl glass-panel space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-xs font-bold text-white flex items-center gap-2">
              <Activity className="h-4 w-4 text-indigo-400" />
              <span>LogHub Ingestion Stream Throughput (EPS)</span>
            </h3>
            <span className="text-xs font-mono text-indigo-400">{status.processing_rate} events/sec</span>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={epsHistory}>
                <defs>
                  <linearGradient id="loghubEpsGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#6366F1" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="#6366F1" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="time" stroke="#64748B" fontSize={10} />
                <YAxis stroke="#64748B" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }} />
                <Area type="monotone" dataKey="eps" stroke="#6366F1" strokeWidth={2} fill="url(#loghubEpsGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

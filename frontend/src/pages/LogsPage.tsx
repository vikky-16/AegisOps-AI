import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Search, 
  Filter, 
  Layers, 
  RotateCcw, 
  Zap, 
  ChevronLeft, 
  ChevronRight, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Database,
  Sparkles,
  RefreshCw,
  Trash2
} from 'lucide-react';
import type { LogEntry, LogFingerprint, LogSummary, PaginatedLogs } from '../types';
import { api } from '../services/api';

export const LogsPage: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [fingerprints, setFingerprints] = useState<LogFingerprint[]>([]);
  const [summary, setSummary] = useState<LogSummary | null>(null);
  const [isGroupedView, setIsGroupedView] = useState<boolean>(false);

  // Filter States
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedService, setSelectedService] = useState<string>('all');
  const [selectedLevel, setSelectedLevel] = useState<string>('all');
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalMatching, setTotalMatching] = useState<number>(0);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      if (isGroupedView) {
        const fpData = await api.getLogFingerprints();
        setFingerprints(fpData);
      } else {
        const res = await api.getLogs({
          page,
          pageSize,
          service: selectedService,
          level: selectedLevel,
          search: searchQuery,
          grouped: false
        }) as PaginatedLogs;
        
        if (res && res.items) {
          setLogs(res.items);
          setTotalPages(res.total_pages || 1);
          setTotalMatching(res.total || 0);
        }
      }

      const sumData = await api.getLogSummary();
      setSummary(sumData);
    } catch (e) {
      console.error('Failed to fetch logs:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, pageSize, selectedService, selectedLevel, isGroupedView]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const handleGenerateLogs = async (count: number, scenario: string) => {
    setIsGenerating(true);
    setGenMessage(`Generating & ingesting ${count.toLocaleString()} logs...`);
    try {
      const res = await api.generateLogs(count, scenario, true);
      setGenMessage(res.message);
      await fetchLogs();
      setTimeout(() => setGenMessage(null), 4500);
    } catch (e: any) {
      setGenMessage(`Failed: ${e.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleClearLogs = async () => {
    if (window.confirm('Clear in-memory log buffer and fingerprint stats?')) {
      await api.clearLogs();
      fetchLogs();
    }
  };

  const getLevelBadge = (level: string) => {
    switch (level.toUpperCase()) {
      case 'CRITICAL':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">CRITICAL</span>;
      case 'ERROR':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">ERROR</span>;
      case 'WARNING':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">WARNING</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">INFO</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="h-5 w-5 text-cyan-400" />
            <span>Log Intelligence & High-Throughput Stream</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time ingestion, SHA256 fingerprint deduplication, and anomaly correlation capable of 100,000+ events.
          </p>
        </div>

        {/* Generator Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleGenerateLogs(10000, 'database_storm')}
            disabled={isGenerating}
            className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Simulate 10,000 Logs</span>
          </button>

          <button
            onClick={() => handleGenerateLogs(50000, 'database_storm')}
            disabled={isGenerating}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />
            <span>50,000 Logs</span>
          </button>

          <button
            onClick={handleClearLogs}
            className="p-2 rounded-xl bg-slate-900 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-slate-800 transition"
            title="Clear in-memory buffer"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {genMessage && (
        <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-semibold flex items-center gap-2 animate-bounce">
          <CheckCircle2 className="h-4 w-4" />
          <span>{genMessage}</span>
        </div>
      )}

      {/* KPI Stats Bar */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
          <div className="p-4 rounded-xl glass-card">
            <p className="text-[11px] text-slate-400 font-medium">Total Ingested</p>
            <p className="text-xl font-extrabold text-white mt-1">{summary.total_logs.toLocaleString()}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Ring buffer indexed</p>
          </div>

          <div className="p-4 rounded-xl glass-card">
            <p className="text-[11px] text-slate-400 font-medium">Errors & Critical</p>
            <p className="text-xl font-extrabold text-rose-400 mt-1">
              {(summary.by_level.ERROR + summary.by_level.CRITICAL).toLocaleString()}
            </p>
            <p className="text-[10px] text-rose-500/80 mt-0.5">{summary.by_level.CRITICAL} Critical</p>
          </div>

          <div className="p-4 rounded-xl glass-card">
            <p className="text-[11px] text-slate-400 font-medium">Warnings</p>
            <p className="text-xl font-extrabold text-amber-400 mt-1">{summary.by_level.WARNING.toLocaleString()}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Threshold anomalies</p>
          </div>

          <div className="p-4 rounded-xl glass-card">
            <p className="text-[11px] text-slate-400 font-medium">Unique Fingerprints</p>
            <p className="text-xl font-extrabold text-indigo-400 mt-1">{summary.unique_fingerprints}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Deduplicated clusters</p>
          </div>

          <div className="p-4 rounded-xl glass-card col-span-2 md:col-span-1">
            <p className="text-[11px] text-slate-400 font-medium">Memory Ring Buffer</p>
            <p className="text-xl font-extrabold text-emerald-400 mt-1">{summary.buffer_usage.toLocaleString()}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">/ {summary.buffer_capacity.toLocaleString()} max</p>
          </div>
        </div>
      )}

      {/* Filter and View Toggles Bar */}
      <div className="p-4 rounded-2xl glass-panel space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1">
            <div className="relative flex-1">
              <Search className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search logs by message, trace ID, or event type..."
                className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold transition"
            >
              Filter
            </button>
          </form>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1.5 bg-slate-900/90 p-1 rounded-xl border border-slate-800 text-xs">
            <button
              onClick={() => setIsGroupedView(false)}
              className={`px-3 py-1.5 rounded-lg font-medium transition ${!isGroupedView ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Stream View (Paginated)
            </button>
            <button
              onClick={() => setIsGroupedView(true)}
              className={`px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 ${isGroupedView ? 'bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200'}`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Grouped Fingerprints</span>
            </button>
          </div>
        </div>

        {/* Dropdown Filters (Stream Mode) */}
        {!isGroupedView && (
          <div className="flex items-center gap-3 flex-wrap pt-2 border-t border-slate-800/80 text-xs text-slate-400">
            <div className="flex items-center gap-1.5">
              <span>Service:</span>
              <select
                value={selectedService}
                onChange={(e) => { setSelectedService(e.target.value); setPage(1); }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200"
              >
                <option value="all">All Services</option>
                <option value="gateway">Gateway (8001)</option>
                <option value="service-a">Service A (8002)</option>
                <option value="service-b">Service B (8003)</option>
                <option value="database-service">Database Service (8004)</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <span>Severity:</span>
              <select
                value={selectedLevel}
                onChange={(e) => { setSelectedLevel(e.target.value); setPage(1); }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200"
              >
                <option value="all">All Levels</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 ml-auto">
              <span>Page Size:</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200"
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Logs Display Section */}
      <div className="p-6 rounded-2xl glass-panel space-y-4">
        {isGroupedView ? (
          /* Grouped Fingerprint Clusters */
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-indigo-400" />
                <span>Grouped Event Fingerprint Clusters ({fingerprints.length})</span>
              </h3>
              <span className="text-xs text-slate-400">Deduplicated SHA256 clusters from 10,000+ stream</span>
            </div>

            {fingerprints.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-xs">
                No logs recorded yet. Click 'Simulate 10,000 Logs' above to generate events.
              </div>
            ) : (
              <div className="space-y-2.5">
                {fingerprints.map((fp) => (
                  <div key={fp.fingerprint} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition space-y-2">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {getLevelBadge(fp.level)}
                        <span className="font-mono font-bold text-cyan-400 text-xs">{fp.event_type}</span>
                        <span className="text-xs text-slate-400">on <strong className="text-slate-200 capitalize">{fp.service}</strong></span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-mono font-bold">
                          {fp.occurrences.toLocaleString()} occurrences
                        </span>
                        <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-0.5 rounded">
                          FP: {fp.fingerprint}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs font-mono text-slate-300 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
                      {fp.sample_message}
                    </p>

                    <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                      <span>First Seen: {fp.first_seen.split('T')[1]?.split('.')[0] || fp.first_seen}</span>
                      <span>Last Seen: {fp.last_seen.split('T')[1]?.split('.')[0] || fp.last_seen}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Stream View (Paginated Table) */
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs text-slate-400">
                Showing {logs.length} of {totalMatching.toLocaleString()} matching events
              </span>
              
              {/* Pagination Controls */}
              <div className="flex items-center gap-2 text-xs">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1 || isLoading}
                  className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 transition"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="font-mono text-slate-300 font-medium">Page {page} of {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isLoading}
                  className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 transition"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left font-mono">
                <thead className="text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Service</th>
                    <th className="py-2.5 px-3">Level</th>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Trace ID</th>
                    <th className="py-2.5 px-3">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-[11px]">
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400 font-sans">
                        No log records match the current filters.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap text-[10px]">
                          {log.timestamp.split('T')[1]?.split('.')[0] || log.timestamp}
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 capitalize">{log.service}</td>
                        <td className="py-2.5 px-3">{getLevelBadge(log.level)}</td>
                        <td className="py-2.5 px-3 text-cyan-400 font-bold">{log.event_type}</td>
                        <td className="py-2.5 px-3 text-slate-500 text-[10px]">{log.trace_id}</td>
                        <td className="py-2.5 px-3 text-slate-300 max-w-md truncate font-sans text-xs">
                          {log.message}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

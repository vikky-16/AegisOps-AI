import React, { useState, useEffect } from 'react';
import { 
  HardDrive, 
  Archive, 
  CheckCircle2, 
  Sparkles, 
  Database 
} from 'lucide-react';
import type { StorageStatus } from '../types';
import { api } from '../services/api';

export const StoragePage: React.FC = () => {
  const [storageData, setStorageData] = useState<StorageStatus | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizeResult, setOptimizeResult] = useState<any | null>(null);

  const fetchStorage = async () => {
    try {
      const data = await api.getStorage();
      setStorageData(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchStorage();
  }, []);

  const handleOptimize = async () => {
    setIsOptimizing(true);
    try {
      const res = await api.optimizeStorage();
      setOptimizeResult(res);
      await fetchStorage();
      setTimeout(() => setOptimizeResult(null), 5000);
    } catch (e: any) {
      console.error(e);
    } finally {
      setIsOptimizing(false);
    }
  };

  if (!storageData) {
    return <div className="text-center py-12 text-slate-400">Loading storage intelligence metrics...</div>;
  }

  const isWarning = storageData.used_percentage >= 75.0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <HardDrive className="h-5 w-5 text-amber-400" />
            <span>Storage Intelligence & Growth Forecasting</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Automated disk capacity forecasting, log rotation, gzip compression, and non-destructive archival.
          </p>
        </div>

        <button
          onClick={handleOptimize}
          disabled={isOptimizing}
          className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-cyan-500 hover:from-amber-400 hover:to-cyan-400 text-slate-950 font-bold text-xs shadow-lg shadow-amber-500/20 transition flex items-center gap-2"
        >
          <Archive className="h-4 w-4" />
          <span>{isOptimizing ? 'Compressing & Archiving...' : 'Optimize Storage & Compress Logs'}</span>
        </button>
      </div>

      {optimizeResult && (
        <div className="p-4 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center gap-2 animate-bounce">
          <CheckCircle2 className="h-4 w-4" />
          <span>{optimizeResult.message}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl glass-card">
          <p className="text-xs text-slate-400">Used Storage</p>
          <p className="text-2xl font-extrabold text-white mt-2">{storageData.used_gb} GB</p>
          <p className="text-[11px] text-slate-400 mt-1">of {storageData.total_gb} GB capacity ({storageData.used_percentage}%)</p>
        </div>

        <div className="p-5 rounded-xl glass-card">
          <p className="text-xs text-slate-400">Growth Velocity</p>
          <p className="text-2xl font-extrabold text-amber-400 mt-2">+{storageData.growth_rate_gb_per_hour} GB/h</p>
          <p className="text-[11px] text-slate-400 mt-1">Linear trend extrapolation</p>
        </div>

        <div className="p-5 rounded-xl glass-card">
          <p className="text-xs text-slate-400">Estimated Critical Point (95%)</p>
          <p className="text-2xl font-extrabold text-cyan-400 mt-2">~{storageData.predicted_critical_hours} Hours</p>
          <p className="text-[11px] text-slate-400 mt-1">Sustained load threshold</p>
        </div>

        <div className="p-5 rounded-xl glass-card">
          <p className="text-xs text-slate-400">Reclaimable Candidate</p>
          <p className="text-2xl font-extrabold text-emerald-400 mt-2">~18.2 GB</p>
          <p className="text-[11px] text-slate-400 mt-1">Application logs &gt; 14 days</p>
        </div>
      </div>

      {/* Visual Capacity Bar & Recommendation */}
      <div className="p-6 rounded-2xl glass-panel space-y-4">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-200">Disk Volume Allocation</span>
          <span className="font-mono text-slate-400">{storageData.used_gb} GB / {storageData.total_gb} GB</span>
        </div>

        <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden flex">
          <div 
            className={`h-full transition-all duration-700 ${isWarning ? 'bg-amber-400' : 'bg-cyan-400'}`}
            style={{ width: `${storageData.used_percentage}%` }}
          ></div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-bold text-white">Storage Intelligence Recommendation</h4>
            <p className="text-xs text-slate-300 mt-0.5">{storageData.recommendation}</p>
          </div>
        </div>
      </div>

      {/* Top Consumers Table */}
      <div className="p-6 rounded-2xl glass-panel space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Database className="h-4 w-4 text-cyan-400" />
          <span>Top Storage Consumers Breakdown</span>
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider font-mono">
              <tr>
                <th className="py-2.5 px-3">Resource / Tablespace</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Size (GB)</th>
                <th className="py-2.5 px-3">Volume Share</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {storageData.top_consumers?.map((c, idx) => (
                <tr key={idx} className="hover:bg-slate-900/40">
                  <td className="py-3 px-3 font-semibold text-slate-200">{c.name}</td>
                  <td className="py-3 px-3">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">
                      {c.category}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-200">{c.size_gb} GB</td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-cyan-400 h-full" style={{ width: `${c.percentage}%` }}></div>
                      </div>
                      <span className="font-mono text-slate-400 text-[10px]">{c.percentage}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  AlertTriangle, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Radio, 
  Database, 
  Activity, 
  Layers, 
  Server, 
  Lock, 
  Cpu
} from 'lucide-react';
import { api } from '../../services/api';
import type { SystemConsistencyAudit } from '../../types';

interface SystemConsistencyPanelProps {
  tenantId?: string;
  onRefreshTrigger?: () => void;
}

export const SystemConsistencyPanel: React.FC<SystemConsistencyPanelProps> = ({ 
  tenantId = 'shopsphere', 
  onRefreshTrigger 
}) => {
  const [audit, setAudit] = useState<SystemConsistencyAudit | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastChecked, setLastChecked] = useState<string>('');
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const data = await api.getSystemConsistency(tenantId);
      setAudit(data);
      const now = new Date();
      setLastChecked(now.toLocaleTimeString());
    } catch (err) {
      console.error('Failed to run consistency audit', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
    if (!autoRefresh) return;
    const interval = setInterval(fetchAudit, 8000);
    return () => clearInterval(interval);
  }, [tenantId, autoRefresh]);

  const items = [
    { key: 'service_status', label: 'Backend State', desc: 'Canonical state matching', icon: Server },
    { key: 'telemetry', label: 'Telemetry', desc: 'Freshness & Truth rules', icon: Radio },
    { key: 'incidents', label: 'Incident State', desc: 'Pipeline & DB sync', icon: AlertTriangle },
    { key: 'approvals', label: 'Approval State', desc: 'Governance sync', icon: ShieldCheck },
    { key: 'recovery', label: 'Recovery State', desc: 'Stage machine integrity', icon: RefreshCw },
    { key: 'dependencies', label: 'Dependency Graph', desc: 'Topology & node states', icon: Layers },
    { key: 'ml', label: 'ML State', desc: 'Ensemble health & episodes', icon: Cpu },
    { key: 'tenant_isolation', label: 'Tenant Isolation', desc: 'Boundary enforcement', icon: Lock },
    { key: 'timestamps', label: 'Real-time Sync', desc: 'UTC timestamps & causal order', icon: Activity },
  ];

  const isAllPass = audit?.status === 'PASS';

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 backdrop-blur-md">
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isAllPass ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
            {isAllPass ? <ShieldCheck className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold tracking-wide uppercase text-slate-200">
                SYSTEM CONSISTENCY
              </h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider ${
                isAllPass 
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse'
              }`}>
                {isAllPass ? 'PASS' : 'FAIL'}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Single Source of Truth Audit across 9 subsystems ({audit?.total_services_audited ?? 7} services audited)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">
            Last verified: <span className="text-slate-200 font-semibold">{lastChecked || 'Checking...'}</span>
          </span>
          <button
            onClick={() => {
              fetchAudit();
              if (onRefreshTrigger) onRefreshTrigger();
            }}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition border border-slate-700 disabled:opacity-50"
            title="Re-run Diagnostic Audit"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {items.map((it) => {
          const pass = audit ? (audit.checks as any)[it.key] === 'PASS' : true;
          const IconComponent = it.icon;
          return (
            <div
              key={it.key}
              className={`flex items-center justify-between p-3 rounded-lg border transition ${
                pass 
                  ? 'bg-slate-950/40 border-slate-800/80 hover:border-slate-700' 
                  : 'bg-rose-950/20 border-rose-900/50'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className={`w-2 h-2 rounded-full ${pass ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-rose-400 shadow-[0_0_8px_rgba(251,113,133,0.6)]'}`} />
                <div>
                  <span className="text-xs font-medium text-slate-200 block">{it.label}</span>
                  <span className="text-[10px] text-slate-500 block">{it.desc}</span>
                </div>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider ${
                pass 
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
              }`}>
                {pass ? 'PASS' : 'FAIL'}
              </span>
            </div>
          );
        })}
      </div>

      {audit && audit.discrepancies && audit.discrepancies.length > 0 && (
        <div className="mt-4 p-3 rounded-lg bg-rose-950/30 border border-rose-800/50">
          <div className="flex items-center gap-2 text-xs font-semibold text-rose-400 mb-1.5">
            <XCircle className="w-4 h-4 text-rose-400" />
            Detected Operational Discrepancies ({audit.discrepancies.length}):
          </div>
          <ul className="text-xs text-rose-300/90 space-y-1 pl-5 list-disc font-mono">
            {audit.discrepancies.map((d, idx) => (
              <li key={idx}>{d}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

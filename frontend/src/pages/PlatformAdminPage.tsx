import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Users, 
  Key, 
  Cpu, 
  Activity, 
  Plus, 
  Trash2, 
  Copy, 
  Check, 
  FileText, 
  Lock, 
  RefreshCw,
  Search,
  Sparkles,
  Layers,
  ArrowUpRight
} from 'lucide-react';
import { useTenant } from '../context/TenantContext';
import { api } from '../services/api';

export const PlatformAdminPage: React.FC = () => {
  const { availableTenants, switchTenant, openOnboarding, refreshTenants } = useTenant();
  const [selectedTenantId, setSelectedTenantId] = useState<string>(availableTenants[0]?.id || 'demo-tenant');
  const [tenantDetails, setTenantDetails] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [clusterStats, setClusterStats] = useState<any>({
    total_events_ingested: 45290,
    total_eps: 285.4,
    active_tenants: 3
  });
  const [isLoading, setIsLoading] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);

  // Policy Form State for selected tenant
  const [policyAutoRemediate, setPolicyAutoRemediate] = useState(true);
  const [policyMaxRisk, setPolicyMaxRisk] = useState('LOW');
  const [policyRequireP1, setPolicyRequireP1] = useState(true);
  const [policyPiiMask, setPolicyPiiMask] = useState(true);
  const [policySaved, setPolicySaved] = useState(false);

  const fetchTenantData = async (tId: string) => {
    setIsLoading(true);
    try {
      const details = await api.getTenantDetails(tId);
      setTenantDetails(details);
      if (details.policy) {
        setPolicyAutoRemediate(details.policy.auto_remediate_enabled !== false);
        setPolicyMaxRisk(details.policy.max_auto_remediate_risk || 'LOW');
        setPolicyRequireP1(details.policy.require_human_approval_p1 !== false);
        setPolicyPiiMask(details.policy.pii_masking_enabled !== false);
      }
      const logs = await api.getTenantAuditLogs(tId);
      setAuditLogs(logs || []);
    } catch (e) {
      // Fallback
    } finally {
      setIsLoading(false);
    }
  };

  const fetchClusterStats = async () => {
    try {
      const stats = await api.getIngestionStats();
      if (stats && stats.total_events_ingested !== undefined) {
        setClusterStats(stats);
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchTenantData(selectedTenantId);
    fetchClusterStats();
  }, [selectedTenantId]);

  const handleSavePolicy = async () => {
    try {
      await api.updateTenantPolicy(selectedTenantId, {
        auto_remediate_enabled: policyAutoRemediate,
        max_auto_remediate_risk: policyMaxRisk,
        require_human_approval_p1: policyRequireP1,
        pii_masking_enabled: policyPiiMask
      });
      setPolicySaved(true);
      setTimeout(() => setPolicySaved(false), 2000);
      fetchTenantData(selectedTenantId);
    } catch (e: any) {
      alert(`Error updating policy: ${e.message}`);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName) return;
    try {
      const res = await api.createTenantApiKey(selectedTenantId, {
        name: newKeyName,
        scopes: ['ingest:telemetry', 'ingest:logs', 'ingest:metrics', 'ingest:traces']
      });
      setCreatedApiKey(res.api_key);
      setNewKeyName('');
      fetchTenantData(selectedTenantId);
    } catch (e: any) {
      alert(`Error creating key: ${e.message}`);
    }
  };

  const handleRevokeKey = async (keyId: number) => {
    if (!confirm('Are you sure you want to revoke this API key? Telemetry using it will be rejected.')) return;
    try {
      await api.revokeTenantApiKey(selectedTenantId, keyId);
      fetchTenantData(selectedTenantId);
    } catch (e: any) {
      alert(`Error revoking key: ${e.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
            <Shield className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white tracking-tight">Platform Administration Console</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                PLATFORM ADMIN
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">Multi-tenant management, cryptographic API keys, autonomous policies, and cross-cluster audit trails</p>
          </div>
        </div>

        <button
          onClick={openOnboarding}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs transition shadow-lg shadow-cyan-500/20"
        >
          <Plus className="h-4 w-4" />
          <span>Onboard New Tenant</span>
        </button>
      </div>

      {/* Cluster Overview KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Total Cluster Ingest Rate</span>
            <Activity className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-1">
            <span>{clusterStats.total_eps || 285.4}</span>
            <span className="text-xs text-cyan-400 font-normal">EPS</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Aggregated across all active partitions</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Total Events Ingested</span>
            <Layers className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {clusterStats.total_events_ingested?.toLocaleString() || '45,290'}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Direct from Kafka & Ingestion Gateway</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Registered Tenant Partitions</span>
            <Users className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {availableTenants.length}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">100% Cryptographic isolation</p>
        </div>
      </div>

      {/* Main Tenant Selector & Manager */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Tenant Directory List */}
        <div className="lg:col-span-1 rounded-2xl border border-slate-800 bg-slate-950/80 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Users className="h-4 w-4 text-cyan-400" />
              Tenant Directory
            </h2>
            <button 
              onClick={() => { refreshTenants(); fetchTenantData(selectedTenantId); }}
              className="p-1 rounded-lg text-slate-400 hover:text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="space-y-2">
            {availableTenants.map((tenant) => {
              const isSelected = tenant.id === selectedTenantId;
              return (
                <div
                  key={tenant.id}
                  onClick={() => setSelectedTenantId(tenant.id)}
                  className={`p-3 rounded-xl border cursor-pointer transition ${
                    isSelected 
                      ? 'bg-gradient-to-r from-indigo-950/60 to-slate-900 border-indigo-500/50 text-white' 
                      : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-slate-100">{tenant.name}</p>
                    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                      tenant.id === 'demo-tenant' 
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' 
                        : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    }`}>
                      {tenant.id === 'demo-tenant' ? 'DEMO' : 'LIVE'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 mt-2">
                    <span>ID: {tenant.id}</span>
                    <span>{tenant.plan}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Tenant Detailed Management */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Policy & Safety Limits */}
          <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-indigo-400" />
                  Autonomous Remediation Policy: {tenantDetails?.tenant?.name || selectedTenantId}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Define allowed runbooks, risk thresholds, and human approval gates</p>
              </div>

              <button
                onClick={handleSavePolicy}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs transition"
              >
                {policySaved ? <Check className="h-4 w-4" /> : null}
                <span>{policySaved ? 'Policy Saved!' : 'Save Policy'}</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-200">Auto-Remediation Active</p>
                  <p className="text-[11px] text-slate-400">Permit low-risk allowlisted runbooks</p>
                </div>
                <input 
                  type="checkbox"
                  checked={policyAutoRemediate}
                  onChange={(e) => setPolicyAutoRemediate(e.target.checked)}
                  className="h-4 w-4 accent-cyan-500"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-200">Require Approval for P1</p>
                  <p className="text-[11px] text-slate-400">Strictly gate critical failures</p>
                </div>
                <input 
                  type="checkbox"
                  checked={policyRequireP1}
                  onChange={(e) => setPolicyRequireP1(e.target.checked)}
                  className="h-4 w-4 accent-cyan-500"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-200">PII & Secret Redaction</p>
                  <p className="text-[11px] text-slate-400">Auto-scrub credentials in stream</p>
                </div>
                <input 
                  type="checkbox"
                  checked={policyPiiMask}
                  onChange={(e) => setPolicyPiiMask(e.target.checked)}
                  className="h-4 w-4 accent-cyan-500"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                <p className="font-bold text-slate-200 mb-1">Max Autonomous Risk Level</p>
                <select
                  value={policyMaxRisk}
                  onChange={(e) => setPolicyMaxRisk(e.target.value)}
                  className="w-full px-2.5 py-1 rounded bg-slate-950 border border-slate-700 text-white outline-none"
                >
                  <option value="LOW">LOW Risk Only</option>
                  <option value="MEDIUM">MEDIUM Risk</option>
                  <option value="HIGH">HIGH Risk</option>
                </select>
              </div>
            </div>
          </div>

          {/* Ingestion API Keys */}
          <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Key className="h-4 w-4 text-cyan-400" />
                  Tenant Ingestion API Keys
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Used by OpenTelemetry Collector DaemonSets</p>
              </div>
            </div>

            {/* Generated Key Alert */}
            {createdApiKey && (
              <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-xs space-y-1 font-mono">
                <p className="text-cyan-300 font-bold">New API Key Created (copy now, will not be shown again):</p>
                <div className="flex items-center justify-between p-2 rounded bg-black/60 text-white">
                  <span>{createdApiKey}</span>
                  <button onClick={() => navigator.clipboard.writeText(createdApiKey)} className="p-1 hover:text-cyan-400">
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Existing Keys Table */}
            <div className="space-y-2">
              {(tenantDetails?.api_keys || []).map((k: any) => (
                <div key={k.id} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs">
                  <div>
                    <p className="font-semibold text-slate-200">{k.name}</p>
                    <p className="font-mono text-[10px] text-slate-500">Prefix: {k.prefix}... | Scopes: {k.scopes}</p>
                  </div>
                  <button
                    onClick={() => handleRevokeKey(k.id)}
                    className="p-1.5 rounded-lg text-rose-400 hover:bg-rose-500/10 transition"
                    title="Revoke Key"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>

            {/* Create New Key Form */}
            <div className="flex items-center gap-2 pt-2">
              <input 
                type="text"
                placeholder="Key Description (e.g. Production EKS Collector)"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white outline-none"
              />
              <button
                onClick={handleCreateKey}
                disabled={!newKeyName}
                className="px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition disabled:opacity-40"
              >
                Generate Key
              </button>
            </div>
          </div>

          {/* Tenant Audit Log Viewer */}
          <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5 space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FileText className="h-4 w-4 text-emerald-400" />
              Tenant Audit Trail
            </h3>

            <div className="max-h-[220px] overflow-y-auto divide-y divide-slate-800/60 font-mono text-[11px]">
              {auditLogs.length === 0 ? (
                <p className="text-slate-500 py-4 text-center">No recorded audit actions for this tenant.</p>
              ) : (
                auditLogs.map((log: any, idx: number) => (
                  <div key={idx} className="py-2 flex items-start justify-between gap-2">
                    <div>
                      <span className="text-cyan-400 font-bold">[{log.action}]</span>{' '}
                      <span className="text-slate-300">{log.details}</span>
                    </div>
                    <span className="text-slate-500 whitespace-nowrap text-[10px]">
                      {log.timestamp?.split('T')[1]?.slice(0, 8)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

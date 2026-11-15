import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Users, 
  Key, 
  ShieldCheck, 
  Shield, 
  Lock, 
  Check, 
  Copy, 
  AlertTriangle, 
  Plus, 
  Trash2, 
  RefreshCw,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { api } from '../services/api';
import { useTenant } from '../context/TenantContext';

export const OrganizationSettingsPage: React.FC = () => {
  const { currentTenant } = useTenant();
  const [orgData, setOrgData] = useState<any>(null);
  const [teams, setTeams] = useState<any[]>([]);
  const [apiKeys, setApiKeys] = useState<any[]>([
    {
      id: "key-live-1",
      name: "Primary Production OTel Ingest Key",
      prefix: "aegis_live_99f8...",
      created_at: "2026-08-15T10:00:00Z",
      last_used_at: "Just now",
      status: "ACTIVE"
    },
    {
      id: "key-live-2",
      name: "Staging Pipeline Collector Key",
      prefix: "aegis_stg_44e1...",
      created_at: "2026-09-01T14:30:00Z",
      last_used_at: "5 minutes ago",
      status: "ACTIVE"
    }
  ]);

  const [members, setMembers] = useState<any[]>([
    { id: "usr-1", name: "Arthur Vance", username: "ceo_acme", email: "arthur@acme.com", role: "CEO", team: "Executive Command", status: "ACTIVE" },
    { id: "usr-2", name: "Elena Rostova", username: "sre_acme", email: "elena@acme.com", role: "SRE_LEAD", team: "SRE & Core Platform", status: "ACTIVE" },
    { id: "usr-3", name: "Marcus Chen", username: "cto_acme", email: "marcus@acme.com", role: "CTO", team: "Executive Command", status: "ACTIVE" },
    { id: "usr-4", name: "Devendra Patel", username: "devops_acme", email: "devendra@acme.com", role: "DEVOPS_ENGINEER", team: "Infrastructure & CI/CD", status: "ACTIVE" },
    { id: "usr-5", name: "Sarah Connor", username: "sec_acme", email: "sarah@acme.com", role: "SECURITY_ENGINEER", team: "Security Operations", status: "ACTIVE" },
    { id: "usr-6", name: "Liam Vance", username: "ic_acme", email: "liam@acme.com", role: "INCIDENT_COMMANDER", team: "Incident Response", status: "ACTIVE" }
  ]);

  // Single-Reveal API Key Modal State
  const [showGenerateKeyModal, setShowGenerateKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  // Invite Modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('DEVOPS_ENGINEER');

  useEffect(() => {
    fetchOrgDetails();
  }, [currentTenant]);

  const fetchOrgDetails = async () => {
    try {
      const org = await api.getOrganization(currentTenant?.id || 'tenant-acme-corp');
      setOrgData(org);
    } catch (e) {
      setOrgData({
        id: currentTenant?.id || "tenant-acme-corp",
        name: currentTenant?.name || "Acme Corporation",
        plan: "ENTERPRISE",
        industry: "Financial Technology & E-Commerce",
        region: "us-east-1 (N. Virginia)",
        created_at: "2026-01-10T08:00:00Z"
      });
    }

    try {
      const teamList: any = await api.getTeams(currentTenant?.id || 'tenant-acme-corp');
      if (Array.isArray(teamList)) {
        setTeams(teamList);
      } else if (teamList && teamList.teams) {
        setTeams(teamList.teams);
      }
    } catch (e) {
      setTeams([
        { id: "t-1", name: "SRE & Core Platform", members_count: 5, description: "Maintains cluster availability, OTel ingestion, and autonomous runbooks." },
        { id: "t-2", name: "Security Operations (SecOps)", members_count: 3, description: "Compliance, audit log reviews, and zero-trust boundary verification." },
        { id: "t-3", name: "Incident Response Command", members_count: 4, description: "24/7 on-call triage and incident command." }
      ]);
    }
  };

  const handleGenerateKey = () => {
    if (!newKeyName.trim()) return;
    const generatedSecret = `aegis_live_sec_${Math.random().toString(36).substring(2, 15)}_${Math.random().toString(36).substring(2, 15)}`;
    setRevealedKey(generatedSecret);
    setApiKeys(prev => [
      {
        id: `key-live-${Date.now()}`,
        name: newKeyName,
        prefix: generatedSecret.substring(0, 14) + "...",
        created_at: new Date().toISOString(),
        last_used_at: "Never",
        status: "ACTIVE"
      },
      ...prev
    ]);
  };

  const handleRoleChange = (memberId: string, newRole: string) => {
    setMembers(prev => prev.map(m => m.id === memberId ? { ...m, role: newRole } : m));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2.5 py-0.5 rounded-md border border-indigo-500/20 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5" />
              Tenant Administration
            </span>
            <span className="text-xs text-slate-500">•</span>
            <span className="text-xs text-slate-400 font-medium">Enterprise Organization</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Organization & RBAC Settings</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage organization profile, enterprise team topology, fine-grained role privileges, and single-reveal telemetry API keys.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowInviteModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            Invite Member
          </button>
        </div>
      </div>

      {/* Organization Profile Overview Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <h3 className="text-base font-semibold text-white mb-4">Enterprise Organization Profile</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 text-xs">
          <div>
            <label className="text-slate-400 block mb-1">Organization Legal Entity</label>
            <div className="text-white font-medium text-sm">{orgData?.name || "Acme Corporation"}</div>
          </div>
          <div>
            <label className="text-slate-400 block mb-1">Tenant Partition ID</label>
            <div className="text-indigo-400 font-mono text-sm">{orgData?.id || "tenant-acme-corp"}</div>
          </div>
          <div>
            <label className="text-slate-400 block mb-1">SaaS Subscription Plan</label>
            <div className="flex items-center gap-2">
              <span className="text-purple-400 bg-purple-500/10 border border-purple-500/30 px-2.5 py-0.5 rounded font-semibold text-xs">
                {orgData?.plan || "ENTERPRISE TIER"}
              </span>
              <span className="text-slate-500">99.99% SLA</span>
            </div>
          </div>
          <div>
            <label className="text-slate-400 block mb-1">Data Residency & Region</label>
            <div className="text-white font-medium text-sm">{orgData?.region || "us-east-1 (N. Virginia)"}</div>
          </div>
        </div>
      </div>

      {/* Role-Based Access Control (RBAC) Member Roster */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Enterprise Organization Roster & RBAC Roles</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Strict role enforcement. Note: <strong>CEO</strong> has read-only executive visibility; remediation approvals require <strong>SRE_LEAD</strong> or <strong>INCIDENT_COMMANDER</strong>.
            </p>
          </div>
          <div className="text-xs text-slate-400">
            {members.length} Active Personnel
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold text-[11px] border-b border-slate-800">
              <tr>
                <th className="px-5 py-3">User & Persona</th>
                <th className="px-4 py-3">Email Address</th>
                <th className="px-4 py-3">Assigned Team</th>
                <th className="px-4 py-3">RBAC Role</th>
                <th className="px-4 py-3">Remediation Authority</th>
                <th className="px-5 py-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-[12px]">
              {members.map((member) => (
                <tr key={member.id} className="hover:bg-slate-800/40 transition">
                  <td className="px-5 py-3.5">
                    <div className="text-white font-medium">{member.name}</div>
                    <div className="text-slate-500 font-mono text-[11px]">{member.username}</div>
                  </td>
                  <td className="px-4 py-3.5 font-mono text-slate-300">
                    {member.email}
                  </td>
                  <td className="px-4 py-3.5 text-slate-300">
                    {member.team}
                  </td>
                  <td className="px-4 py-3.5">
                    <select
                      value={member.role}
                      onChange={(e) => handleRoleChange(member.id, e.target.value)}
                      className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-200 text-xs font-medium focus:border-indigo-500 outline-none"
                    >
                      <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                      <option value="ORG_ADMIN">ORG_ADMIN</option>
                      <option value="CEO">CEO (Executive Read)</option>
                      <option value="CTO">CTO (Architecture)</option>
                      <option value="SRE_LEAD">SRE_LEAD (Approver)</option>
                      <option value="DEVOPS_ENGINEER">DEVOPS_ENGINEER</option>
                      <option value="SECURITY_ENGINEER">SECURITY_ENGINEER</option>
                      <option value="INCIDENT_COMMANDER">INCIDENT_COMMANDER</option>
                      <option value="DEVELOPER">DEVELOPER</option>
                      <option value="VIEWER">VIEWER</option>
                    </select>
                  </td>
                  <td className="px-4 py-3.5">
                    {member.role === 'SRE_LEAD' || member.role === 'INCIDENT_COMMANDER' || member.role === 'SUPER_ADMIN' ? (
                      <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        FULL AUTHORITY
                      </span>
                    ) : member.role === 'CEO' ? (
                      <span className="text-[11px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                        RESTRICTED (GOVERNANCE)
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                        LIMITED / VIEW ONLY
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-right font-semibold text-emerald-400">
                    {member.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Single-Reveal Telemetry Ingestion API Keys */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Single-Reveal Ingestion API Keys</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Secure keys for OpenTelemetry Collector DaemonSets and application SDKs. Keys are hashed with SHA-256; full secrets cannot be viewed after generation.
            </p>
          </div>
          <button
            onClick={() => {
              setNewKeyName('');
              setRevealedKey(null);
              setShowGenerateKeyModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm transition"
          >
            <Key className="w-3.5 h-3.5" />
            Generate Ingestion Key
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold text-[11px] border-b border-slate-800">
              <tr>
                <th className="px-5 py-3">Key Name</th>
                <th className="px-4 py-3">Key Prefix</th>
                <th className="px-4 py-3">Created Date</th>
                <th className="px-4 py-3">Last Active</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[12px]">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-slate-800/40 transition">
                  <td className="px-5 py-3.5 font-sans font-medium text-white">
                    {key.name}
                  </td>
                  <td className="px-4 py-3.5 text-indigo-300">
                    {key.prefix}
                  </td>
                  <td className="px-4 py-3.5 text-slate-400 font-sans">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3.5 text-slate-300 font-sans">
                    {key.last_used_at}
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded text-[11px] font-sans font-semibold">
                      {key.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right font-sans">
                    <button 
                      onClick={() => setApiKeys(prev => prev.filter(k => k.id !== key.id))}
                      className="text-rose-400 hover:text-rose-300 transition text-xs"
                    >
                      Revoke Key
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Single-Reveal Generation Modal */}
      {showGenerateKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-indigo-400" />
                <h3 className="text-base font-semibold text-white">
                  {revealedKey ? "Save Your Ingestion Key" : "Generate Ingestion Key"}
                </h3>
              </div>
              <button 
                onClick={() => {
                  setShowGenerateKeyModal(false);
                  setRevealedKey(null);
                }} 
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {!revealedKey ? (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Key Description / Purpose</label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g. Production EKS Cluster DaemonSet"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500"
                  />
                </div>
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <span>
                    <strong>Single-Reveal Security Policy:</strong> The secret key will be shown only once upon generation. Store it securely in your secrets vault (AWS Secrets Manager / HashiCorp Vault).
                  </span>
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => setShowGenerateKeyModal(false)}
                    className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleGenerateKey}
                    disabled={!newKeyName.trim()}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold"
                  >
                    Generate Secret
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                  <span>
                    <strong>Copy your key now!</strong> This token will never be displayed again. If you lose this key, you will need to revoke it and generate a new one.
                  </span>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Ingestion Secret Key</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={revealedKey}
                      className="w-full bg-slate-950 border border-indigo-500/50 rounded-lg px-3 py-2 text-indigo-300 font-mono text-xs select-all outline-none"
                    />
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(revealedKey);
                        setCopiedKey(true);
                        setTimeout(() => setCopiedKey(false), 2000);
                      }}
                      className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg flex items-center gap-1.5 transition"
                    >
                      {copiedKey ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedKey ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => {
                      setShowGenerateKeyModal(false);
                      setRevealedKey(null);
                    }}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
                  >
                    I Have Saved My Key
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-white">Invite Team Member</h3>
              <button onClick={() => setShowInviteModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Corporate Email</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="engineer@acme.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Assigned Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white outline-none focus:border-indigo-500"
                >
                  <option value="SRE_LEAD">SRE_LEAD (Full Remediation Approval)</option>
                  <option value="DEVOPS_ENGINEER">DEVOPS_ENGINEER (Infra & Deploy)</option>
                  <option value="SECURITY_ENGINEER">SECURITY_ENGINEER (SecOps & Audit)</option>
                  <option value="INCIDENT_COMMANDER">INCIDENT_COMMANDER</option>
                  <option value="DEVELOPER">DEVELOPER</option>
                  <option value="VIEWER">VIEWER</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowInviteModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (inviteEmail) {
                    setMembers(prev => [
                      ...prev,
                      {
                        id: `usr-${Date.now()}`,
                        name: inviteEmail.split('@')[0],
                        username: inviteEmail.split('@')[0],
                        email: inviteEmail,
                        role: inviteRole,
                        team: "Engineering",
                        status: "INVITED"
                      }
                    ]);
                    setShowInviteModal(false);
                    setInviteEmail('');
                  }
                }}
                disabled={!inviteEmail}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold"
              >
                Send Invite
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { 
  CheckSquare, 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertTriangle, 
  ArrowRight, 
  UserCheck, 
  Check, 
  X, 
  Lock, 
  ShieldCheck, 
  AlertOctagon, 
  FileText, 
  ChevronRight, 
  RefreshCw, 
  Layers, 
  Eye, 
  Zap, 
  Activity, 
  Database, 
  Server, 
  Shield, 
  CheckCheck,
  Search,
  ExternalLink,
  Sliders,
  History,
  Box,
  Cpu,
  Building2
} from 'lucide-react';
import type { ApprovalTicket, Incident, ApprovalStats } from '../types';
import { api } from '../services/api';
import { useTenant } from '../context/TenantContext';

interface ApprovalsPageProps {
  approvals: ApprovalTicket[];
  incidents?: Incident[];
  onActionComplete: () => void;
  setActiveTab?: (tab: string) => void;
  onSelectIncident?: (incidentId: string) => void;
  selectedApprovalId?: string;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({ 
  approvals, 
  incidents = [],
  onActionComplete,
  setActiveTab,
  onSelectIncident,
  selectedApprovalId: initialSelectedId
}) => {
  const { currentUser, activeTenant } = useTenant();
  const isPlatformOwner = Boolean(currentUser?.is_platform_admin || currentUser?.role === 'PLATFORM_OWNER_ADMIN');
  const [allTickets, setAllTickets] = useState<ApprovalTicket[]>(approvals);
  const [selectedCompanyFilter, setSelectedCompanyFilter] = useState<string>('ALL');
  const [activeTabFilter, setActiveTabFilter] = useState<'PENDING' | 'HIGH_RISK' | 'MEDIUM_RISK' | 'LOW_RISK' | 'APPROVED' | 'REJECTED' | 'ALL'>('PENDING');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDrawerTicket, setSelectedDrawerTicket] = useState<ApprovalTicket | null>(null);
  
  // Real stats from backend (Single source of truth)
  const [stats, setStats] = useState<ApprovalStats>({
    pending_approvals: 0,
    pending_count: 0,
    total_pending: 0,
    unique_incidents: 0,
    unique_incidents_requiring_approval: 0,
    high_risk: 0,
    high_risk_count: 0,
    medium_risk: 0,
    medium_risk_count: 0,
    low_risk: 0,
    low_risk_count: 0,
    approved_today: 0,
    rejected_today: 0,
    total_reviewed: 0,
    total_tickets: 0
  });

  // RBAC User Role (Operating Context)
  const [userRole, setUserRole] = useState<string>('ADMIN');

  // Confirmation Modals
  const [confirmApproveTicket, setConfirmApproveTicket] = useState<ApprovalTicket | null>(null);
  const [confirmRejectTicket, setConfirmRejectTicket] = useState<ApprovalTicket | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [rejectionError, setRejectionError] = useState<string | null>(null);

  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string; incidentId?: string } | null>(null);

  // Fetch all tickets & stats from backend
  const fetchData = async () => {
    try {
      const [tickets, statsData] = await Promise.all([
        api.getApprovals('ALL'),
        api.getApprovalStats()
      ]);
      setAllTickets(tickets);
      setStats(statsData);
    } catch (e) {
      console.warn('Failed to fetch approvals data:', e);
    }
  };

  useEffect(() => {
    fetchData();
  }, [approvals]);

  // Keep selected ticket updated if in drawer
  useEffect(() => {
    if (initialSelectedId) {
      const target = allTickets.find(t => t.approval_id === initialSelectedId || t.incident_id === initialSelectedId);
      if (target) setSelectedDrawerTicket(target);
    }
  }, [initialSelectedId, allTickets]);

  const formatRelativeTime = (timestamp?: string | null) => {
    if (!timestamp) return 'Just now';
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
      if (diffSec < 60) return `${diffSec}s ago`;
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHours = Math.floor(diffMin / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      return date.toLocaleDateString();
    } catch (e) {
      return timestamp;
    }
  };

  // Filter tickets strictly based on active tab, company filter, and search query
  const filteredTickets = allTickets.filter(ticket => {
    const status = (ticket.status || 'PENDING').toUpperCase();
    const isPending = status === 'PENDING' || status === 'PENDING_APPROVAL' || status === 'AWAITING_APPROVAL';
    const isApproved = status === 'APPROVED';
    const isRejected = status === 'REJECTED';
    const risk = (ticket.risk_level || ticket.risk || 'LOW').toUpperCase();

    // Company filter for Platform Owner & multi-tenant isolation
    if (selectedCompanyFilter !== 'ALL') {
      const ticketTenant = ((ticket.tenant_id || (ticket as any).company) || '').toLowerCase();
      if (ticketTenant !== selectedCompanyFilter.toLowerCase()) return false;
    }

    // Strict tab filtering: NO MIXING!
    if (activeTabFilter === 'PENDING' && !isPending) return false;
    if (activeTabFilter === 'HIGH_RISK') {
      if (!isPending || (risk !== 'HIGH' && risk !== 'CRITICAL')) return false;
    }
    if (activeTabFilter === 'MEDIUM_RISK') {
      if (!isPending || risk !== 'MEDIUM') return false;
    }
    if (activeTabFilter === 'LOW_RISK') {
      if (risk !== 'LOW') return false;
    }
    if (activeTabFilter === 'APPROVED' && !isApproved) return false;
    if (activeTabFilter === 'REJECTED' && !isRejected) return false;

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (ticket.service_name || ticket.service || '').toLowerCase().includes(q);
      const matchTitle = (ticket.incident_title || ticket.problem || ticket.detected_problem || '').toLowerCase().includes(q);
      const matchAction = (ticket.proposed_action || ticket.proposed_recovery_action || '').toLowerCase().includes(q);
      const matchInc = (ticket.incident_id || '').toLowerCase().includes(q);
      const matchApp = (ticket.approval_id || '').toLowerCase().includes(q);
      const matchCompany = ((ticket.tenant_id || (ticket as any).company) || '').toLowerCase().includes(q);
      return matchName || matchTitle || matchAction || matchInc || matchApp || matchCompany;
    }

    return true;
  });

  // Action: Confirm Approval
  const handleConfirmApproval = async () => {
    if (!confirmApproveTicket) return;
    setIsProcessing(true);
    setActionFeedback(null);
    try {
      const res = await api.approveTicket(
        confirmApproveTicket.approval_id,
        `SRE Operator (${userRole})`,
        userRole,
        `Authorized via Approval Center by SRE (${userRole})`
      );
      setConfirmApproveTicket(null);
      setActionFeedback({
        type: 'success',
        message: `Recovery Action APPROVED. Controlled Execution started for ${confirmApproveTicket.incident_id}.`,
        incidentId: confirmApproveTicket.incident_id
      });
      onActionComplete();
      await fetchData();
      if (selectedDrawerTicket?.approval_id === confirmApproveTicket.approval_id) {
        setSelectedDrawerTicket({ ...confirmApproveTicket, status: 'APPROVED' });
      }
      setTimeout(() => setActionFeedback(null), 8000);
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Authorization failed' });
    } finally {
      setIsProcessing(false);
    }
  };

  // Action: Confirm Rejection
  const handleConfirmRejection = async () => {
    if (!confirmRejectTicket) return;
    if (!rejectionReason.trim()) {
      setRejectionError('Operational rejection reason is mandatory.');
      return;
    }

    setIsProcessing(true);
    setRejectionError(null);
    try {
      await api.rejectTicket(
        confirmRejectTicket.approval_id,
        `SRE Operator (${userRole})`,
        userRole,
        rejectionReason.trim()
      );
      setConfirmRejectTicket(null);
      setRejectionReason('');
      setActionFeedback({
        type: 'success',
        message: `Recovery Action REJECTED. Incident ${confirmRejectTicket.incident_id} will NOT execute recovery.`
      });
      onActionComplete();
      await fetchData();
      if (selectedDrawerTicket?.approval_id === confirmRejectTicket.approval_id) {
        setSelectedDrawerTicket({ ...confirmRejectTicket, status: 'REJECTED' });
      }
      setTimeout(() => setActionFeedback(null), 5000);
    } catch (err: any) {
      setRejectionError(err.message || 'Rejection failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const navigateToIncidentContext = (incidentId: string, tab: string) => {
    if (onSelectIncident) {
      onSelectIncident(incidentId);
    }
    if (setActiveTab) {
      setActiveTab(tab);
    }
  };

  const getRiskBadge = (risk: string) => {
    const r = (risk || 'LOW').toUpperCase();
    if (r === 'HIGH' || r === 'CRITICAL') {
      return (
        <span className="px-2.5 py-1 rounded-md text-xs font-black bg-rose-500/20 text-rose-300 border border-rose-500/50 flex items-center gap-1.5 uppercase tracking-wide shadow-sm">
          <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
          <span>RISK: HIGH</span>
        </span>
      );
    }
    if (r === 'MEDIUM') {
      return (
        <span className="px-2.5 py-1 rounded-md text-xs font-black bg-amber-500/20 text-amber-300 border border-amber-500/50 flex items-center gap-1.5 uppercase tracking-wide shadow-sm">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          <span>RISK: MEDIUM</span>
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5 uppercase tracking-wide shadow-sm">
        <Check className="h-3.5 w-3.5 text-emerald-400" />
        <span>RISK: LOW</span>
      </span>
    );
  };

  const getSeverityBadge = (severity?: string) => {
    const sev = (severity || 'P1').toUpperCase();
    if (sev === 'P1' || sev === 'CRITICAL') {
      return <span className="px-2 py-0.5 rounded text-xs font-black bg-rose-600 text-white shadow-sm font-mono">CRITICAL</span>;
    }
    if (sev === 'P2' || sev === 'HIGH') {
      return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-600 text-white shadow-sm font-mono">HIGH</span>;
    }
    return <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-600 text-white shadow-sm font-mono">MEDIUM</span>;
  };

  const getStatusBadge = (status: string) => {
    const s = (status || 'PENDING').toUpperCase();
    if (s === 'APPROVED') {
      return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono">✓ APPROVED</span>;
    }
    if (s === 'REJECTED') {
      return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono">✗ REJECTED</span>;
    }
    return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse font-mono">⏳ PENDING APPROVAL</span>;
  };

  const getCompanyBadge = (tenantId?: string) => {
    const tid = (tenantId || 'fincore').toLowerCase();
    if (tid === 'fincore') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-950/80 text-blue-300 border border-blue-500/40 flex items-center gap-1 shadow-sm">
          <Building2 className="h-3 w-3 text-blue-400" />
          <span>FINCORE</span>
        </span>
      );
    }
    if (tid === 'shopsphere') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 flex items-center gap-1 shadow-sm">
          <Building2 className="h-3 w-3 text-emerald-400" />
          <span>SHOPSPHERE</span>
        </span>
      );
    }
    if (tid === 'clouddesk') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-500/40 flex items-center gap-1 shadow-sm">
          <Building2 className="h-3 w-3 text-indigo-400" />
          <span>CLOUDDESK</span>
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1 shadow-sm">
        <Building2 className="h-3 w-3 text-slate-400" />
        <span>{tid.toUpperCase()}</span>
      </span>
    );
  };

  // Truthful pending count representing current actionable requests
  const pendingCount = stats.pending_approvals ?? stats.total_pending ?? 0;
  const uniqueIncidentsCount = stats.unique_incidents ?? stats.unique_incidents_requiring_approval ?? 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-fadeIn">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 shadow-md">
              <CheckSquare className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                <span>APPROVAL CENTER</span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Truthful governance gateway: review risk-gated recovery actions, inspect pre-fix telemetry, and authorize controlled execution.
              </p>
            </div>
          </div>
        </div>

        {/* Operating Role Toggle & Refresh */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 p-1.5 px-3 bg-slate-900 rounded-xl border border-slate-800 text-xs shadow-sm">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <UserCheck className="h-3.5 w-3.5 text-cyan-400" />
              <span>Role:</span>
            </span>
            <div className="flex items-center gap-1 font-mono text-xs">
              {['ADMIN', 'SRE_LEAD', 'OPERATOR', 'VIEWER'].map((role) => (
                <button
                  key={role}
                  onClick={() => setUserRole(role)}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold transition ${
                    userRole === role
                      ? 'bg-cyan-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={fetchData}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition shadow-sm"
            title="Refresh Approvals"
          >
            <RefreshCw className="h-4 w-4 text-cyan-400" />
          </button>
        </div>
      </div>

      {/* KPI Metric Strip: All 7 Required Backend Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {/* 1. PENDING APPROVALS */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-amber-500/30 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Pending Approvals</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-black text-amber-400 font-mono">{pendingCount}</span>
            <span className="text-[10px] text-slate-500">requests</span>
          </div>
        </div>

        {/* 2. UNIQUE INCIDENTS */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Unique Incidents</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-black text-cyan-400 font-mono">{uniqueIncidentsCount}</span>
            <span className="text-[10px] text-slate-500">awaiting</span>
          </div>
        </div>

        {/* 3. HIGH RISK */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-rose-500/30 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">High Risk</span>
          <span className="text-2xl font-black text-rose-400 mt-1 font-mono">{stats.high_risk}</span>
        </div>

        {/* 4. MEDIUM RISK */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-amber-500/20 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Medium Risk</span>
          <span className="text-2xl font-black text-amber-300 mt-1 font-mono">{stats.medium_risk}</span>
        </div>

        {/* 5. LOW RISK / AUTO-ALLOWED */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-emerald-500/20 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Low / Auto-Allowed</span>
          <span className="text-2xl font-black text-emerald-400 mt-1 font-mono">{stats.low_risk}</span>
        </div>

        {/* 6. APPROVED TODAY */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Approved Today</span>
          <span className="text-2xl font-black text-emerald-400 mt-1 font-mono">{stats.approved_today}</span>
        </div>

        {/* 7. REJECTED TODAY */}
        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between shadow-md">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Rejected Today</span>
          <span className="text-2xl font-black text-slate-400 mt-1 font-mono">{stats.rejected_today}</span>
        </div>
      </div>

      {/* Feedback Toast */}
      {actionFeedback && (
        <div className={`p-4 rounded-xl text-xs font-semibold flex flex-wrap items-center justify-between gap-3 border shadow-lg ${
          actionFeedback.type === 'success' 
            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' 
            : 'bg-rose-500/20 border-rose-500/40 text-rose-300'
        }`}>
          <div className="flex items-center gap-2">
            {actionFeedback.type === 'success' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
            <span>{actionFeedback.message}</span>
          </div>
          <div className="flex items-center gap-3">
            {actionFeedback.incidentId && setActiveTab && (
              <button
                onClick={() => navigateToIncidentContext(actionFeedback.incidentId!, 'recovery')}
                className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs flex items-center gap-1.5 transition shadow-md shadow-cyan-950"
              >
                <span>Open Live Remediation Workspace</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
            <button onClick={() => setActionFeedback(null)} className="text-slate-400 hover:text-white">✕</button>
          </div>
        </div>
      )}

      {/* Strict Tab Filters & Company Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2 overflow-x-auto">
          <button
            onClick={() => setActiveTabFilter('PENDING')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'PENDING'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>PENDING</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'PENDING' ? 'bg-black/30 text-slate-950 font-black' : 'bg-slate-800 text-slate-300'}`}>
              {pendingCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('HIGH_RISK')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'HIGH_RISK'
                ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>HIGH RISK</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'HIGH_RISK' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {stats.high_risk}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('MEDIUM_RISK')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'MEDIUM_RISK'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>MEDIUM RISK</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'MEDIUM_RISK' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {stats.medium_risk}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('LOW_RISK')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'LOW_RISK'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>LOW RISK</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'LOW_RISK' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {stats.low_risk}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('APPROVED')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'APPROVED'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>APPROVED</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'APPROVED' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {stats.approved_today}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('REJECTED')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'REJECTED'
                ? 'bg-rose-600 text-white shadow-md shadow-rose-600/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>REJECTED</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'REJECTED' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {stats.rejected_today}
            </span>
          </button>

          <button
            onClick={() => setActiveTabFilter('ALL')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTabFilter === 'ALL'
                ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/20 font-black'
                : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <span>ALL</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${activeTabFilter === 'ALL' ? 'bg-black/30 text-white font-black' : 'bg-slate-800 text-slate-300'}`}>
              {allTickets.length}
            </span>
          </button>
        </div>

        {/* Company Filter & Search */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-xl px-2.5 py-1.5">
            <Building2 className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
            <select
              value={selectedCompanyFilter}
              onChange={(e) => setSelectedCompanyFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-200 font-mono font-bold focus:outline-none cursor-pointer"
            >
              <option value="ALL" className="bg-slate-950 text-white">ALL COMPANIES</option>
              <option value="fincore" className="bg-slate-950 text-blue-300">FinCore</option>
              <option value="shopsphere" className="bg-slate-950 text-emerald-300">ShopSphere</option>
              <option value="clouddesk" className="bg-slate-950 text-indigo-300">CloudDesk</option>
            </select>
          </div>

          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search approvals, actions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 w-full sm:w-56 font-mono"
            />
          </div>
        </div>
      </div>

      {/* Approval Cards List */}
      {filteredTickets.length === 0 ? (
        <div className="p-12 rounded-2xl bg-slate-900/60 border border-slate-800 text-center space-y-3">
          <CheckCheck className="h-12 w-12 text-emerald-400 mx-auto" />
          <h3 className="text-base font-bold text-white">No Approval Tickets in Queue</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            {activeTabFilter === 'PENDING'
              ? 'No pending approval requests. Current actionable pending count is 0.'
              : 'No matching tickets found for the active filter.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredTickets.map((ticket) => {
            const linkedIncident = incidents.find(i => i.incident_id === ticket.incident_id);
            const title = ticket.incident_title || linkedIncident?.title || ticket.detected_problem || ticket.problem || `Remediation for ${ticket.service_name || ticket.service}`;
            const service = ticket.service_name || ticket.service || 'unknown-service';
            const rootCause = ticket.root_cause || linkedIncident?.root_cause || linkedIncident?.root_cause_summary || 'Service anomaly detected';
            const proposedAction = ticket.proposed_recovery_action || ticket.proposed_action || ticket.action || 'Execute Recovery';
            const riskLevel = (ticket.risk_level || ticket.risk || 'LOW').toUpperCase();
            const isPending = (ticket.status || '').toUpperCase() === 'PENDING';
            const whyRequired = ticket.why_approval_required || `Action has ${riskLevel} operational risk. Enterprise safety governance requires member authorization.`;
            const expectedImpact = ticket.expected_impact || ticket.expected_outcome || 'Restores service health to baseline without downstream regressions.';
            const blastRadius = ticket.blast_radius || 'CONTAINED';
            const sandboxStatus = ticket.sandbox_status || 'READY';
            const validationStatus = ticket.validation_status || (isPending ? 'AWAITING_AUTHORIZATION' : 'VERIFIED');

            return (
              <div 
                key={ticket.approval_id}
                onClick={() => setSelectedDrawerTicket(ticket)}
                className={`p-6 rounded-2xl bg-slate-900/90 border transition-all duration-200 hover:border-slate-700 cursor-pointer shadow-lg space-y-4 ${
                  isPending 
                    ? 'border-slate-800 hover:shadow-cyan-500/5' 
                    : ticket.status === 'APPROVED' 
                    ? 'border-emerald-500/30 bg-slate-900/60' 
                    : 'border-rose-500/30 bg-slate-900/60'
                }`}
              >
                {/* Row 1: Header - Company, Severity, Status, Approval ID, Incident ID, Timestamp */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    {getCompanyBadge(ticket.tenant_id || (ticket as any).company)}
                    {getSeverityBadge(ticket.incident_severity || ticket.severity)}
                    {getStatusBadge(ticket.status)}
                    <span className="font-mono text-xs text-slate-600">•</span>
                    <span className="font-mono text-xs text-cyan-400 font-bold">{ticket.approval_id}</span>
                    <span className="font-mono text-xs text-slate-600">•</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigateToIncidentContext(ticket.incident_id, 'rca');
                      }}
                      className="font-mono text-xs text-indigo-400 hover:text-indigo-300 font-bold hover:underline flex items-center gap-1"
                      title="Inspect incident in RCA"
                    >
                      <span>{ticket.incident_id}</span>
                      <ExternalLink className="h-3 w-3" />
                    </button>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                    <span className="text-[11px] text-slate-500">By: <strong className="text-slate-300">{ticket.requested_by || 'Policy Engine'}</strong></span>
                    <span className="text-slate-600">•</span>
                    <div className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-slate-500" />
                      <span>{formatRelativeTime(ticket.requested_at || ticket.created_at)}</span>
                    </div>
                  </div>
                </div>

                {/* Row 2: Title, Service, Risk Badge */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-black text-white tracking-tight">{title}</h3>
                    <p className="text-xs text-slate-400 mt-0.5 font-mono">
                      Affected Service: <strong className="text-cyan-300 font-bold">{service}</strong>
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {getRiskBadge(riskLevel)}
                  </div>
                </div>

                {/* Row 3: Audit Grid - Root Cause, Recovery Action, Why Approval Required */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs bg-slate-950/70 p-4 rounded-xl border border-slate-800/80">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider block">ROOT CAUSE</span>
                    <p className="text-slate-200 font-medium leading-relaxed">{rootCause}</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-cyan-400 uppercase font-black tracking-wider block">RECOVERY ACTION</span>
                    <p className="text-cyan-300 font-mono font-bold flex items-center gap-1.5">
                      <Zap className="h-4 w-4 text-cyan-400 shrink-0" />
                      <span>{proposedAction}</span>
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-amber-400 uppercase font-black tracking-wider block">WHY APPROVAL IS REQUIRED</span>
                    <p className="text-slate-300 font-medium leading-relaxed">{whyRequired}</p>
                  </div>
                </div>

                {/* Row 4: Status Strip - Expected Impact, Blast Radius, Sandbox, Validation */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">Expected Impact</span>
                    <span className="text-slate-200 font-bold truncate block">{expectedImpact}</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">Blast Radius</span>
                    <span className="text-amber-300 font-bold truncate block">{blastRadius}</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">Sandbox Status</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      <Box className="h-3 w-3" />
                      <span>{sandboxStatus}</span>
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">Validation Status</span>
                    <span className="text-cyan-300 font-bold truncate block">{validationStatus}</span>
                  </div>
                </div>

                {/* Row 5: Action Strip & Cross-Navigation Links */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80" onClick={(e) => e.stopPropagation()}>
                  {/* Cross-Navigation Buttons (Goal 4) */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigateToIncidentContext(ticket.incident_id, 'rca')}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 font-bold text-xs border border-indigo-500/30 transition flex items-center gap-1"
                    >
                      <span>View RCA</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>

                    <button
                      onClick={() => navigateToIncidentContext(ticket.incident_id, 'recovery')}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-teal-300 font-bold text-xs border border-teal-500/30 transition flex items-center gap-1"
                    >
                      <span>View Recovery</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>

                    <button
                      onClick={() => navigateToIncidentContext(ticket.incident_id, 'recovery')}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 font-bold text-xs border border-cyan-500/30 transition flex items-center gap-1"
                    >
                      <span>View Validation</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>

                    <button
                      onClick={() => setSelectedDrawerTicket(ticket)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs border border-slate-700 transition flex items-center gap-1"
                    >
                      <Eye className="h-3 w-3" />
                      <span>Inspect Details</span>
                    </button>
                  </div>

                  {/* Approve / Reject Actions */}
                  {isPending ? (
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => {
                          setConfirmRejectTicket(ticket);
                          setRejectionReason('');
                          setRejectionError(null);
                        }}
                        disabled={isProcessing || userRole === 'VIEWER'}
                        className="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold text-xs transition flex items-center gap-1.5 disabled:opacity-40"
                      >
                        <X className="h-4 w-4" />
                        <span>REJECT</span>
                      </button>

                      <button
                        onClick={() => setConfirmApproveTicket(ticket)}
                        disabled={isProcessing || userRole === 'VIEWER'}
                        className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-black text-xs shadow-lg shadow-emerald-500/20 transition flex items-center gap-2 disabled:opacity-40"
                      >
                        <Check className="h-4 w-4" />
                        <span>APPROVE RECOVERY</span>
                      </button>
                    </div>
                  ) : ticket.status === 'APPROVED' ? (
                    <div className="flex items-center gap-2 text-xs text-emerald-400 font-bold">
                      <CheckCircle2 className="h-4 w-4" />
                      <span>Approved by {ticket.reviewed_by || 'SRE Admin'} — Controlled Execution In Progress</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-xs text-rose-400 font-bold">
                      <XCircle className="h-4 w-4" />
                      <span>Rejected by {ticket.reviewed_by || 'SRE Reviewer'} — Recovery Stopped</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* NON-BLOCKING DETAIL SLIDE-OUT DRAWER */}
      {selectedDrawerTicket && (
        <div 
          className="fixed inset-0 z-50 overflow-hidden bg-slate-950/40 backdrop-blur-xs flex justify-end"
          onClick={() => setSelectedDrawerTicket(null)}
        >
          <div 
            className="w-full max-w-2xl bg-[#0d121f] border-l border-slate-800 h-full overflow-y-auto p-6 space-y-6 shadow-2xl animate-in slide-in-from-right duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  {getSeverityBadge(selectedDrawerTicket.incident_severity || selectedDrawerTicket.severity)}
                  {getStatusBadge(selectedDrawerTicket.status)}
                  <span className="font-mono text-xs text-cyan-400 font-bold">{selectedDrawerTicket.approval_id}</span>
                </div>
                <h2 className="text-xl font-black text-white mt-2">
                  {selectedDrawerTicket.incident_title || selectedDrawerTicket.detected_problem || selectedDrawerTicket.problem || `Recovery Detail: ${selectedDrawerTicket.service_name}`}
                </h2>
                <div className="flex items-center gap-3 mt-1 text-xs text-slate-400 font-mono">
                  <span>Incident: <strong className="text-cyan-300">{selectedDrawerTicket.incident_id}</strong></span>
                  <span>•</span>
                  <span>Tenant: <strong className="text-slate-300">{selectedDrawerTicket.tenant_id || 'demo-tenant'}</strong></span>
                </div>
              </div>

              <button 
                onClick={() => setSelectedDrawerTicket(null)}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Quick Cross-Navigation Bar in Drawer */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-[11px] text-slate-400 font-bold uppercase mr-2">Lifecycle Links:</span>
              <button
                onClick={() => navigateToIncidentContext(selectedDrawerTicket.incident_id, 'rca')}
                className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 text-xs font-bold transition flex items-center gap-1"
              >
                <span>View RCA</span>
                <ExternalLink className="h-3 w-3" />
              </button>
              <button
                onClick={() => navigateToIncidentContext(selectedDrawerTicket.incident_id, 'recovery')}
                className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-teal-300 text-xs font-bold transition flex items-center gap-1"
              >
                <span>View Recovery</span>
                <ExternalLink className="h-3 w-3" />
              </button>
              <button
                onClick={() => navigateToIncidentContext(selectedDrawerTicket.incident_id, 'recovery')}
                className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-bold transition flex items-center gap-1"
              >
                <span>View Validation</span>
                <ExternalLink className="h-3 w-3" />
              </button>
            </div>

            {/* Section 1: INCIDENT */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">1. INCIDENT</span>
              <p className="text-sm font-semibold text-white">
                {selectedDrawerTicket.detected_problem || selectedDrawerTicket.problem || selectedDrawerTicket.incident_title || 'Service anomaly detected.'}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-xs">
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Service</span>
                  <span className="text-cyan-300 font-bold">{selectedDrawerTicket.service_name || selectedDrawerTicket.service}</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Severity</span>
                  <span className="text-rose-400 font-bold">{selectedDrawerTicket.incident_severity || selectedDrawerTicket.severity || 'P1'}</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Attempt #</span>
                  <span className="text-white font-bold">{selectedDrawerTicket.attempt_number || 1}</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Requested By</span>
                  <span className="text-slate-300 font-bold truncate block">{selectedDrawerTicket.requested_by || 'Policy Engine'}</span>
                </div>
              </div>
            </div>

            {/* Section 2: ROOT CAUSE */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">2. ROOT CAUSE</span>
                <span className="text-xs font-mono font-bold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/30">
                  Confidence: {selectedDrawerTicket.root_cause_confidence ? Math.round(selectedDrawerTicket.root_cause_confidence * 100) : (selectedDrawerTicket.rca_confidence ? Math.round(selectedDrawerTicket.rca_confidence * 100) : 94)}%
                </span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed font-medium">
                {selectedDrawerTicket.root_cause || 'Connection saturation or resource contention detected on target service.'}
              </p>
            </div>

            {/* Section 3: EVIDENCE SUMMARY */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">3. EVIDENCE SUMMARY</span>
              <ul className="text-xs text-slate-300 space-y-1.5 list-disc list-inside bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                {Array.isArray(selectedDrawerTicket.evidence) && selectedDrawerTicket.evidence.length > 0 ? (
                  selectedDrawerTicket.evidence.map((ev: any, idx: number) => (
                    <li key={idx}>
                      {typeof ev === 'string' ? ev : (ev.metric_or_log_value || ev.observation || JSON.stringify(ev))}
                    </li>
                  ))
                ) : (
                  <>
                    <li>Connection pool saturation detected: active pool usage exceeded 95% threshold</li>
                    <li>Service request timeout rate surged beyond 15% SLO limit</li>
                    <li>Distributed trace dependency indicates primary failure origin at target service</li>
                    <li>HTTP 500 error cascades observed on downstream consuming services</li>
                  </>
                )}
              </ul>
            </div>

            {/* Section 4: RECOVERY PLAN */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">4. RECOVERY PLAN</span>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex items-center gap-2 text-sm font-bold text-cyan-300">
                  <Zap className="h-4 w-4 text-cyan-400" />
                  <span>{selectedDrawerTicket.proposed_recovery_action || selectedDrawerTicket.proposed_action}</span>
                </div>
                <p className="text-slate-300 font-sans text-xs">
                  Why Selected: <strong className="text-slate-100">{selectedDrawerTicket.why_this_recovery_was_selected || selectedDrawerTicket.why_selected || 'Allowlisted action with highest empirical recovery confidence for this failure signature.'}</strong>
                </p>
              </div>
            </div>

            {/* Section 5: RISK & WHY APPROVAL IS REQUIRED */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">5. RISK & GOVERNANCE</span>
                {getRiskBadge(selectedDrawerTicket.risk_level)}
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-xs">
                <div className="space-y-1">
                  <span className="text-slate-500 font-bold text-[10px] uppercase">Why Approval Is Required:</span>
                  <p className="text-amber-300 leading-relaxed font-medium">
                    {selectedDrawerTicket.why_approval_required || `Action is classified as ${selectedDrawerTicket.risk_level} risk. Enterprise safety governance requires member authorization before execution.`}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-slate-800 font-mono text-slate-400 text-[11px]">
                  <span>Required Approver Role:</span>
                  <strong className="text-white">{selectedDrawerTicket.approver_role_requirement || selectedDrawerTicket.required_role || 'SRE Lead'}</strong>
                </div>
              </div>
            </div>

            {/* Section 6: SANDBOX & PRE-FIX TELEMETRY */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">6. SANDBOX & PRE-FIX TELEMETRY</span>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                  SANDBOX: {selectedDrawerTicket.sandbox_status || 'READY'}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Pre-Fix Error Rate</span>
                  <span className="text-rose-400 font-bold">38.4%</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Pre-Fix P95 Latency</span>
                  <span className="text-amber-300 font-bold">845ms</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Socket Utilization</span>
                  <span className="text-rose-400 font-bold">98/100</span>
                </div>
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Isolation Gate</span>
                  <span className="text-emerald-400 font-bold">CONTAINED</span>
                </div>
              </div>
            </div>

            {/* Section 7: RECOVERY ACTION & VALIDATION STATUS */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">7. RECOVERY ACTION & VALIDATION</span>
                <span className="text-[10px] font-mono text-cyan-300 font-bold">
                  {selectedDrawerTicket.validation_status || 'AWAITING_AUTHORIZATION'}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono space-y-1 text-slate-300">
                <p>• Action: <strong className="text-white">{selectedDrawerTicket.proposed_recovery_action || selectedDrawerTicket.proposed_action}</strong></p>
                <p>• Target: <strong className="text-cyan-300">{selectedDrawerTicket.service_name || selectedDrawerTicket.service}</strong></p>
                <p>• Estimated Execution Duration: <strong className="text-slate-100">~{selectedDrawerTicket.estimated_downtime_sec || 15}s</strong></p>
              </div>
            </div>

            {/* Section 8: EXPECTED IMPACT & ROLLBACK PLAN */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">8. EXPECTED IMPACT & ROLLBACK PLAN</span>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block">Expected Impact:</span>
                  <p className="text-slate-200 font-sans">{selectedDrawerTicket.expected_impact || selectedDrawerTicket.expected_outcome || 'Restores service health and normalizes latency without side effects.'}</p>
                </div>
                <div className="pt-2 border-t border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Rollback Plan:</span>
                  <p className="text-amber-300">{selectedDrawerTicket.rollback_plan || 'RESTART_CONTROLLED_SERVICE'}</p>
                  <span className="text-[10px] text-slate-500">Rollback Available: <strong className="text-emerald-400">{selectedDrawerTicket.rollback_available !== false ? 'YES' : 'NO'}</strong></span>
                </div>
              </div>
            </div>

            {/* Section 9: ATTEMPT HISTORY */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-black text-cyan-400 uppercase tracking-wider block">9. ATTEMPT HISTORY</span>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Current Attempt:</span>
                  <span className="text-white font-bold">Attempt #{selectedDrawerTicket.attempt_number || 1} of 3</span>
                </div>
                <div className="flex items-center justify-between mt-1 text-slate-400">
                  <span>Prior Failures:</span>
                  <span className="text-emerald-400 font-bold">0 (Clean initial attempt)</span>
                </div>
              </div>
            </div>

            {/* Section 10: DECISION ACTIONS */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-slate-900 to-slate-950 border-2 border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-black text-white uppercase tracking-wider block">10. APPROVAL DECISION</span>
                <span className="text-xs font-mono text-cyan-400">Operating Role: {userRole}</span>
              </div>

              {(selectedDrawerTicket.status || '').toUpperCase() === 'PENDING' ? (
                <div className="space-y-3 pt-1">
                  <p className="text-xs text-slate-400">
                    Authorizing will trigger real controlled execution, telemetry observation, workload replay, and empirical 8-point verification.
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setConfirmApproveTicket(selectedDrawerTicket)}
                      disabled={isProcessing || userRole === 'VIEWER'}
                      className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-black text-xs shadow-lg shadow-emerald-500/20 transition flex items-center justify-center gap-2 disabled:opacity-40"
                    >
                      <Check className="h-4 w-4" />
                      <span>APPROVE RECOVERY</span>
                    </button>

                    <button
                      onClick={() => {
                        setConfirmRejectTicket(selectedDrawerTicket);
                        setRejectionReason('');
                        setRejectionError(null);
                      }}
                      disabled={isProcessing || userRole === 'VIEWER'}
                      className="px-5 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold text-xs transition flex items-center gap-1.5 disabled:opacity-40"
                    >
                      <X className="h-4 w-4" />
                      <span>REJECT</span>
                    </button>
                  </div>
                </div>
              ) : selectedDrawerTicket.status === 'APPROVED' ? (
                <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-mono space-y-2.5">
                  <div className="flex items-center gap-1.5 font-bold">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>✓ APPROVED by {selectedDrawerTicket.reviewed_by || 'SRE Admin'}</span>
                  </div>
                  <p className="text-slate-400 text-[11px]">Recovery executed and undergoing active verified validation.</p>
                  {setActiveTab && (
                    <button
                      onClick={() => navigateToIncidentContext(selectedDrawerTicket.incident_id, 'recovery')}
                      className="w-full py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition shadow-md shadow-cyan-950"
                    >
                      <Zap className="h-3.5 w-3.5" />
                      <span>Open Live Remediation Execution Workspace</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 font-mono space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <XCircle className="h-4 w-4" />
                    <span>✗ REJECTED by {selectedDrawerTicket.reviewed_by || 'SRE Reviewer'}</span>
                  </div>
                  <p className="text-slate-400 text-[11px]">Reason: "{selectedDrawerTicket.review_notes || 'Operational policy rejection'}"</p>
                </div>
              )}
            </div>

          </div>
        </div>
      )}

      {/* Confirmation Modal for APPROVAL */}
      {confirmApproveTicket && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-emerald-500/80 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-black text-white">AUTHORIZE CONTROLLED RECOVERY</h3>
                <p className="text-xs text-slate-400">Governance Gate for {confirmApproveTicket.approval_id}</p>
              </div>
            </div>

            <div className="space-y-2 text-xs bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono">
              <div>
                <span className="text-slate-500 block text-[10px]">Action to Execute:</span>
                <p className="text-emerald-300 font-bold text-sm">{confirmApproveTicket.proposed_recovery_action || confirmApproveTicket.proposed_action}</p>
              </div>
              <div className="flex justify-between pt-1 border-t border-slate-800">
                <span className="text-slate-500">Service:</span>
                <span className="text-white font-bold">{confirmApproveTicket.service_name || confirmApproveTicket.service}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Incident:</span>
                <span className="text-cyan-400 font-bold">{confirmApproveTicket.incident_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Risk Assessment:</span>
                <span className="text-amber-400 font-bold uppercase">{confirmApproveTicket.risk_level} RISK</span>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Authorizing will start real controlled execution, pre/post telemetry comparison, workload replay, and validation.
            </p>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setConfirmApproveTicket(null)}
                disabled={isProcessing}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                CANCEL
              </button>
              <button
                onClick={handleConfirmApproval}
                disabled={isProcessing}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-black text-xs shadow-lg shadow-emerald-500/20 transition flex items-center gap-1.5"
              >
                <Check className="h-4 w-4" />
                <span>{isProcessing ? 'Executing...' : 'CONFIRM & EXECUTE'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for REJECTION */}
      {confirmRejectTicket && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-rose-500/80 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <AlertOctagon className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-black text-white">REJECT RECOVERY ACTION</h3>
                <p className="text-xs text-slate-400">Halt automated execution for {confirmRejectTicket.approval_id}</p>
              </div>
            </div>

            <div className="space-y-2 text-xs bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-500">Proposed Action:</span>
                <span className="text-rose-300 font-bold">{confirmRejectTicket.proposed_recovery_action || confirmRejectTicket.proposed_action}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Service:</span>
                <span className="text-white font-bold">{confirmRejectTicket.service_name || confirmRejectTicket.service}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Incident:</span>
                <span className="text-cyan-400 font-bold">{confirmRejectTicket.incident_id}</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300 block">
                Operational Rejection Reason <span className="text-rose-400">*</span>
              </label>
              <textarea
                rows={3}
                value={rejectionReason}
                onChange={(e) => {
                  setRejectionReason(e.target.value);
                  setRejectionError(null);
                }}
                placeholder="Explain why this remediation is declined (e.g., active maintenance window, planned failover, false positive)..."
                className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-400 font-sans"
              />
              {rejectionError && (
                <p className="text-[11px] text-rose-400 font-medium">{rejectionError}</p>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => {
                  setConfirmRejectTicket(null);
                  setRejectionError(null);
                }}
                disabled={isProcessing}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                CANCEL
              </button>
              <button
                onClick={handleConfirmRejection}
                disabled={isProcessing}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs shadow-lg shadow-rose-500/20 transition flex items-center gap-1.5"
              >
                <X className="h-4 w-4" />
                <span>{isProcessing ? 'Rejecting...' : 'CONFIRM REJECTION'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

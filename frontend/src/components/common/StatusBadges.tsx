import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  HelpCircle, 
  Radio, 
  Clock, 
  Wifi, 
  WifiOff, 
  ShieldCheck, 
  RotateCw,
  AlertOctagon
} from 'lucide-react';
import type { ServiceOperationalStatus, TelemetryConnectionStatus } from '../../types';

// ============================================================================
// PART 42 — VISUAL STATUS LANGUAGE
// ============================================================================

interface StatusBadgeProps {
  status: TelemetryConnectionStatus | 'LIVE' | 'STALE' | string;
  className?: string;
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '', showIcon = true }) => {
  const s = (status || 'UNKNOWN').toUpperCase();

  switch (s) {
    case 'CONNECTED':
    case 'LIVE':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ${className}`}>
          {showIcon && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
          {s}
        </span>
      );
    case 'DEGRADED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20 ${className}`}>
          {showIcon && <Wifi className="w-3 h-3 text-amber-400" />}
          DEGRADED
        </span>
      );
    case 'DISCONNECTED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20 ${className}`}>
          {showIcon && <WifiOff className="w-3 h-3 text-rose-400" />}
          DISCONNECTED
        </span>
      );
    case 'PENDING':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 ${className}`}>
          {showIcon && <RotateCw className="w-3 h-3 text-blue-400 animate-spin" />}
          PENDING
        </span>
      );
    case 'STALE':
    case 'STALE DATA':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30 ${className}`}>
          {showIcon && <Clock className="w-3 h-3 text-amber-300" />}
          STALE DATA
        </span>
      );
    default:
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono bg-slate-500/10 text-slate-400 border border-slate-500/20 ${className}`}>
          {showIcon && <HelpCircle className="w-3 h-3 text-slate-400" />}
          {s}
        </span>
      );
  }
};


interface HealthBadgeProps {
  status: ServiceOperationalStatus | string;
  className?: string;
  showIcon?: boolean;
}

export const HealthBadge: React.FC<HealthBadgeProps> = ({ status, className = '', showIcon = true }) => {
  const s = (status || 'UNKNOWN').toUpperCase();

  switch (s) {
    case 'HEALTHY':
    case 'UP':
    case 'OK':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ${className}`}>
          {showIcon && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
          HEALTHY
        </span>
      );
    case 'DEGRADED':
    case 'WARNING':
    case 'WARN':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20 ${className}`}>
          {showIcon && <AlertTriangle className="w-3 h-3 text-amber-400" />}
          DEGRADED
        </span>
      );
    case 'CRITICAL':
    case 'FAILED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30 animate-pulse ${className}`}>
          {showIcon && <AlertOctagon className="w-3 h-3 text-rose-400" />}
          CRITICAL
        </span>
      );
    case 'DOWN':
    case 'CRASHED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-rose-600/20 text-rose-300 border border-rose-500/40 ${className}`}>
          {showIcon && <XCircle className="w-3 h-3 text-rose-400" />}
          DOWN
        </span>
      );
    case 'UNKNOWN':
    default:
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-slate-800 text-slate-400 border border-slate-700 ${className}`}>
          {showIcon && <HelpCircle className="w-3 h-3 text-slate-400" />}
          UNKNOWN
        </span>
      );
  }
};


interface IncidentStatusBadgeProps {
  status: string;
  className?: string;
}

export const IncidentStatusBadge: React.FC<IncidentStatusBadgeProps> = ({ status, className = '' }) => {
  const s = (status || 'OPEN').toUpperCase();

  switch (s) {
    case 'OPEN':
    case 'DETECTED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-rose-500/15 text-rose-400 border border-rose-500/30 ${className}`}>
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping" />
          OPEN
        </span>
      );
    case 'INVESTIGATING':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-blue-500/15 text-blue-400 border border-blue-500/30 ${className}`}>
          <RotateCw className="w-3 h-3 text-blue-400 animate-spin" />
          INVESTIGATING
        </span>
      );
    case 'ROOT_CAUSE_IDENTIFIED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-purple-500/15 text-purple-400 border border-purple-500/30 ${className}`}>
          <CheckCircle2 className="w-3 h-3 text-purple-400" />
          RCA IDENTIFIED
        </span>
      );
    case 'AWAITING_APPROVAL':
    case 'PENDING_APPROVAL':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse ${className}`}>
          <AlertTriangle className="w-3 h-3 text-amber-300" />
          AWAITING APPROVAL
        </span>
      );
    case 'APPROVED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-teal-500/15 text-teal-300 border border-teal-500/30 ${className}`}>
          <ShieldCheck className="w-3 h-3 text-teal-300" />
          APPROVED
        </span>
      );
    case 'REMEDIATING':
    case 'EXECUTING':
    case 'RECOVERING':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 ${className}`}>
          <RotateCw className="w-3 h-3 text-indigo-300 animate-spin" />
          REMEDIATING
        </span>
      );
    case 'VERIFYING':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 ${className}`}>
          <Radio className="w-3 h-3 text-cyan-300 animate-pulse" />
          VERIFYING
        </span>
      );
    case 'RESOLVED':
    case 'VALIDATED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 ${className}`}>
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
          RESOLVED
        </span>
      );
    case 'REJECTED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-slate-500/20 text-slate-400 border border-slate-600 ${className}`}>
          <XCircle className="w-3 h-3 text-slate-400" />
          REJECTED
        </span>
      );
    case 'REMEDIATION_FAILED':
    case 'VERIFICATION_FAILED':
    case 'FAILED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40 ${className}`}>
          <XCircle className="w-3 h-3 text-rose-300" />
          FAILED
        </span>
      );
    case 'UNRESOLVED':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-amber-600/20 text-amber-300 border border-amber-500/50 ${className}`}>
          <AlertOctagon className="w-3 h-3 text-amber-300" />
          UNRESOLVED
        </span>
      );
    default:
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono bg-slate-800 text-slate-400 border border-slate-700 ${className}`}>
          {s}
        </span>
      );
  }
};

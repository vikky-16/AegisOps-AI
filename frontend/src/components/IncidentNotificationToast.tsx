import React, { useState, useEffect, useRef } from 'react';
import { ShieldAlert, AlertTriangle, ArrowRight, X, Clock, CheckCircle } from 'lucide-react';
import type { Incident, ApprovalTicket } from '../types';
import { useTenant } from '../context/TenantContext';

export interface ActiveToast {
  id: string;
  dedupKey: string;
  type: 'incident' | 'approval';
  recordId: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  subtitle: string;
  serviceName?: string;
  actionText: string;
  createdAt: number;
  durationMs: number;
  tenantId: string;
}

interface IncidentNotificationToastProps {
  activeIncidents: Incident[];
  pendingApprovals: ApprovalTicket[];
  onNavigateToIncident?: (incidentId: string) => void;
  onNavigateToApproval?: (approvalId: string) => void;
  onNavigateToIncidents: () => void;
  onNavigateToApprovals: () => void;
}

export const IncidentNotificationToast: React.FC<IncidentNotificationToastProps> = ({
  activeIncidents,
  pendingApprovals,
  onNavigateToIncident,
  onNavigateToApproval,
  onNavigateToIncidents,
  onNavigateToApprovals
}) => {
  const { activeTenant, currentUser } = useTenant();
  const currentTenantId = activeTenant?.id || 'demo-tenant';

  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  // Stable deduplication set across renders and polls
  const seenKeysRef = useRef<Set<string>>(new Set());
  const isInitialMountRef = useRef<boolean>(true);
  const lastTenantRef = useRef<string>(currentTenantId);

  // When tenant switches, clear all toasts and reset seen keys so tenants cannot see each other's toasts
  useEffect(() => {
    if (lastTenantRef.current !== currentTenantId) {
      lastTenantRef.current = currentTenantId;
      seenKeysRef.current.clear();
      setToasts([]);
      isInitialMountRef.current = true;
    }
  }, [currentTenantId]);

  // Monitor genuinely new incidents or approvals, or material severity updates
  useEffect(() => {
    // Filter to current tenant
    const tenantIncidents = activeIncidents.filter(
      i => !i.tenant_id || i.tenant_id === currentTenantId || currentTenantId === 'all'
    );
    const tenantApprovals = pendingApprovals.filter(
      a => !a.tenant_id || a.tenant_id === currentTenantId || currentTenantId === 'all'
    );

    const newlyDiscoveredToasts: ActiveToast[] = [];

    // Check critical or high active incidents
    tenantIncidents.forEach(inc => {
      if (inc.status === 'RESOLVED' || inc.status === 'CLOSED') return;
      const sev = (inc.severity || 'CRITICAL').toUpperCase();
      // Notify on critical or high incidents
      if (sev === 'CRITICAL' || sev === 'HIGH') {
        const updateSig = inc.created_at || (inc as any).timestamp || '';
        const dedupKey = `inc-${inc.incident_id}-${sev}-${updateSig}-${currentTenantId}`;

        if (!seenKeysRef.current.has(dedupKey)) {
          seenKeysRef.current.add(dedupKey);

          // On initial cold page load, populate seen keys so we don't spam toasts on first load,
          // UNLESS there is an active critical incident that should show once
          if (!isInitialMountRef.current || newlyDiscoveredToasts.length === 0) {
            newlyDiscoveredToasts.push({
              id: `toast-inc-${inc.incident_id}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              dedupKey,
              type: 'incident',
              recordId: inc.incident_id,
              severity: sev as 'CRITICAL' | 'HIGH',
              title: sev === 'CRITICAL' ? 'Critical Incident Active' : 'High Severity Incident',
              subtitle: inc.title || `Operational anomaly on ${inc.primary_service || 'monitored service'}`,
              serviceName: inc.primary_service || inc.root_cause_service,
              actionText: 'Inspect',
              createdAt: Date.now(),
              durationMs: 6000, // 6 seconds auto-dismiss
              tenantId: currentTenantId
            });
          }
        }
      }
    });

    // Check pending approvals
    tenantApprovals.forEach(app => {
      const isPending = app.status === 'PENDING' || app.status === 'PENDING_APPROVAL' || app.status === 'AWAITING_APPROVAL';
      if (!isPending) return;

      const appSig = app.created_at || app.proposed_action || '';
      const dedupKey = `app-${app.approval_id}-${app.status}-${appSig}-${currentTenantId}`;

      if (!seenKeysRef.current.has(dedupKey)) {
        seenKeysRef.current.add(dedupKey);

        if (!isInitialMountRef.current || newlyDiscoveredToasts.length === 0) {
          newlyDiscoveredToasts.push({
            id: `toast-app-${app.approval_id}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            dedupKey,
            type: 'approval',
            recordId: app.approval_id,
            severity: (app.risk_level || 'HIGH') as any,
            title: 'Approval Required',
            subtitle: `${app.proposed_action || 'Remediation action'} on ${app.service_name || 'service'}`,
            serviceName: app.service_name,
            actionText: 'Review',
            createdAt: Date.now(),
            durationMs: 6500, // 6.5 seconds auto-dismiss
            tenantId: currentTenantId
          });
        }
      }
    });

    isInitialMountRef.current = false;

    if (newlyDiscoveredToasts.length > 0) {
      setToasts(prev => {
        // Keep stack bounded to max 4 toasts
        const combined = [...newlyDiscoveredToasts, ...prev];
        return combined.slice(0, 4);
      });
    }
  }, [activeIncidents, pendingApprovals, currentTenantId]);

  // Visual dismiss only: does NOT resolve, approve, delete, or alter any record
  const dismissToast = (toastId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setToasts(prev => prev.filter(t => t.id !== toastId));
  };

  const handleToastClick = (toast: ActiveToast) => {
    dismissToast(toast.id);
    if (toast.type === 'incident') {
      if (onNavigateToIncident) {
        onNavigateToIncident(toast.recordId);
      } else {
        onNavigateToIncidents();
      }
    } else {
      if (onNavigateToApproval) {
        onNavigateToApproval(toast.recordId);
      } else {
        onNavigateToApprovals();
      }
    }
  };

  if (toasts.length === 0) {
    return null;
  }

  return (
    <aside
      aria-label="System notifications"
      className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm sm:max-w-md w-[calc(100vw-2.5rem)] sm:w-full pointer-events-none transition-all duration-300"
    >
      {toasts.map(toast => (
        <ToastItemCard
          key={toast.id}
          toast={toast}
          onDismiss={(e) => dismissToast(toast.id, e)}
          onClick={() => handleToastClick(toast)}
        />
      ))}
    </aside>
  );
};

interface ToastItemCardProps {
  toast: ActiveToast;
  onDismiss: (e: React.MouseEvent) => void;
  onClick: () => void;
}

const ToastItemCard: React.FC<ToastItemCardProps> = ({ toast, onDismiss, onClick }) => {
  const [progress, setProgress] = useState(100);
  const [isHovered, setIsHovered] = useState(false);
  const timerRef = useRef<any>(null);
  const startTimeRef = useRef<number>(Date.now());
  const remainingTimeRef = useRef<number>(toast.durationMs);

  useEffect(() => {
    if (isHovered) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    startTimeRef.current = Date.now();
    const intervalTime = 50;

    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      const newRemaining = Math.max(0, remainingTimeRef.current - elapsed);
      const pct = (newRemaining / toast.durationMs) * 100;
      setProgress(pct);

      if (newRemaining <= 0) {
        if (timerRef.current) clearInterval(timerRef.current);
        onClick(); // or dismiss
      }
    }, intervalTime);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      remainingTimeRef.current = Math.max(0, remainingTimeRef.current - (Date.now() - startTimeRef.current));
    };
  }, [isHovered, toast.durationMs]);

  // Keydown accessibility (Enter/Space opens, Escape dismisses)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onDismiss(e as any);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const isCritical = toast.severity === 'CRITICAL';
  const isApproval = toast.type === 'approval';

  const bgStyle = isCritical
    ? 'bg-rose-950/95 border-rose-500/80 shadow-rose-950/50'
    : isApproval
    ? 'bg-amber-950/95 border-amber-500/80 shadow-amber-950/50'
    : 'bg-indigo-950/95 border-indigo-500/80 shadow-indigo-950/50';

  const badgeStyle = isCritical
    ? 'bg-rose-500 text-white'
    : isApproval
    ? 'bg-amber-500 text-slate-950 font-bold'
    : 'bg-indigo-500 text-white';

  const iconColor = isCritical ? 'text-rose-400' : isApproval ? 'text-amber-400' : 'text-indigo-400';
  const progressBarColor = isCritical ? 'bg-rose-500' : isApproval ? 'bg-amber-500' : 'bg-indigo-500';

  return (
    <div
      role="status"
      aria-live="polite"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
      className={`pointer-events-auto group relative overflow-hidden rounded-2xl border-2 shadow-2xl backdrop-blur-xl p-3.5 sm:p-4 text-white cursor-pointer transition-all duration-300 transform hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-cyan-400 ${bgStyle}`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Icon & Indicator */}
        <div className="flex items-start gap-3 min-w-0">
          <div className={`p-2 rounded-xl bg-black/30 border border-white/10 shrink-0 mt-0.5 ${iconColor}`}>
            {isApproval ? (
              <ShieldAlert className="h-5 w-5 animate-pulse" />
            ) : (
              <AlertTriangle className="h-5 w-5 animate-pulse" />
            )}
          </div>

          {/* Text Content */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider font-bold ${badgeStyle}`}>
                {toast.title}
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                {toast.recordId}
              </span>
              {toast.serviceName && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-black/40 text-slate-300">
                  {toast.serviceName}
                </span>
              )}
            </div>

            <p className="text-xs font-semibold text-slate-100 line-clamp-2 leading-relaxed">
              {toast.subtitle}
            </p>
          </div>
        </div>

        {/* Action Button & Close Icon */}
        <div className="flex items-center gap-1.5 shrink-0 self-start">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClick();
            }}
            className={`px-2.5 py-1.5 rounded-xl font-bold text-xs shadow-md transition flex items-center gap-1 shrink-0 ${
              isCritical
                ? 'bg-rose-500 hover:bg-rose-400 text-white'
                : isApproval
                ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold'
                : 'bg-indigo-500 hover:bg-indigo-400 text-white'
            }`}
          >
            <span>{toast.actionText}</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>

          <button
            type="button"
            aria-label="Dismiss visual alert"
            onClick={onDismiss}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition shrink-0"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Subtle Auto-Dismiss Countdown Progress Bar */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/40 overflow-hidden">
        <div
          className={`h-full transition-all duration-75 ${progressBarColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};

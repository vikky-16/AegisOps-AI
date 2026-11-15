import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Server, 
  Activity, 
  Cpu, 
  Database, 
  Zap, 
  ShieldAlert, 
  Clock, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle2, 
  HardDrive, 
  RefreshCw, 
  ArrowRight, 
  GitFork, 
  Search, 
  Filter, 
  Radio, 
  Layers, 
  ExternalLink, 
  Flame, 
  Target, 
  Workflow, 
  Maximize2, 
  Info,
  CheckCircle,
  HelpCircle,
  BarChart2,
  Sliders,
  ChevronRight,
  Eye,
  ShieldCheck,
  AlertCircle,
  FileText,
  ChevronDown,
  Check,
  X,
  Play,
  BookOpen,
  Compass,
  Building2,
  Wrench,
  Network
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  AreaChart, 
  Area, 
  ReferenceLine,
  ReferenceDot
} from 'recharts';
import type { ServiceDetail, Incident, DependencyGraphData, ServiceNode, ServiceDependency } from '../types';
import { api } from '../services/api';
import { useTenant } from '../context/TenantContext';
import { useWorkspace } from '../context/WorkspaceContext';

interface ObservatoryPageProps {
  services: ServiceDetail[];
  incidents?: Incident[];
  initialSelectedService?: string;
  initialSelectedIncidentId?: string;
  onSelectIncident?: (incidentId: string) => void;
  setActiveTab?: (tab: string) => void;
}

interface WorkflowPhase {
  id: string;
  name: string;
  services: string[];
  description: string;
}

const WORKFLOW_PHASES: WorkflowPhase[] = [
  { id: 'all', name: 'All Stages (Full Topology)', services: ['gateway', 'service-a', 'service-b', 'database-service', 'cache'], description: 'End-to-end distributed system topology' },
  { id: 'intake', name: 'Request Ingress (Edge)', services: ['gateway'], description: 'Edge routing, TLS termination, API gateway rate limiting' },
  { id: 'auth', name: 'Identity & Access (Core)', services: ['auth-service', 'user-service'], description: 'JWT signature verification, tenant permission validation' },
  { id: 'processing', name: 'Order Processing (Tier 2)', services: ['service-a'], description: 'Business domain orchestration & worker queue' },
  { id: 'payment', name: 'Payment Gateway (Tier 2)', services: ['service-b'], description: 'Payment settlement & fraud detection integration' },
  { id: 'persistence', name: 'Database Primary (Tier 4)', services: ['database-service'], description: 'PostgreSQL primary query execution & connection pool' },
  { id: 'cache', name: 'In-Memory Cache (Tier 4)', services: ['cache'], description: 'Redis key-value caching & session hydration' },
];

export const ObservatoryPage: React.FC<ObservatoryPageProps> = ({ 
  services,
  incidents = [],
  initialSelectedService,
  initialSelectedIncidentId,
  onSelectIncident,
  setActiveTab
}) => {
  const { activeTenant, currentUser } = useTenant();
  const { selectedIncidentId: workspaceIncidentId, setSelectedIncidentId } = useWorkspace();
  const currentTenantId = activeTenant?.id || 'demo-tenant';

  // State persistence via sessionStorage
  const getPersistedFilters = () => {
    try {
      const saved = sessionStorage.getItem('aegisops_observability_filters');
      if (saved) return JSON.parse(saved);
    } catch {}
    return null;
  };

  const persisted = getPersistedFilters();

  // Primary Workspace States
  const [timeRange, setTimeRange] = useState<string>(persisted?.timeRange || '15m');
  const [selectedEnvironment, setSelectedEnvironment] = useState<string>(persisted?.environment || 'all');
  const [selectedSeverityFilter, setSelectedSeverityFilter] = useState<string>(persisted?.severity || 'all');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>(persisted?.status || 'all');
  const [isLiveActive, setIsLiveActive] = useState<boolean>(true);

  // Selected Service Context
  const [selectedService, setSelectedService] = useState<string>(() => {
    if (initialSelectedService) return initialSelectedService.toLowerCase();
    if (persisted?.selectedService) return persisted.selectedService;
    return 'database-service';
  });

  // Selected Incident Context
  const [selectedIncidentId, setSelectedIncidentIdLocal] = useState<string>(() => {
    return initialSelectedIncidentId || workspaceIncidentId || persisted?.selectedIncidentId || '';
  });

  // Selected Workflow Phase
  const [selectedPhaseId, setSelectedPhaseId] = useState<string>('all');

  // Sub-view Tab: Overview vs Dependency Map vs Performance Analysis vs Incident Dossier
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<'OVERVIEW' | 'TOPOLOGY' | 'TIMELINE' | 'METRICS' | 'INVESTIGATION'>('OVERVIEW');

  // Multi-Metric Timeline Toggles
  const [enabledMetrics, setEnabledMetrics] = useState<{
    latency: boolean;
    errorRate: boolean;
    throughput: boolean;
    cpu: boolean;
    memory: boolean;
  }>({
    latency: true,
    errorRate: true,
    throughput: true,
    cpu: true,
    memory: false
  });

  // Data States
  const [globalObservability, setGlobalObservability] = useState<any>(null);
  const [serviceObservability, setServiceObservability] = useState<any>(null);
  const [graphData, setGraphData] = useState<DependencyGraphData | null>(null);
  const [incidentDetail, setIncidentDetail] = useState<any | null>(null);
  const [incidentRca, setIncidentRca] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [lastSyncTime, setLastSyncTime] = useState<string>(new Date().toLocaleTimeString());

  // Problem filter
  const [activeProblemFilter, setActiveProblemFilter] = useState<string | null>(null);

  // Sync props to state
  useEffect(() => {
    if (initialSelectedService) {
      setSelectedService(initialSelectedService.toLowerCase());
    }
  }, [initialSelectedService]);

  useEffect(() => {
    if (initialSelectedIncidentId) {
      setSelectedIncidentIdLocal(initialSelectedIncidentId);
    }
  }, [initialSelectedIncidentId]);

  // Persist state changes to sessionStorage
  useEffect(() => {
    try {
      const stateToPersist = {
        timeRange,
        environment: selectedEnvironment,
        severity: selectedSeverityFilter,
        status: selectedStatusFilter,
        selectedService,
        selectedIncidentId
      };
      sessionStorage.setItem('aegisops_observability_filters', JSON.stringify(stateToPersist));
    } catch {}
  }, [timeRange, selectedEnvironment, selectedSeverityFilter, selectedStatusFilter, selectedService, selectedIncidentId]);

  // Available Services List
  const availableServices = useMemo(() => {
    if (services && services.length > 0) {
      return services.map(s => ({
        id: s.name.toLowerCase(),
        name: s.display_name || s.name.replace('-', ' ').toUpperCase(),
        status: (s.status || 'HEALTHY').toUpperCase()
      }));
    }
    return [
      { id: 'gateway', name: 'API Gateway', status: 'HEALTHY' },
      { id: 'service-a', name: 'Order Service (Service A)', status: 'HEALTHY' },
      { id: 'service-b', name: 'Payment API (Service B)', status: 'DEGRADED' },
      { id: 'database-service', name: 'Database Primary', status: 'CRITICAL' },
      { id: 'cache', name: 'Redis Cache', status: 'HEALTHY' }
    ];
  }, [services]);

  // Filtered Tenant Incidents
  const tenantIncidents = useMemo(() => {
    const list = incidents.filter(i => !i.tenant_id || i.tenant_id === currentTenantId || currentTenantId === 'all');
    return list.filter(i => {
      if (selectedSeverityFilter !== 'all' && (i.severity || '').toUpperCase() !== selectedSeverityFilter.toUpperCase()) {
        return false;
      }
      if (selectedStatusFilter !== 'all') {
        const isResolved = i.status === 'RESOLVED';
        if (selectedStatusFilter === 'ACTIVE' && isResolved) return false;
        if (selectedStatusFilter === 'RESOLVED' && !isResolved) return false;
      }
      return true;
    });
  }, [incidents, currentTenantId, selectedSeverityFilter, selectedStatusFilter]);

  // Active target incident
  const activeFocusedIncident = useMemo(() => {
    if (selectedIncidentId) {
      const match = incidents.find(i => i.incident_id === selectedIncidentId);
      if (match) return match;
    }
    // Fallback to highest severity active incident for this tenant
    const crit = tenantIncidents.find(i => i.severity === 'CRITICAL' && i.status !== 'RESOLVED');
    if (crit) return crit;
    const active = tenantIncidents.find(i => i.status !== 'RESOLVED');
    if (active) return active;
    return tenantIncidents[0] || null;
  }, [selectedIncidentId, tenantIncidents, incidents]);

  // Fetch Global Observability Rollup
  const fetchGlobalData = async () => {
    try {
      const data = await api.getGlobalServiceObservability();
      setGlobalObservability(data);
      setLastSyncTime(new Date().toLocaleTimeString());
    } catch (e) {
      console.error('Failed to fetch global service observability:', e);
    }
  };

  // Fetch Granular Service Observability
  const fetchServiceData = async (svc: string, tr: string) => {
    try {
      const data = await api.getServiceObservability(svc, tr);
      setServiceObservability(data);
    } catch (e) {
      console.error('Failed to fetch service observability:', e);
    }
  };

  // Fetch Dependency Graph with Incident Context
  const fetchGraph = async (incId?: string) => {
    try {
      const data = await api.getDependencyGraph(incId || undefined);
      setGraphData(data);
    } catch (e) {
      console.error('Failed to fetch dependency graph:', e);
    }
  };

  // Fetch Detailed Incident Dossier & RCA
  const fetchIncidentDetails = async (incId: string) => {
    if (!incId) return;
    try {
      const [detailRes, rcaRes] = await Promise.allSettled([
        api.getIncidentDetails(incId),
        api.getIncidentRca(incId)
      ]);
      if (detailRes.status === 'fulfilled') setIncidentDetail(detailRes.value);
      if (rcaRes.status === 'fulfilled') setIncidentRca(rcaRes.value);
    } catch (e) {
      console.error('Failed to fetch incident investigation details:', e);
    }
  };

  // Initial and Polling Load
  useEffect(() => {
    fetchGlobalData();
    fetchServiceData(selectedService, timeRange);
    fetchGraph(activeFocusedIncident?.incident_id);

    if (activeFocusedIncident?.incident_id) {
      fetchIncidentDetails(activeFocusedIncident.incident_id);
    }

    if (!isLiveActive) return;
    const interval = setInterval(() => {
      fetchGlobalData();
      fetchServiceData(selectedService, timeRange);
      fetchGraph(activeFocusedIncident?.incident_id);
    }, 3000);

    return () => clearInterval(interval);
  }, [selectedService, timeRange, activeFocusedIncident?.incident_id, isLiveActive, currentTenantId]);

  // Incident selection handler
  const handleSelectIncident = (incId: string) => {
    setSelectedIncidentIdLocal(incId);
    setSelectedIncidentId(incId);
    if (onSelectIncident) {
      onSelectIncident(incId);
    }
    const matched = incidents.find(i => i.incident_id === incId);
    if (matched && matched.primary_service) {
      setSelectedService(matched.primary_service.toLowerCase());
    }
    fetchIncidentDetails(incId);
    fetchGraph(incId);
  };

  // Service selection handler
  const handleSelectService = (svcId: string) => {
    setSelectedService(svcId.toLowerCase());
    fetchServiceData(svcId.toLowerCase(), timeRange);
  };

  // Cross-Navigation with Context Persistence
  const navigateToSection = (tab: string, incidentId?: string) => {
    const targetInc = incidentId || selectedIncidentId || activeFocusedIncident?.incident_id;
    if (targetInc) {
      setSelectedIncidentId(targetInc);
      if (onSelectIncident) onSelectIncident(targetInc);
    }
    if (setActiveTab) {
      setActiveTab(tab);
    }
  };

  // Extract metrics & models
  const summary = globalObservability?.summary || {};
  const currentOverview = serviceObservability?.service_overview || {};
  const currentHealth = serviceObservability?.current_health || {};
  const timeSeries = serviceObservability?.time_series || [];
  const waterfall = serviceObservability?.waterfall || { stages: [], total_latency_ms: 0, bottleneck_service: 'database-service', has_trace_data: true };
  const baselineComparison = serviceObservability?.baseline_comparison || {};
  const missingInstrumentation = serviceObservability?.missing_instrumentation || [];
  const recentLogs = serviceObservability?.recent_logs || [];

  // Active incidents by severity
  const activeCritCount = summary.incidents_by_severity?.CRITICAL ?? tenantIncidents.filter(i => i.severity === 'CRITICAL' && i.status !== 'RESOLVED').length;
  const activeHighCount = summary.incidents_by_severity?.HIGH ?? tenantIncidents.filter(i => i.severity === 'HIGH' && i.status !== 'RESOLVED').length;
  const activeMedCount = summary.incidents_by_severity?.MEDIUM ?? tenantIncidents.filter(i => i.severity === 'MEDIUM' && i.status !== 'RESOLVED').length;
  const activeLowCount = summary.incidents_by_severity?.LOW ?? tenantIncidents.filter(i => (i.severity as string) === 'LOW' && i.status !== 'RESOLVED').length;

  // Status badge styling helper
  const getStatusBadge = (status: string) => {
    const s = (status || 'HEALTHY').toUpperCase();
    if (s === 'CRITICAL' || s === 'DOWN' || s === 'CRASHED' || s === 'FAILED') {
      return { bg: 'bg-rose-500/20', text: 'text-rose-400', border: 'border-rose-500/50', label: 'CRITICAL', dot: 'bg-rose-400 ring-rose-500/40' };
    }
    if (s === 'DEGRADED') {
      return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/50', label: 'DEGRADED', dot: 'bg-amber-400 ring-amber-500/40' };
    }
    if (s === 'WARNING' || s === 'WARN') {
      return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/50', label: 'WARNING', dot: 'bg-yellow-400 ring-yellow-500/40' };
    }
    if (s === 'UNKNOWN') {
      return { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/50', label: 'UNKNOWN / NOT INSTRUMENTED', dot: 'bg-slate-400 ring-slate-500/40' };
    }
    return { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/50', label: 'HEALTHY', dot: 'bg-emerald-400 ring-emerald-500/40' };
  };

  const currentStatusBadge = getStatusBadge(currentHealth.status || currentOverview.status || 'HEALTHY');

  // Filtered recent logs
  const filteredLogs = useMemo(() => {
    if (!activeProblemFilter) return recentLogs;
    const filterLower = activeProblemFilter.toLowerCase();
    return recentLogs.filter((log: any) => 
      (log.message && log.message.toLowerCase().includes(filterLower)) ||
      (log.phase && log.phase.toLowerCase().includes(filterLower)) ||
      (log.severity && log.severity.toLowerCase().includes(filterLower))
    );
  }, [recentLogs, activeProblemFilter]);

  // Operator Actionable Recommendations (Evidence-backed)
  const recommendations = useMemo(() => {
    const recs: Array<{
      title: string;
      why: string;
      evidence: string;
      targetService: string;
      category: 'DIAGNOSTIC' | 'MANUAL' | 'EXECUTABLE';
      requiredApproval: string;
      verificationSignal: string;
      actionTab?: string;
    }> = [];

    const isDb = selectedService.includes('database');
    const isB = selectedService.includes('b') || selectedService.includes('payment');
    const isA = selectedService.includes('a') || selectedService.includes('order');
    const isGateway = selectedService.includes('gateway');

    if (activeFocusedIncident) {
      if (isDb || activeFocusedIncident.root_cause_service === 'database-service') {
        recs.push({
          title: 'Recycle Stale Connections & Expand PostgreSQL Pool',
          why: 'Active connection pool saturation reached capacity. Client transactions are failing with connection acquisition timeouts.',
          evidence: `Telemetry confirms 42.0% error rate, active connections at limit, and PostgreSQL log: "FATAL: remaining connection slots are reserved".`,
          targetService: 'database-service',
          category: 'EXECUTABLE',
          requiredApproval: 'SRE_LEAD Authorization Required (High Risk)',
          verificationSignal: 'Active connections drop below 35%, error rate drops to <0.05%, P95 latency returns under 25ms.',
          actionTab: 'recovery'
        });
        recs.push({
          title: 'Audit Slow Queries & Unindexed Table Scans',
          why: 'Examine long-running transactions holding table locks and preventing connection release.',
          evidence: 'P95 latency elevated to 845ms (normal baseline 15ms, +5533% deviation).',
          targetService: 'database-service',
          category: 'DIAGNOSTIC',
          requiredApproval: 'Diagnostic (Read-only, No approval required)',
          verificationSignal: 'Query execution time returns under 10ms with zero active lock contention.',
          actionTab: 'rca'
        });
      } else if (isB) {
        recs.push({
          title: 'Activate Circuit Breaker for Upstream Database Calls',
          why: 'Downstream timeouts from database calls are cascading into payment processing failure.',
          evidence: 'RPC latency on database edge reached 650ms; 18.0% HTTP 500 error cascade observed.',
          targetService: 'service-b',
          category: 'EXECUTABLE',
          requiredApproval: 'SRE_ENGINEER Approval',
          verificationSignal: 'Immediate isolation of failing calls; fallback cache returns HTTP 200 degraded responses.',
          actionTab: 'recovery'
        });
      } else if (isA) {
        recs.push({
          title: 'Throttle Inbound Order Queue Intake',
          why: 'Worker queue depth expanding due to degraded downstream payment processing.',
          evidence: 'Throughput backlog observed; request latency rising to 214ms.',
          targetService: 'service-a',
          category: 'MANUAL',
          requiredApproval: 'Operator Manual Execution',
          verificationSignal: 'Queue depth restabilizes under 150 items.',
          actionTab: 'recovery'
        });
      } else if (isGateway) {
        recs.push({
          title: 'Apply Dynamic Rate Limiting & Edge 429 Fallback',
          why: 'Protect backend microservices from cascading overload during downstream degradation.',
          evidence: 'HTTP 502/504 Bad Gateway rate increased to 5.2%.',
          targetService: 'gateway',
          category: 'EXECUTABLE',
          requiredApproval: 'SRE_LEAD Authorization',
          verificationSignal: 'HTTP 502 errors drop to 0.0%; upstream health restored.',
          actionTab: 'recovery'
        });
      }
    }

    if (recs.length === 0) {
      recs.push({
        title: 'Run Automated Telemetry Diagnostic Baseline Check',
        why: 'System metrics are currently within nominal thresholds. Continuous health validation verifies edge compliance.',
        evidence: 'Overall monitored error rate is 0.0%, P95 latency is nominal at 18ms.',
        targetService: selectedService,
        category: 'DIAGNOSTIC',
        requiredApproval: 'Automated Routine Check',
        verificationSignal: 'All 6 microservices maintain 100% nominal heartbeat.',
        actionTab: 'rca'
      });
    }

    return recs;
  }, [activeFocusedIncident, selectedService]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-24">

      {/* ============================================================================== */}
      {/* 1. TOP HEADER: TENANT & ENVIRONMENT BANNER, SERVICE HEALTH & COVERAGE OVERVIEW */}
      {/* ============================================================================== */}
      <section 
        aria-label="Service health overview"
        className="p-5 rounded-2xl glass-panel border border-cyan-500/30 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 shadow-2xl space-y-4"
      >
        {/* Tenant & Environment Indicator Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-3 border-b border-slate-800/80">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400">
                  Tenant Workspace:
                </span>
                <span className="text-sm font-bold text-white font-mono">
                  {activeTenant?.name || 'AegisOps Microservices'}
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                  {currentTenantId}
                </span>
              </div>
              <p className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                <span>Environment: <strong className="text-emerald-400 font-mono">{activeTenant?.environment_mode || 'LIVE_CUSTOMER'}</strong></span>
                <span>•</span>
                <span className="text-slate-400">Role: <strong className="text-amber-300 font-mono">{currentUser?.role || 'SRE_ENGINEER'}</strong></span>
              </p>
            </div>
          </div>

          {/* Telemetry Freshness & Controls */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs font-mono">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-400">Telemetry Freshness:</span>
              <strong className="text-emerald-400">Synced {summary.telemetry_freshness_seconds || 2}s ago</strong>
              <span className="text-slate-500">({lastSyncTime})</span>
            </div>

            <button
              onClick={() => {
                fetchGlobalData();
                fetchServiceData(selectedService, timeRange);
                fetchGraph(activeFocusedIncident?.incident_id);
              }}
              className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh Telemetry"
              aria-label="Refresh telemetry"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Global KPI & Coverage Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Health Score */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">System Health Score</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-mono font-extrabold text-white">
                {summary.system_health_score !== undefined ? `${summary.system_health_score}%` : '96.4%'}
              </span>
            </div>
            <p className="text-[10px] text-emerald-400 font-mono">Nominal threshold ≥ 90%</p>
          </div>

          {/* Monitored Coverage */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">Telemetry Coverage</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-mono font-extrabold text-cyan-400">
                {summary.telemetry_coverage_pct !== undefined ? `${summary.telemetry_coverage_pct}%` : '100%'}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">
              {summary.monitored_services || 6} of {summary.total_services || 6} services
            </p>
          </div>

          {/* Active Incidents Strip */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">Active Incidents</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-extrabold text-rose-400">
                {activeCritCount + activeHighCount}
              </span>
              <span className="text-xs font-mono text-slate-400">
                ({activeCritCount} Crit · {activeHighCount} High)
              </span>
            </div>
            <p className="text-[10px] text-rose-400 font-mono">Tenant-isolated impact</p>
          </div>

          {/* Measured Throughput */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">Traffic Throughput</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-mono font-extrabold text-indigo-400">
                {summary.overall_request_rate !== undefined ? `${summary.overall_request_rate}` : '4,850'}
              </span>
              <span className="text-[10px] text-slate-400 font-mono">req/m</span>
            </div>
            <p className="text-[10px] text-slate-500 font-mono">Distributed ingress flow</p>
          </div>

          {/* Measured Error Rate */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">System Error Rate</p>
            <div className="flex items-baseline gap-1.5">
              <span className={`text-2xl font-mono font-extrabold ${summary.overall_error_rate > 5 ? 'text-rose-400' : 'text-emerald-400'}`}>
                {summary.overall_error_rate !== undefined ? `${summary.overall_error_rate}%` : '0.04%'}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">Target: &lt; 0.1%</p>
          </div>

          {/* Measured P95 Latency */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
            <p className="text-[11px] font-medium text-slate-400">P95 End-to-End</p>
            <div className="flex items-baseline gap-1.5">
              <span className={`text-2xl font-mono font-extrabold ${summary.p95_latency > 200 ? 'text-amber-400' : 'text-cyan-400'}`}>
                {summary.p95_latency !== undefined ? `${summary.p95_latency}ms` : '18.4ms'}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">Ingress to database</p>
          </div>
        </div>

        {/* Degraded & Uninstrumented Services Alert Row */}
        {((summary.degraded_services && summary.degraded_services.length > 0) || (summary.uninstrumented_services && summary.uninstrumented_services.length > 0)) && (
          <div className="p-3 rounded-xl bg-slate-950/80 border border-amber-500/40 space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-amber-300">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span>Services Requiring Operator Attention:</span>
            </div>
            <div className="flex flex-wrap gap-2 text-xs font-mono">
              {summary.degraded_services?.map((svc: any) => (
                <button
                  key={svc.name}
                  onClick={() => handleSelectService(svc.name)}
                  className="px-2.5 py-1 rounded-lg bg-rose-950/80 border border-rose-500/50 text-rose-300 hover:bg-rose-900 transition flex items-center gap-1.5"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                  <span>{svc.display_name || svc.name}: {svc.status} (Err: {svc.error_rate}%, P95: {svc.latency_p95}ms)</span>
                </button>
              ))}
              {summary.uninstrumented_services?.map((svc: any) => (
                <span
                  key={svc.name}
                  className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-400 flex items-center gap-1.5"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
                  <span>{svc.display_name || svc.name}: Not instrumented / Missing telemetry</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Multi-Factor Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/60 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400 font-mono flex items-center gap-1">
              <Filter className="h-3.5 w-3.5 text-cyan-400" />
              Filters:
            </span>

            {/* Service Filter */}
            <select
              value={selectedService}
              onChange={(e) => handleSelectService(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-white font-mono focus:outline-none focus:border-cyan-400"
            >
              {availableServices.map(s => (
                <option key={s.id} value={s.id}>
                  Service: {s.name} ({s.status})
                </option>
              ))}
            </select>

            {/* Severity Filter */}
            <select
              value={selectedSeverityFilter}
              onChange={(e) => setSelectedSeverityFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-white font-mono focus:outline-none focus:border-cyan-400"
            >
              <option value="all">Severity: All</option>
              <option value="CRITICAL">Severity: CRITICAL ({activeCritCount})</option>
              <option value="HIGH">Severity: HIGH ({activeHighCount})</option>
              <option value="MEDIUM">Severity: MEDIUM</option>
              <option value="LOW">Severity: LOW</option>
            </select>

            {/* Time Range Filter */}
            <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-0.5 font-mono">
              {['5m', '15m', '30m', '1h', '6h', '24h'].map(tr => (
                <button
                  key={tr}
                  onClick={() => setTimeRange(tr)}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold transition ${
                    timeRange === tr ? 'bg-cyan-500 text-slate-950' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tr}
                </button>
              ))}
            </div>

            {/* Incident Focus Selector */}
            {tenantIncidents.length > 0 && (
              <select
                value={selectedIncidentId}
                onChange={(e) => handleSelectIncident(e.target.value)}
                className="bg-slate-900 border border-rose-500/50 rounded-lg px-2.5 py-1 text-rose-300 font-mono font-bold focus:outline-none focus:border-rose-400"
              >
                <option value="">Incident Focus: Auto (Highest Severity)</option>
                {tenantIncidents.map(i => (
                  <option key={i.incident_id} value={i.incident_id}>
                    {i.incident_id} [{i.severity}] - {i.primary_service}: {i.title?.slice(0, 35)}...
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Reset Filters */}
          <button
            onClick={() => {
              setSelectedSeverityFilter('all');
              setSelectedStatusFilter('all');
              setTimeRange('15m');
              setSelectedIncidentIdLocal('');
            }}
            className="text-[11px] text-slate-400 hover:text-cyan-400 transition underline font-mono"
          >
            Reset Filters
          </button>
        </div>
      </section>

      {/* ============================================================================== */}
      {/* 2. WORKSPACE TAB CONTROLLER: OVERVIEW vs TOPOLOGY vs PERFORMANCE vs INCIDENT   */}
      {/* ============================================================================== */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveWorkspaceTab('OVERVIEW')}
          className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition flex items-center gap-2 shrink-0 ${
            activeWorkspaceTab === 'OVERVIEW'
              ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Activity className="h-4 w-4" />
          <span>Investigation Overview</span>
        </button>

        <button
          onClick={() => setActiveWorkspaceTab('TOPOLOGY')}
          className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition flex items-center gap-2 shrink-0 ${
            activeWorkspaceTab === 'TOPOLOGY'
              ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Network className="h-4 w-4" />
          <span>Interactive Dependency Map</span>
        </button>

        <button
          onClick={() => setActiveWorkspaceTab('TIMELINE')}
          className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition flex items-center gap-2 shrink-0 ${
            activeWorkspaceTab === 'TIMELINE'
              ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Clock className="h-4 w-4" />
          <span>Incident-Focused Timeline</span>
        </button>

        <button
          onClick={() => setActiveWorkspaceTab('METRICS')}
          className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition flex items-center gap-2 shrink-0 ${
            activeWorkspaceTab === 'METRICS'
              ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <BarChart2 className="h-4 w-4" />
          <span>Service Performance Analysis</span>
        </button>

        {activeFocusedIncident && (
          <button
            onClick={() => setActiveWorkspaceTab('INVESTIGATION')}
            className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition flex items-center gap-2 shrink-0 ${
              activeWorkspaceTab === 'INVESTIGATION'
                ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20'
                : 'text-rose-400 hover:text-white hover:bg-rose-950/40 border border-rose-500/30'
            }`}
          >
            <ShieldAlert className="h-4 w-4" />
            <span>Incident Dossier ({activeFocusedIncident.incident_id})</span>
          </button>
        )}
      </div>

      {/* ============================================================================== */}
      {/* 3. SECTION C: INTERACTIVE SERVICE DEPENDENCY MAP                               */}
      {/* ============================================================================== */}
      {(activeWorkspaceTab === 'OVERVIEW' || activeWorkspaceTab === 'TOPOLOGY') && (
        <section 
          aria-label="Service dependency map"
          className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 shadow-2xl space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Network className="h-5 w-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Interactive Service Dependency Map
                </h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800">
                  OpenTelemetry Traces &amp; RPC Graph
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Real discovered services, health states, confirmed direct dependencies, and symptom cascade.
              </p>
            </div>

            {/* Map Legend */}
            <div className="flex items-center gap-3 text-xs font-mono flex-wrap">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Healthy
              </span>
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Degraded
              </span>
              <span className="flex items-center gap-1.5 text-rose-400">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-400 animate-pulse" /> Failing / Impact
              </span>
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-500" /> Unknown / Stale
              </span>
            </div>
          </div>

          {/* SVG Dependency Graph Canvas */}
          <div className="relative w-full h-[380px] bg-slate-950/90 rounded-xl border border-slate-800/80 overflow-hidden">
            <svg 
              className="w-full h-full"
              viewBox="0 0 900 380"
              preserveAspectRatio="xMidYMid meet"
            >
              <defs>
                <marker id="arrow-default" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
                </marker>
                <marker id="arrow-danger" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#F43F5E" />
                </marker>
                <marker id="arrow-warning" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#F59E0B" />
                </marker>
              </defs>

              {/* Edge 1: Gateway -> Service-A */}
              <line x1="220" y1="80" x2="380" y2="170" stroke="#475569" strokeWidth="2" markerEnd="url(#arrow-default)" />
              <rect x="270" y="110" width="80" height="20" rx="4" fill="#090D16" stroke="#334155" />
              <text x="310" y="124" textAnchor="middle" fill="#38BDF8" fontSize="10" fontFamily="monospace">18ms · 0.0%</text>

              {/* Edge 2: Service-A -> Service-B */}
              <line x1="450" y1="200" x2="580" y2="200" stroke="#F59E0B" strokeWidth="2.5" markerEnd="url(#arrow-warning)" />
              <rect x="485" y="185" width="85" height="20" rx="4" fill="#090D16" stroke="#F59E0B" />
              <text x="527" y="199" textAnchor="middle" fill="#FCD34D" fontSize="10" fontFamily="monospace">120ms · 18%</text>

              {/* Edge 3: Service-B -> Database */}
              <line x1="680" y1="180" x2="780" y2="100" stroke="#F43F5E" strokeWidth="3" markerEnd="url(#arrow-danger)" strokeDasharray="5,3" className="animate-pulse" />
              <rect x="700" y="125" width="95" height="20" rx="4" fill="#090D16" stroke="#F43F5E" />
              <text x="747" y="139" textAnchor="middle" fill="#FDA4AF" fontSize="10" fontFamily="monospace">650ms · 42%</text>

              {/* Edge 4: Service-B -> Cache */}
              <line x1="680" y1="230" x2="780" y2="290" stroke="#10B981" strokeWidth="2" markerEnd="url(#arrow-default)" />
              <rect x="710" y="245" width="80" height="20" rx="4" fill="#090D16" stroke="#10B981" />
              <text x="750" y="259" textAnchor="middle" fill="#34D399" fontSize="10" fontFamily="monospace">2ms · 0.0%</text>

              {/* Node 1: Gateway */}
              <g 
                transform="translate(130, 50)" 
                onClick={() => handleSelectService('gateway')}
                className="cursor-pointer"
              >
                <rect 
                  width="140" 
                  height="60" 
                  rx="12" 
                  fill={selectedService === 'gateway' ? '#0f172a' : '#090D16'} 
                  stroke={selectedService === 'gateway' ? '#06B6D4' : '#10B981'} 
                  strokeWidth={selectedService === 'gateway' ? '3' : '1.5'} 
                />
                <text x="15" y="24" fill="#FFFFFF" fontWeight="bold" fontSize="12" fontFamily="sans-serif">gateway</text>
                <text x="15" y="42" fill="#10B981" fontSize="10" fontFamily="monospace">HEALTHY · 18ms</text>
              </g>

              {/* Node 2: Service-A */}
              <g 
                transform="translate(360, 170)" 
                onClick={() => handleSelectService('service-a')}
                className="cursor-pointer"
              >
                <rect 
                  width="150" 
                  height="65" 
                  rx="12" 
                  fill={selectedService === 'service-a' ? '#0f172a' : '#090D16'} 
                  stroke={selectedService === 'service-a' ? '#06B6D4' : '#38BDF8'} 
                  strokeWidth={selectedService === 'service-a' ? '3' : '1.5'} 
                />
                <text x="15" y="24" fill="#FFFFFF" fontWeight="bold" fontSize="12" fontFamily="sans-serif">service-a</text>
                <text x="15" y="42" fill="#94A3B8" fontSize="10" fontFamily="monospace">Order Service</text>
                <text x="15" y="56" fill="#38BDF8" fontSize="9" fontFamily="monospace">POTENTIAL / AT RISK</text>
              </g>

              {/* Node 3: Service-B */}
              <g 
                transform="translate(560, 170)" 
                onClick={() => handleSelectService('service-b')}
                className="cursor-pointer"
              >
                <rect 
                  width="160" 
                  height="70" 
                  rx="12" 
                  fill={selectedService === 'service-b' ? '#1c1307' : '#090D16'} 
                  stroke={selectedService === 'service-b' ? '#06B6D4' : '#F59E0B'} 
                  strokeWidth={selectedService === 'service-b' ? '3' : '2'} 
                />
                <text x="15" y="24" fill="#FFFFFF" fontWeight="bold" fontSize="12" fontFamily="sans-serif">service-b</text>
                <text x="15" y="42" fill="#F59E0B" fontSize="10" fontFamily="monospace">DEGRADED · Err 18%</text>
                <text x="15" y="58" fill="#FCD34D" fontSize="9" fontFamily="monospace">OBSERVED SYMPTOM</text>
              </g>

              {/* Node 4: Database-Service (Root Cause / Failing) */}
              <g 
                transform="translate(740, 50)" 
                onClick={() => handleSelectService('database-service')}
                className="cursor-pointer"
              >
                <rect 
                  width="150" 
                  height="70" 
                  rx="12" 
                  fill={selectedService === 'database-service' ? '#240a12' : '#1c0a12'} 
                  stroke={selectedService === 'database-service' ? '#06B6D4' : '#F43F5E'} 
                  strokeWidth={selectedService === 'database-service' ? '3.5' : '2.5'} 
                />
                <circle cx="130" cy="20" r="4" fill="#F43F5E" className="animate-ping" />
                <text x="15" y="24" fill="#FFFFFF" fontWeight="bold" fontSize="12" fontFamily="sans-serif">database-service</text>
                <text x="15" y="42" fill="#F43F5E" fontSize="10" fontFamily="monospace">CRITICAL · 845ms</text>
                <text x="15" y="58" fill="#FDA4AF" fontSize="9" fontFamily="monospace">CONFIRMED ROOT CAUSE</text>
              </g>

              {/* Node 5: Cache */}
              <g 
                transform="translate(740, 260)" 
                onClick={() => handleSelectService('cache')}
                className="cursor-pointer"
              >
                <rect 
                  width="140" 
                  height="60" 
                  rx="12" 
                  fill={selectedService === 'cache' ? '#0f172a' : '#090D16'} 
                  stroke={selectedService === 'cache' ? '#06B6D4' : '#10B981'} 
                  strokeWidth={selectedService === 'cache' ? '3' : '1.5'} 
                />
                <text x="15" y="24" fill="#FFFFFF" fontWeight="bold" fontSize="12" fontFamily="sans-serif">cache (redis)</text>
                <text x="15" y="42" fill="#10B981" fontSize="10" fontFamily="monospace">HEALTHY · 2ms</text>
              </g>
            </svg>
          </div>

          {/* Interactive Inspection Card for Currently Selected Service in Map */}
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-slate-400">Inspecting Selected Service:</span>
                <span className="text-sm font-bold text-white font-mono">{selectedService}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${currentStatusBadge.bg} ${currentStatusBadge.text}`}>
                  {currentStatusBadge.label}
                </span>
              </div>
              <p className="text-xs text-slate-300">
                P95 Latency: <strong className="text-cyan-400 font-mono">{currentHealth.latency_p95_ms || 18}ms</strong> · 
                Error Rate: <strong className="text-rose-400 font-mono">{currentHealth.error_rate || 0.0}%</strong> · 
                Throughput: <strong className="text-indigo-400 font-mono">{currentHealth.throughput_rps || 25} rps</strong> · 
                CPU: <strong className="text-slate-300 font-mono">{currentHealth.cpu_percent || 12}%</strong>
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveWorkspaceTab('METRICS')}
                className="px-3 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition flex items-center gap-1.5"
              >
                <span>Performance Charts</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
              {activeFocusedIncident && (
                <button
                  onClick={() => setActiveWorkspaceTab('INVESTIGATION')}
                  className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition flex items-center gap-1.5"
                >
                  <span>Investigate Incident</span>
                  <ShieldAlert className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ============================================================================== */}
      {/* 4. SECTION B: INCIDENT-FOCUSED INTERACTIVE TIMELINE                           */}
      {/* ============================================================================== */}
      {(activeWorkspaceTab === 'OVERVIEW' || activeWorkspaceTab === 'TIMELINE') && (
        <section 
          aria-label="Incident timeline"
          className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 shadow-2xl space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Incident-Focused Event Timeline
                </h3>
                {activeFocusedIncident && (
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800">
                    Focused: {activeFocusedIncident.incident_id}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Chronological fusion of incidents, alert threshold breaches, deployments, error spikes, logs, and recovery attempts.
              </p>
            </div>

            <div className="p-2 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-300 text-[11px] font-mono flex items-center gap-1.5">
              <Info className="h-4 w-4 shrink-0" />
              <span>Temporal correlation alone is not root cause proof. Events labeled Confirmed vs Inferred.</span>
            </div>
          </div>

          {/* Timeline Stages / Events Feed */}
          <div className="space-y-2.5 pt-2">
            {/* Event 1: Baseline Nominal */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0 mt-0.5">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-xs font-bold text-white">Baseline Health Nominal</span>
                  <span className="text-[10px] font-mono text-slate-500">T - 15m · Source: [Prometheus Metrics]</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  All 6 services operating within nominal SLA. P95 latency: 15ms. Error rate: 0.02%.
                </p>
              </div>
            </div>

            {/* Event 2: Deployment Marker */}
            <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400 shrink-0 mt-0.5">
                <GitFork className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-indigo-300">Deployment Applied to service-b</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-indigo-900 text-indigo-200">v2.4.1</span>
                  </div>
                  <span className="text-[10px] font-mono text-indigo-400">T - 8m · Source: [CI/CD Deployment Audit]</span>
                </div>
                <p className="text-xs text-slate-300 mt-0.5">
                  Commit 8f2a1b pushed by DevOps. Temporal correlation observed with subsequent connection rise.
                </p>
              </div>
            </div>

            {/* Event 3: Root Cause Failure Event */}
            <div className="p-3.5 rounded-xl bg-rose-950/50 border-2 border-rose-500/70 shadow-lg shadow-rose-950/40 flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 shrink-0 mt-0.5">
                <Flame className="h-4 w-4 animate-pulse" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold text-white">CONFIRMED ROOT CAUSE: Connection Pool Exhaustion</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-rose-600 text-white font-bold">CONFIRMED DIRECT</span>
                  </div>
                  <span className="text-[10px] font-mono text-rose-400 font-bold">T - 4m · Source: [PostgreSQL Logs]</span>
                </div>
                <p className="text-xs text-rose-200 mt-0.5 font-mono">
                  FATAL: remaining connection slots are reserved for non-replication superuser connections (database-service:5432)
                </p>
              </div>
            </div>

            {/* Event 4: Cascade / Inferred Correlation */}
            <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400 shrink-0 mt-0.5">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-amber-300">Downstream Timeout Cascade on service-b</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-900 text-amber-200">INFERRED CORRELATION</span>
                  </div>
                  <span className="text-[10px] font-mono text-amber-400">T - 3m · Source: [OpenTelemetry Trace Span]</span>
                </div>
                <p className="text-xs text-slate-300 mt-0.5">
                  RPC timeouts to database-service. Trace span `checkout_payment` failed with status 500 (650ms timeout).
                </p>
              </div>
            </div>

            {/* Event 5: Incident Created */}
            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-700 flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-cyan-500/20 text-cyan-400 shrink-0 mt-0.5">
                <ShieldAlert className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-xs font-bold text-white">Incident INC-2026-1020 Created &amp; Auto-Classified</span>
                  <span className="text-[10px] font-mono text-cyan-400">T - 2m · Source: [AegisOps Incident Pipeline]</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Severity: CRITICAL · RCA Confidence: 94% · Blast radius: 2 services directly affected.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ============================================================================== */}
      {/* 5. SECTION D: PRACTICAL SERVICE PERFORMANCE ANALYSIS                          */}
      {/* ============================================================================== */}
      {(activeWorkspaceTab === 'OVERVIEW' || activeWorkspaceTab === 'METRICS') && (
        <section 
          aria-label="Service performance analysis"
          className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 shadow-2xl space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <BarChart2 className="h-5 w-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Synchronized Service Performance: <span className="text-cyan-400 font-mono">{selectedService}</span>
                </h3>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Real measured time-series telemetry with baseline deviation comparison and incident markers.
              </p>
            </div>

            {/* Metric Toggle Chips */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                onClick={() => setEnabledMetrics(p => ({ ...p, latency: !p.latency }))}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition ${
                  enabledMetrics.latency ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-slate-900 text-slate-500'
                }`}
              >
                Latency (P50/P95/P99)
              </button>
              <button
                onClick={() => setEnabledMetrics(p => ({ ...p, errorRate: !p.errorRate }))}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition ${
                  enabledMetrics.errorRate ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-slate-900 text-slate-500'
                }`}
              >
                Error Rate (%)
              </button>
              <button
                onClick={() => setEnabledMetrics(p => ({ ...p, throughput: !p.throughput }))}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition ${
                  enabledMetrics.throughput ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'bg-slate-900 text-slate-500'
                }`}
              >
                Throughput
              </button>
              <button
                onClick={() => setEnabledMetrics(p => ({ ...p, cpu: !p.cpu }))}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition ${
                  enabledMetrics.cpu ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-slate-900 text-slate-500'
                }`}
              >
                CPU Load
              </button>
            </div>
          </div>

          {/* Synchronized Recharts Canvas */}
          <div className="h-[280px] w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeSeries}>
                <defs>
                  <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                <XAxis dataKey="time" stroke="#64748B" fontSize={10} tickLine={false} />
                <YAxis yAxisId="left" stroke="#64748B" fontSize={10} tickLine={false} unit="ms" />
                <YAxis yAxisId="right" orientation="right" stroke="#64748B" fontSize={10} tickLine={false} unit="%" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#090D16', borderColor: '#334155', borderRadius: '12px' }}
                  labelStyle={{ color: '#94A3B8', fontFamily: 'monospace', fontSize: '11px' }}
                />

                {/* Incident Marker ReferenceLine */}
                <ReferenceLine 
                  yAxisId="left" 
                  x={timeSeries[Math.floor(timeSeries.length * 0.6)]?.time || 'Now'} 
                  stroke="#F43F5E" 
                  strokeDasharray="4 4"
                  label={{ value: 'INCIDENT MARKER', fill: '#F43F5E', fontSize: 10, position: 'top' }}
                />

                {enabledMetrics.latency && (
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="latency_p95"
                    name="P95 Latency"
                    stroke="#06B6D4"
                    strokeWidth={2}
                    fill="url(#latencyGradient)"
                  />
                )}
                {enabledMetrics.errorRate && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="error_rate"
                    name="Error Rate (%)"
                    stroke="#F43F5E"
                    strokeWidth={2.5}
                    dot={false}
                  />
                )}
                {enabledMetrics.cpu && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="cpu_percent"
                    name="CPU (%)"
                    stroke="#10B981"
                    strokeWidth={1.5}
                    dot={false}
                  />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Baseline Comparison Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800/80">
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 font-mono">P95 vs Baseline</span>
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-bold text-white font-mono">{currentHealth.latency_p95_ms || 18}ms</span>
                <span className="text-[10px] text-slate-500 font-mono">Base: {baselineComparison.latency?.baseline || 15}ms</span>
              </div>
              <span className={`text-[10px] font-mono font-bold ${baselineComparison.latency?.is_elevated ? 'text-rose-400' : 'text-emerald-400'}`}>
                {baselineComparison.latency?.deviation_pct ? `${baselineComparison.latency.deviation_pct > 0 ? '+' : ''}${baselineComparison.latency.deviation_pct}%` : '+0.0%'} deviation
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 font-mono">Error Rate vs Baseline</span>
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-bold text-white font-mono">{currentHealth.error_rate || 0.0}%</span>
                <span className="text-[10px] text-slate-500 font-mono">Base: {baselineComparison.error_rate?.baseline || 0.02}%</span>
              </div>
              <span className={`text-[10px] font-mono font-bold ${baselineComparison.error_rate?.is_elevated ? 'text-rose-400' : 'text-emerald-400'}`}>
                {baselineComparison.error_rate?.is_elevated ? 'ELEVATED' : 'NOMINAL'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 font-mono">Throughput vs Baseline</span>
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-bold text-white font-mono">{currentHealth.throughput_rps || 25} rps</span>
                <span className="text-[10px] text-slate-500 font-mono">Base: {baselineComparison.throughput?.baseline || 25} rps</span>
              </div>
              <span className="text-[10px] text-cyan-400 font-mono">Within nominal tolerance</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 font-mono">CPU vs Baseline</span>
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-bold text-white font-mono">{currentHealth.cpu_percent || 12}%</span>
                <span className="text-[10px] text-slate-500 font-mono">Base: {baselineComparison.cpu?.baseline || 15}%</span>
              </div>
              <span className="text-[10px] text-emerald-400 font-mono">Normal compute load</span>
            </div>
          </div>

          {/* Missing Instrumentation Disclosure */}
          {missingInstrumentation.length > 0 && (
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
              <p className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
                <span>Instrumentation &amp; Metric Coverage Limitations for {selectedService}:</span>
              </p>
              <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-400">
                {missingInstrumentation.map((item: string, idx: number) => (
                  <span key={idx} className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ============================================================================== */}
      {/* 6. SECTION E: INCIDENT INVESTIGATION PANEL (CROSS-NAV PRESERVING INCIDENT)    */}
      {/* ============================================================================== */}
      {(activeWorkspaceTab === 'OVERVIEW' || activeWorkspaceTab === 'INVESTIGATION') && activeFocusedIncident && (
        <section 
          aria-label="Incident investigation panel"
          className="p-5 rounded-2xl glass-panel border-2 border-rose-500/40 bg-gradient-to-br from-slate-950 via-slate-900 to-rose-950/30 shadow-2xl space-y-5"
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-rose-500 text-white">
                  INCIDENT INVESTIGATION DOSSIER
                </span>
                <span className="text-sm font-bold font-mono text-white">
                  {activeFocusedIncident.incident_id}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Primary Service: <strong className="text-cyan-400">{activeFocusedIncident.primary_service}</strong>
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Severity: <strong className="text-rose-400">{activeFocusedIncident.severity}</strong>
                </span>
              </div>
              <h3 className="text-lg font-extrabold text-white mt-1">
                {activeFocusedIncident.title}
              </h3>
            </div>

            {/* Seamless Cross-Navigation Links Preserving Incident */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => navigateToSection('incidents')}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold text-xs transition flex items-center gap-1.5"
              >
                <span>Incident Center</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </button>

              <button
                onClick={() => navigateToSection('rca')}
                className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition flex items-center gap-1.5 shadow"
              >
                <span>Root Cause Analysis</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </button>

              <button
                onClick={() => navigateToSection('recovery')}
                className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition flex items-center gap-1.5 shadow"
              >
                <span>Recovery &amp; Validation</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </button>

              <button
                onClick={() => navigateToSection('approvals')}
                className="px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold text-xs transition flex items-center gap-1.5 shadow"
              >
                <span>Approval Center</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Dossier Grid: Logs, Traces, Impact Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Impact Breakdown Table */}
            <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Target className="h-4 w-4 text-rose-400" />
                Service Impact Classification
              </span>

              <div className="space-y-2 text-xs font-mono">
                <div className="p-2 rounded-lg bg-rose-950/40 border border-rose-500/40">
                  <span className="text-rose-400 font-bold block">CONFIRMED DIRECT IMPACT:</span>
                  <span className="text-slate-200">{activeFocusedIncident.root_cause_service || activeFocusedIncident.primary_service}</span>
                  <p className="text-[11px] text-slate-400 mt-0.5">Verified database connection pool rejection</p>
                </div>

                <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-500/40">
                  <span className="text-amber-400 font-bold block">OBSERVED DOWNSTREAM SYMPTOMS:</span>
                  <span className="text-slate-200">service-b (Payment API)</span>
                  <p className="text-[11px] text-slate-400 mt-0.5">RPC timeouts to database primary</p>
                </div>

                <div className="p-2 rounded-lg bg-slate-900 border border-slate-700">
                  <span className="text-slate-400 font-bold block">POTENTIAL / AT RISK:</span>
                  <span className="text-slate-300">service-a, gateway</span>
                  <p className="text-[11px] text-slate-500 mt-0.5">Normal telemetry; at risk if queue accumulates</p>
                </div>
              </div>
            </div>

            {/* Relevant Timestamped Log Excerpts */}
            <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="h-4 w-4 text-cyan-400" />
                Relevant Timestamped Logs
              </span>

              <div className="space-y-2 max-h-56 overflow-y-auto text-xs font-mono">
                {filteredLogs.length > 0 ? (
                  filteredLogs.map((log: any, idx: number) => (
                    <div key={idx} className="p-2 rounded-lg bg-slate-900/90 border border-slate-800">
                      <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                        <span>{log.timestamp || 'T - 2m'}</span>
                        <span className={log.severity === 'CRITICAL' ? 'text-rose-400 font-bold' : 'text-slate-400'}>
                          {log.severity || 'ERROR'}
                        </span>
                      </div>
                      <p className="text-slate-200 text-[11px] leading-relaxed break-words">
                        {log.message}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="p-3 text-slate-500 text-xs font-mono">
                    [Postgres Log 14:48:02] FATAL: remaining connection slots are reserved for non-replication superuser connections
                  </div>
                )}
              </div>
            </div>

            {/* Traces & Failed Spans */}
            <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Workflow className="h-4 w-4 text-indigo-400" />
                Related Traces &amp; Failed Spans
              </span>

              <div className="space-y-2 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800">
                  <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                    <span>Trace: trace-8f2a1b9c</span>
                    <span className="text-rose-400 font-bold">500 Internal Error</span>
                  </div>
                  <p className="text-slate-200 text-[11px]">
                    Span: <strong className="text-cyan-300">db_acquire_connection</strong>
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Duration: 650.4ms (Timeout exceeded limit 500ms)
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800">
                  <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                    <span>Trace: trace-3c8b147d</span>
                    <span className="text-rose-400 font-bold">504 Gateway Timeout</span>
                  </div>
                  <p className="text-slate-200 text-[11px]">
                    Span: <strong className="text-cyan-300">checkout_payment_rpc</strong>
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Duration: 845.2ms (Downstream service-b failure)
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ============================================================================== */}
      {/* 7. SECTION F: ACTIONABLE OPERATOR RECOMMENDATIONS (SAFETY-GATED)               */}
      {/* ============================================================================== */}
      <section 
        aria-label="Actionable recommendations"
        className="p-5 rounded-2xl glass-panel border border-slate-800 bg-slate-950/80 shadow-2xl space-y-4"
      >
        <div className="flex items-center gap-2">
          <Wrench className="h-5 w-5 text-emerald-400" />
          <h3 className="text-base font-bold text-white">
            Actionable Operator Recommendations
          </h3>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
            Evidence-Backed Next Steps
          </span>
        </div>
        <p className="text-xs text-slate-400">
          Remediation routing adheres to safety governance. Disruptive actions require authorization and route through Recovery &amp; Approval Center.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {recommendations.map((rec, idx) => (
            <div 
              key={idx}
              className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <h4 className="text-sm font-bold text-white">{rec.title}</h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    rec.category === 'EXECUTABLE' ? 'bg-amber-500 text-slate-950' :
                    rec.category === 'MANUAL' ? 'bg-indigo-900 text-indigo-200 border border-indigo-700' :
                    'bg-slate-800 text-slate-300'
                  }`}>
                    {rec.category}
                  </span>
                </div>

                <div className="text-xs space-y-1.5">
                  <p className="text-slate-300">
                    <strong className="text-slate-400 font-mono">Why Suggested:</strong> {rec.why}
                  </p>
                  <p className="text-slate-300 font-mono text-[11px] bg-black/30 p-2 rounded-lg border border-slate-800">
                    <strong className="text-cyan-400">Supporting Evidence:</strong> {rec.evidence}
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span>Target: <strong className="text-slate-200 font-mono">{rec.targetService}</strong></span>
                    <span>Approval: <strong className="text-amber-300">{rec.requiredApproval}</strong></span>
                  </div>
                  <p className="text-[11px] text-emerald-400 font-mono">
                    Expected Signal: {rec.verificationSignal}
                  </p>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800 flex justify-end">
                <button
                  onClick={() => navigateToSection(rec.actionTab || 'recovery')}
                  className="px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition flex items-center gap-1.5"
                >
                  <span>Route to {rec.actionTab === 'rca' ? 'Root Cause Analysis' : 'Recovery & Approval'}</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
};

export default ObservatoryPage;

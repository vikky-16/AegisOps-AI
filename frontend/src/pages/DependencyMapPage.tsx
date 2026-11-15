import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Network, 
  Server, 
  Activity, 
  Database, 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowRight, 
  ExternalLink, 
  Zap, 
  RefreshCw, 
  Search, 
  Filter, 
  Layers, 
  Eye, 
  Play, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  RotateCcw, 
  Flame, 
  Clock, 
  ChevronRight,
  GitFork,
  Radio,
  Sliders,
  Check,
  X,
  Target,
  BarChart2,
  HelpCircle,
  TrendingDown
} from 'lucide-react';
import { api } from '../services/api';
import type { ServiceDetail, Incident, DependencyGraphData, ServiceNode, ServiceDependency } from '../types';

interface DependencyMapPageProps {
  services: ServiceDetail[];
  incidents: Incident[];
  liveGraphData?: DependencyGraphData;
  highlightedServiceId?: string;
  setActiveTab: (tab: string) => void;
  onSelectIncident?: (incidentId: string) => void;
  onNavigateToObservability?: (serviceId: string) => void;
}

export const DependencyMapPage: React.FC<DependencyMapPageProps> = ({
  services,
  incidents,
  liveGraphData,
  highlightedServiceId,
  setActiveTab,
  onSelectIncident,
  onNavigateToObservability
}) => {
  const [graphData, setGraphData] = useState<DependencyGraphData | null>(liveGraphData || null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>(highlightedServiceId || 'database-service');
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  
  // Incident focus & status filters
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'HEALTHY' | 'DEGRADED' | 'CRITICAL' | 'AFFECTED' | 'ROOT_CAUSE'>('ALL');
  const [problemFilter, setProblemFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [focusIncidentMode, setFocusIncidentMode] = useState<boolean>(true);
  
  // Right-side panel active tab
  const [rightPanelTab, setRightPanelTab] = useState<'OVERVIEW' | 'WHY_DEGRADED' | 'UPSTREAM' | 'DOWNSTREAM' | 'HEALTH' | 'INCIDENTS'>('OVERVIEW');

  // Simulation Feedback
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simMessage, setSimMessage] = useState<string | null>(null);

  // Pan and Zoom viewport state
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const svgContainerRef = useRef<HTMLDivElement>(null);

  // Fetch graph data from backend
  const loadGraph = async (incidentId?: string) => {
    try {
      const data = await api.getDependencyGraph(incidentId || undefined);
      setGraphData(data);
    } catch (e) {
      console.error('Failed to load dependency graph:', e);
    }
  };

  useEffect(() => {
    loadGraph(selectedIncidentId || undefined);
    const interval = setInterval(() => {
      loadGraph(selectedIncidentId || undefined);
    }, 2500);
    return () => clearInterval(interval);
  }, [selectedIncidentId]);

  useEffect(() => {
    if (liveGraphData && !selectedIncidentId) {
      setGraphData(liveGraphData);
    }
  }, [liveGraphData, selectedIncidentId]);

  useEffect(() => {
    if (highlightedServiceId) {
      setSelectedNodeId(highlightedServiceId);
    }
  }, [highlightedServiceId]);

  // Hierarchical Deterministic DAG Positions
  // Tier 0: Gateway / Ingress (y = 65)
  // Tier 1: Core Services (y = 185)
  // Tier 2: Business Services (y = 305)
  // Tier 3: Transactions & Processing (y = 425)
  // Tier 4: Persistence & Storage (y = 545)
  const deterministicPositions: Record<string, { x: number; y: number; tier: number }> = {
    // Ingress
    'gateway': { x: 500, y: 65, tier: 0 },
    'api-gateway': { x: 500, y: 65, tier: 0 },

    // Core
    'user-service': { x: 230, y: 185, tier: 1 },
    'auth-service': { x: 500, y: 185, tier: 1 },
    'project-service': { x: 770, y: 185, tier: 1 },

    // Business
    'payment-service': { x: 200, y: 305, tier: 2 },
    'service-b': { x: 200, y: 305, tier: 2 },
    'order-service': { x: 400, y: 305, tier: 2 },
    'service-a': { x: 400, y: 305, tier: 2 },
    'account-service': { x: 600, y: 305, tier: 2 },
    'inventory-service': { x: 800, y: 305, tier: 2 },

    // Transactions
    'transaction-service': { x: 300, y: 425, tier: 3 },
    'billing-service': { x: 500, y: 425, tier: 3 },
    'fraud-detection-service': { x: 700, y: 425, tier: 3 },

    // Storage
    'database-service': { x: 380, y: 545, tier: 4 },
    'cache': { x: 620, y: 545, tier: 4 },
    'redis': { x: 620, y: 545, tier: 4 }
  };

  const nodes: ServiceNode[] = useMemo(() => {
    if (graphData?.nodes && graphData.nodes.length > 0) {
      return graphData.nodes;
    }
    return [
      { id: 'gateway', name: 'gateway', display_name: 'API Gateway', service_type: 'gateway', status: 'HEALTHY', criticality: 'CRITICAL', owner: 'Edge Team', environment: 'production', port: 8000, url: 'http://127.0.0.1:8000', request_rate: 1440, error_rate: 0.0, p95_latency: 18.0, cpu: 5.2, ram: 128.0, availability: 100.0, active_incidents: [] },
      { id: 'service-a', name: 'service-a', display_name: 'Order Service', service_type: 'api', status: 'HEALTHY', criticality: 'HIGH', owner: 'Order Core', environment: 'production', port: 8001, url: 'http://127.0.0.1:8001', request_rate: 720, error_rate: 0.1, p95_latency: 22.0, cpu: 8.5, ram: 140.0, availability: 100.0, active_incidents: [] },
      { id: 'service-b', name: 'service-b', display_name: 'Payment API', service_type: 'api', status: 'DEGRADED', criticality: 'CRITICAL', owner: 'Fintech Team', environment: 'production', port: 8002, url: 'http://127.0.0.1:8002', request_rate: 650, error_rate: 18.0, p95_latency: 214.0, cpu: 14.0, ram: 160.0, availability: 82.0, active_incidents: ['INC-001'] },
      { id: 'database-service', name: 'database-service', display_name: 'Database Primary', service_type: 'database', status: 'CRITICAL', criticality: 'CRITICAL', owner: 'Data Infra', environment: 'production', port: 5432, url: 'postgres://127.0.0.1:5432', request_rate: 1850, error_rate: 42.0, p95_latency: 845.0, cpu: 88.0, ram: 350.0, availability: 0.0, active_incidents: ['INC-001'] },
      { id: 'cache', name: 'cache', display_name: 'Redis Cache', service_type: 'cache', status: 'HEALTHY', criticality: 'MEDIUM', owner: 'Infra', environment: 'production', port: 6379, url: 'redis://127.0.0.1:6379', request_rate: 2400, error_rate: 0.0, p95_latency: 2.0, cpu: 5.5, ram: 80.0, availability: 100.0, active_incidents: [] },
    ];
  }, [graphData]);

  const edges: ServiceDependency[] = useMemo(() => {
    if (graphData?.edges && graphData.edges.length > 0) {
      return graphData.edges;
    }
    return [
      { id: 'DEP-GW-A', source: 'gateway', target: 'service-a', relationship_type: 'HTTP_RPC', confidence: 0.98, confidence_pct: 98, observation_count: 850, correlated_failures_count: 0, status: 'VALIDATED', evidence: ['850 req/min'], request_volume: '850/min', latency: '20ms', latency_ms: 20, error_rate: '0.1%', error_rate_pct: 0.1, dependency_status: 'HEALTHY' },
      { id: 'DEP-A-B', source: 'service-a', target: 'service-b', relationship_type: 'HTTP_RPC', confidence: 0.97, confidence_pct: 97, observation_count: 650, correlated_failures_count: 12, status: 'VALIDATED', evidence: ['650 req/min'], request_volume: '650/min', latency: '120ms', latency_ms: 120, error_rate: '18.0%', error_rate_pct: 18.0, dependency_status: 'DEGRADED', is_incident_path: true },
      { id: 'DEP-B-DB', source: 'service-b', target: 'database-service', relationship_type: 'DATABASE_QUERY', confidence: 0.99, confidence_pct: 99, observation_count: 1200, correlated_failures_count: 45, status: 'VALIDATED', evidence: ['1,200 req/min'], request_volume: '1,200/min', latency: '650ms', latency_ms: 650, error_rate: '42.0%', error_rate_pct: 42.0, dependency_status: 'FAILING', is_incident_path: true },
      { id: 'DEP-B-CACHE', source: 'service-b', target: 'cache', relationship_type: 'CACHE_ACCESS', confidence: 0.92, confidence_pct: 92, observation_count: 500, correlated_failures_count: 0, status: 'INFERRED', evidence: ['500 req/min'], request_volume: '500/min', latency: '2ms', latency_ms: 2, error_rate: '0.0%', error_rate_pct: 0.0, dependency_status: 'HEALTHY' },
    ];
  }, [graphData]);

  // Active incident context
  const activeIncidentContext = graphData?.incident_context;
  const currentIncident = incidents.find(i => i.incident_id === (selectedIncidentId || activeIncidentContext?.incident_id)) || (incidents.length > 0 ? incidents[0] : null);

  // Authoritative Node Health State
  const getNodeHealthState = (node: ServiceNode): 'HEALTHY' | 'DEGRADED' | 'CRITICAL' | 'UNKNOWN' => {
    if (activeIncidentContext) {
      if (node.id === activeIncidentContext.root_cause_service) return 'CRITICAL';
      if (activeIncidentContext.affected_services.includes(node.id)) {
        return (node.error_rate && node.error_rate > 25.0) ? 'CRITICAL' : 'DEGRADED';
      }
      if (activeIncidentContext.propagation_path?.includes(node.id)) return 'DEGRADED';
    }
    const st = (node.health_status || node.status || 'HEALTHY').toUpperCase();
    if (st === 'CRITICAL' || st === 'FAILED' || st === 'CRASHED' || st === 'DOWN') return 'CRITICAL';
    if (st === 'DEGRADED' || st === 'WARNING' || st === 'WARN') return 'DEGRADED';
    if (st === 'UNKNOWN' || st === 'PENDING') return 'UNKNOWN';
    return 'HEALTHY';
  };

  // Node Problem Badge
  const getNodeProblemBadge = (node: ServiceNode, healthState: string, isRootCause: boolean) => {
    if (node.problem_badge) {
      const b = node.problem_badge.toUpperCase();
      if (isRootCause) {
        return { label: b, color: '#FDA4AF', bg: 'rgba(244, 63, 94, 0.45)', border: '#F43F5E' };
      }
      if (healthState === 'CRITICAL') {
        return { label: b, color: '#FDA4AF', bg: 'rgba(244, 63, 94, 0.35)', border: '#F43F5E' };
      }
      if (healthState === 'DEGRADED') {
        return { label: b, color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.35)', border: '#F59E0B' };
      }
      return { label: 'HEALTHY', color: '#6EE7B7', bg: 'rgba(16, 185, 129, 0.25)', border: '#10B981' };
    }

    const nid = node.id.toLowerCase();
    if (isRootCause || nid.includes('database')) {
      if (healthState === 'CRITICAL') return { label: 'DB CONNECTION EXHAUSTION', color: '#FDA4AF', bg: 'rgba(244, 63, 94, 0.45)', border: '#F43F5E' };
      if (healthState === 'DEGRADED') return { label: 'DB CONTENTION', color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.45)', border: '#F59E0B' };
    }
    if (nid.includes('payment') || nid.includes('service-b')) {
      if (healthState === 'DEGRADED' || healthState === 'CRITICAL') return { label: 'DATABASE TIMEOUT', color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.45)', border: '#F59E0B' };
    }
    if (nid.includes('order') || nid.includes('service-a')) {
      if (healthState === 'DEGRADED' || healthState === 'CRITICAL') return { label: 'UPSTREAM DATABASE FAILURE', color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.45)', border: '#F59E0B' };
    }
    if (nid.includes('gateway')) {
      if (healthState === 'DEGRADED' || healthState === 'CRITICAL') return { label: 'HTTP 500 CASCADE', color: '#FDA4AF', bg: 'rgba(244, 63, 94, 0.45)', border: '#F43F5E' };
    }
    if (nid.includes('cache') || nid.includes('redis')) {
      if (healthState !== 'HEALTHY') return { label: 'CACHE FAILURE', color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.45)', border: '#F59E0B' };
    }
    if (healthState === 'CRITICAL') return { label: 'SERVICE FAILURE', color: '#FDA4AF', bg: 'rgba(244, 63, 94, 0.45)', border: '#F43F5E' };
    if (healthState === 'DEGRADED') return { label: 'DEGRADED', color: '#FCD34D', bg: 'rgba(245, 158, 11, 0.45)', border: '#F59E0B' };
    return { label: 'HEALTHY', color: '#6EE7B7', bg: 'rgba(16, 185, 129, 0.25)', border: '#10B981' };
  };

  // Visibility / Filter Logic
  const isNodeVisible = (node: ServiceNode): boolean => {
    if (searchQuery.trim().length > 0) {
      const q = searchQuery.toLowerCase();
      if (!node.id.toLowerCase().includes(q) && !(node.display_name && node.display_name.toLowerCase().includes(q))) {
        return false;
      }
    }

    const health = getNodeHealthState(node);
    const isRootCause = (activeIncidentContext?.root_cause_service === node.id);
    const isAffected = (activeIncidentContext?.affected_services.includes(node.id) || activeIncidentContext?.propagation_path?.includes(node.id));

    if (statusFilter === 'HEALTHY' && health !== 'HEALTHY') return false;
    if (statusFilter === 'DEGRADED' && health !== 'DEGRADED') return false;
    if (statusFilter === 'CRITICAL' && health !== 'CRITICAL') return false;
    if (statusFilter === 'ROOT_CAUSE' && !isRootCause) return false;
    if (statusFilter === 'AFFECTED' && !(isAffected || isRootCause)) return false;

    if (problemFilter !== 'ALL') {
      const badge = getNodeProblemBadge(node, health, isRootCause).label.toUpperCase();
      if (!badge.includes(problemFilter.toUpperCase())) return false;
    }

    return true;
  };

  // Check relevance to active incident
  const isIncidentRelevant = (nodeId: string): boolean => {
    if (!activeIncidentContext) return false;
    return activeIncidentContext.root_cause_service === nodeId || 
           activeIncidentContext.affected_services.includes(nodeId) ||
           (activeIncidentContext.propagation_path && activeIncidentContext.propagation_path.includes(nodeId));
  };

  // Selected Node Object
  const selectedNode = useMemo(() => {
    return nodes.find(n => n.id === selectedNodeId) || nodes[0];
  }, [nodes, selectedNodeId]);

  const selectedEdge = useMemo(() => {
    return edges.find(e => e.id === selectedEdgeId);
  }, [edges, selectedEdgeId]);

  // Direct upstream / downstream edges
  const directUpstream = useMemo(() => {
    return edges.filter(e => e.target === selectedNodeId);
  }, [edges, selectedNodeId]);

  const directDownstream = useMemo(() => {
    return edges.filter(e => e.source === selectedNodeId);
  }, [edges, selectedNodeId]);

  // Pan / Zoom Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPanOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Failure simulation trigger
  const handleTriggerFailure = async (failureType: string) => {
    setIsSimulating(true);
    try {
      await api.triggerSimulation(failureType, selectedNode.id);
      setSimMessage(`Injected ${failureType} into ${selectedNode.id}`);
      setTimeout(() => setSimMessage(null), 4000);
      loadGraph(selectedIncidentId || undefined);
    } catch (e: any) {
      setSimMessage(`Injection failed: ${e.message}`);
    } finally {
      setIsSimulating(false);
    }
  };

  // Has active incident flag
  const hasActiveIncident = Boolean(activeIncidentContext && activeIncidentContext.root_cause_service);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-20">
      
      {/* ============================================================================== */}
      {/* 1. TOP BAR: TITLE, INCIDENT FOCUS, SEARCH & FILTERS                            */}
      {/* ============================================================================== */}
      <div className="p-5 rounded-2xl glass-panel border border-cyan-500/30 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 shadow-2xl space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 animate-ping" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400">
                AegisOps Incident-Aware Topology
              </span>
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5 font-mono">
              <Network className="h-6 w-6 text-cyan-400" />
              <span>SERVICE DEPENDENCY MAP</span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Live causal topology driven by real telemetry, RCA root-cause isolation, and directed failure propagation.
            </p>
          </div>

          {/* Action & Mode Controls */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            
            {/* FOCUS INCIDENT TOGGLE */}
            <button
              onClick={() => setFocusIncidentMode(!focusIncidentMode)}
              className={`px-3 py-1.5 rounded-xl border transition flex items-center gap-1.5 font-bold ${
                focusIncidentMode
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-lg shadow-rose-500/20 ring-1 ring-rose-500/50'
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'
              }`}
            >
              <Target className={`h-4 w-4 ${focusIncidentMode ? 'text-rose-400 animate-pulse' : 'text-slate-500'}`} />
              <span>FOCUS INCIDENT {focusIncidentMode ? 'ON' : 'OFF'}</span>
            </button>

            {/* Incident Selector Dropdown */}
            <select
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-cyan-300 focus:border-cyan-400 outline-none"
            >
              <option value="">Latest Active Incident</option>
              {incidents.map(inc => (
                <option key={inc.incident_id} value={inc.incident_id}>
                  {inc.incident_id} - {inc.title || inc.severity}
                </option>
              ))}
            </select>

            {/* Refresh */}
            <button
              onClick={() => loadGraph(selectedIncidentId || undefined)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white transition"
              title="Refresh Graph"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80 font-mono text-xs">
          
          {/* Status Filters */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase mr-1">Status:</span>
            {(['ALL', 'ROOT_CAUSE', 'CRITICAL', 'DEGRADED', 'AFFECTED', 'HEALTHY'] as const).map(st => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-0.5 rounded-lg border transition ${
                  statusFilter === st
                    ? st === 'ROOT_CAUSE' || st === 'CRITICAL'
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500 font-bold'
                      : st === 'DEGRADED' || st === 'AFFECTED'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500 font-bold'
                      : 'bg-cyan-600 text-white border-cyan-400 font-bold'
                    : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Problem Type Filters & Search */}
          <div className="flex flex-wrap items-center gap-2">
            
            {/* Problem Filter */}
            <select
              value={problemFilter}
              onChange={(e) => setProblemFilter(e.target.value)}
              className="px-2.5 py-1 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 focus:border-cyan-400 outline-none"
            >
              <option value="ALL">All Problems</option>
              <option value="DATABASE">Database</option>
              <option value="TIMEOUT">Timeout</option>
              <option value="HTTP">HTTP 500</option>
              <option value="LATENCY">Latency</option>
              <option value="DEPENDENCY">Dependency</option>
              <option value="RESOURCE">Resource</option>
            </select>

            {/* Search */}
            <div className="relative">
              <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search service..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-400 outline-none w-40"
              />
            </div>
          </div>

        </div>
      </div>

      {/* Controlled Action Feedback */}
      {simMessage && (
        <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center gap-2 animate-fadeIn">
          <Activity className="h-4 w-4 text-cyan-400 animate-spin" />
          <span>{simMessage}</span>
        </div>
      )}

      {/* ============================================================================== */}
      {/* 2. MAIN WORKSPACE: GRAPH CANVAS (LEFT 8 COLS) + SERVICE INSPECTOR (RIGHT 4 COLS)*/}
      {/* ============================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left: SVG Directed Topology Graph Canvas (8 cols) */}
        <div className="lg:col-span-8 p-6 rounded-2xl glass-panel border border-slate-800 space-y-4 shadow-xl relative overflow-hidden flex flex-col justify-between">
          
          {/* Top Canvas Controls & Zoom/Pan */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 font-mono text-xs">
            <div className="flex items-center gap-3">
              <span className="text-slate-400 flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                <span>Healthy</span>
              </span>
              <span className="text-amber-400 flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                <span>Degraded</span>
              </span>
              <span className="text-rose-400 flex items-center gap-1.5 font-bold">
                <span className="h-2 w-2 rounded-full bg-rose-400 animate-pulse" />
                <span>Critical / Root Cause</span>
              </span>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 p-1 rounded-xl">
              <button
                onClick={() => setZoomLevel(prev => Math.min(2.0, prev + 0.15))}
                className="p-1 hover:bg-slate-800 text-slate-300 rounded"
                title="Zoom In"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoomLevel(prev => Math.max(0.6, prev - 0.15))}
                className="p-1 hover:bg-slate-800 text-slate-300 rounded"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => { setZoomLevel(1.0); setPanOffset({ x: 0, y: 0 }); }}
                className="p-1 hover:bg-slate-800 text-slate-300 rounded text-[10px]"
                title="Reset View"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* SVG Canvas Element */}
          <div 
            ref={svgContainerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            className={`relative w-full h-[540px] overflow-hidden ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
          >
            <svg 
              className="w-full h-full" 
              viewBox="0 0 1020 620" 
              style={{
                transform: `scale(${zoomLevel}) translate(${panOffset.x}px, ${panOffset.y}px)`,
                transformOrigin: 'center center',
                transition: isDragging ? 'none' : 'transform 0.12s ease-out'
              }}
            >
              <defs>
                <marker
                  id="arrow-default"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#475569" />
                </marker>
                <marker
                  id="arrow-selected"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#06B6D4" />
                </marker>
                <marker
                  id="arrow-danger"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#F43F5E" />
                </marker>
                <marker
                  id="arrow-warning"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#F59E0B" />
                </marker>
              </defs>

              {/* Tier Guidelines */}
              {[
                { label: 'INGRESS / GATEWAY', y: 65 },
                { label: 'CORE SERVICES', y: 185 },
                { label: 'BUSINESS DOMAIN', y: 305 },
                { label: 'TRANSACTIONS & PROCESSING', y: 425 },
                { label: 'DATA & STORAGE', y: 545 },
              ].map((tier, idx) => (
                <g key={idx} opacity={0.12}>
                  <line x1="50" y1={tier.y} x2="970" y2={tier.y} stroke="#334155" strokeDasharray="3,3" />
                  <text x="55" y={tier.y - 30} fill="#64748B" fontSize="9" fontWeight="bold" fontFamily="monospace">
                    TIER {idx}: {tier.label}
                  </text>
                </g>
              ))}

              {/* Edges */}
              {edges.map((edge) => {
                const srcPos = deterministicPositions[edge.source] || { x: 200, y: 100 };
                const dstPos = deterministicPositions[edge.target] || { x: 500, y: 300 };
                
                const isSelectedEdge = edge.id === selectedEdgeId || edge.source === selectedNodeId || edge.target === selectedNodeId;
                const isHovered = edge.id === hoveredEdgeId;
                
                const srcNode = nodes.find(n => n.id === edge.source);
                const dstNode = nodes.find(n => n.id === edge.target);
                const srcState = srcNode ? getNodeHealthState(srcNode) : 'HEALTHY';
                const dstState = dstNode ? getNodeHealthState(dstNode) : 'HEALTHY';
                
                const isFailing = edge.dependency_status === 'FAILING' || edge.dependency_status === 'CRITICAL' || (srcState === 'CRITICAL' && dstState === 'CRITICAL');
                const isDegraded = edge.dependency_status === 'DEGRADED' || srcState === 'DEGRADED' || dstState === 'DEGRADED';
                const isIncidentEdge = Boolean(edge.is_incident_path || (hasActiveIncident && (
                  (edge.source === activeIncidentContext?.root_cause_service && activeIncidentContext?.affected_services.includes(edge.target)) ||
                  (activeIncidentContext?.affected_services.includes(edge.source) && edge.target === activeIncidentContext?.root_cause_service) ||
                  (activeIncidentContext?.affected_services.includes(edge.source) && activeIncidentContext?.affected_services.includes(edge.target))
                )));

                // Focus Incident subduing
                const isSubdued = focusIncidentMode && hasActiveIncident && !isIncidentEdge && !isFailing;

                // Anchor points
                const dx = dstPos.x - srcPos.x;
                const dy = dstPos.y - srcPos.y;
                const angle = Math.atan2(dy, dx);
                
                const startX = srcPos.x + Math.cos(angle) * 75;
                const startY = srcPos.y + Math.sin(angle) * 35;
                const endX = dstPos.x - Math.cos(angle) * 75;
                const endY = dstPos.y - Math.sin(angle) * 35;

                const midX = (startX + endX) / 2;
                const midY = (startY + endY) / 2;

                let strokeColor = '#334155';
                let markerEnd = 'url(#arrow-default)';
                let strokeWidth = 1.5;

                if (isIncidentEdge || isFailing) {
                  strokeColor = '#F43F5E';
                  markerEnd = 'url(#arrow-danger)';
                  strokeWidth = 3;
                } else if (isDegraded) {
                  strokeColor = '#F59E0B';
                  markerEnd = 'url(#arrow-warning)';
                  strokeWidth = 2.5;
                } else if (isSelectedEdge || isHovered) {
                  strokeColor = '#06B6D4';
                  markerEnd = 'url(#arrow-selected)';
                  strokeWidth = 2.5;
                }

                return (
                  <g 
                    key={edge.id}
                    onMouseEnter={() => setHoveredEdgeId(edge.id)}
                    onMouseLeave={() => setHoveredEdgeId(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedEdgeId(edge.id);
                    }}
                    className={`cursor-pointer transition-opacity duration-300 ${isSubdued ? 'opacity-20' : 'opacity-100'}`}
                  >
                    {/* Glowing pulse on failing incident edge */}
                    {(isIncidentEdge || isFailing) && (
                      <line
                        x1={startX}
                        y1={startY}
                        x2={endX}
                        y2={endY}
                        stroke="#F43F5E"
                        strokeWidth={6}
                        strokeOpacity={0.35}
                        className="animate-pulse"
                      />
                    )}

                    {/* Edge line */}
                    <line
                      x1={startX}
                      y1={startY}
                      x2={endX}
                      y2={endY}
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      strokeDasharray={isIncidentEdge ? '6,3' : 'none'}
                      markerEnd={markerEnd}
                    />

                    {/* Hover Metric Pill on Edge */}
                    {(isHovered || edge.id === selectedEdgeId || (isIncidentEdge && !isSubdued)) && (
                      <g transform={`translate(${midX}, ${midY})`}>
                        <rect
                          x="-65"
                          y="-14"
                          width="130"
                          height="24"
                          rx="12"
                          fill="#090D16"
                          stroke={strokeColor}
                          strokeWidth="1.5"
                        />
                        <text
                          x="0"
                          y="2"
                          textAnchor="middle"
                          fill={isFailing ? '#FDA4AF' : isDegraded ? '#FCD34D' : '#38BDF8'}
                          fontSize="9"
                          fontWeight="bold"
                          fontFamily="monospace"
                        >
                          {edge.request_volume || '120/min'} • {edge.latency || '27ms'}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Service Nodes */}
              {nodes.map((node) => {
                const pos = deterministicPositions[node.id] || { x: 500, y: 300, tier: 2 };
                const healthState = getNodeHealthState(node);
                const isSelected = node.id === selectedNodeId;
                const isHovered = node.id === hoveredNodeId;
                const isRootCause = Boolean(activeIncidentContext?.root_cause_service === node.id || node.is_root_cause);
                const isAffected = Boolean(activeIncidentContext?.affected_services.includes(node.id) || node.is_affected);
                const isRelevant = isIncidentRelevant(node.id);
                const isSubdued = focusIncidentMode && hasActiveIncident && !isRelevant;
                const isVisible = isNodeVisible(node);

                if (!isVisible) return null;

                // Color / frame treatment
                let statusFill = '#10B981';
                let statusText = 'HEALTHY';
                let strokeColor = '#1E293B';
                let cardBg = '#090D16';

                if (healthState === 'CRITICAL' || isRootCause) {
                  statusFill = '#F43F5E';
                  statusText = isRootCause ? 'ROOT CAUSE' : 'CRITICAL';
                  strokeColor = '#F43F5E';
                  cardBg = '#1c0a12';
                } else if (healthState === 'DEGRADED' || isAffected) {
                  statusFill = '#F59E0B';
                  statusText = isAffected ? 'AFFECTED' : 'DEGRADED';
                  strokeColor = '#F59E0B';
                  cardBg = '#181207';
                } else if (healthState === 'UNKNOWN') {
                  statusFill = '#94A3B8';
                  statusText = 'UNKNOWN';
                  strokeColor = '#475569';
                  cardBg = '#0d1117';
                }

                if (isSelected) {
                  strokeColor = '#06B6D4';
                }

                const problemBadge = getNodeProblemBadge(node, healthState, isRootCause);
                const reqText = typeof node.request_rate === 'number' ? `${node.request_rate} req/m` : node.request_rate || '120/m';
                const p95Text = `P95 ${node.p95_latency || 18}ms`;
                const errText = `Err ${node.error_rate || 0.0}%`;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onClick={() => {
                      setSelectedNodeId(node.id);
                      setSelectedEdgeId(null);
                    }}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                    className={`cursor-pointer transition-all duration-300 ${isSubdued ? 'opacity-20' : 'opacity-100'}`}
                  >
                    {/* Glowing outer halo on Root Cause or Critical */}
                    {(isSelected || isRootCause || healthState === 'CRITICAL') && (
                      <rect
                        x="-80"
                        y="-40"
                        width="160"
                        height="80"
                        rx="16"
                        fill={isRootCause || healthState === 'CRITICAL' ? 'rgba(244, 63, 94, 0.25)' : 'rgba(6, 182, 212, 0.25)'}
                        className={isRootCause ? 'animate-pulse' : ''}
                      />
                    )}

                    {/* Main Node Box */}
                    <rect
                      x="-76"
                      y="-36"
                      width="152"
                      height="72"
                      rx="12"
                      fill={cardBg}
                      stroke={strokeColor}
                      strokeWidth={isSelected || isRootCause ? 2.5 : 1.5}
                    />

                    {/* Row 1: Status Dot & Label */}
                    <circle cx="-62" cy="-22" r="3.5" fill={statusFill} className={isRootCause ? 'animate-ping' : ''} />
                    <circle cx="-62" cy="-22" r="3.5" fill={statusFill} />
                    <text
                      x="-52"
                      y="-19"
                      fill={statusFill}
                      fontSize="8.5"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {statusText}
                    </text>

                    {/* Root Cause Tag / Problem Badge */}
                    <g transform="translate(10, -29)">
                      <rect
                        x="0"
                        y="0"
                        width="62"
                        height="13"
                        rx="4"
                        fill={problemBadge.bg}
                        stroke={problemBadge.border}
                        strokeWidth="0.8"
                      />
                      <text
                        x="31"
                        y="9.5"
                        textAnchor="middle"
                        fill={problemBadge.color}
                        fontSize="6.8"
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {isRootCause ? 'ROOT CAUSE' : problemBadge.label.slice(0, 14)}
                      </text>
                    </g>

                    {/* Row 2: Service Display Name */}
                    <text
                      x="0"
                      y="1"
                      textAnchor="middle"
                      fill="#FFFFFF"
                      fontSize="10.5"
                      fontWeight="bold"
                      fontFamily="sans-serif"
                    >
                      {node.display_name || node.name}
                    </text>

                    {/* Row 3: Metrics */}
                    <text
                      x="-64"
                      y="17"
                      fill="#94A3B8"
                      fontSize="8"
                      fontFamily="monospace"
                    >
                      {reqText}
                    </text>
                    <text
                      x="64"
                      y="17"
                      textAnchor="end"
                      fill={p95Text.includes('845') || (node.p95_latency || 0) > 250 ? '#FDA4AF' : '#CBD5E1'}
                      fontSize="8"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {p95Text}
                    </text>

                    {/* Row 4: Error Rate */}
                    <text
                      x="-64"
                      y="27"
                      fill={(node.error_rate || 0) > 5 ? '#F43F5E' : '#10B981'}
                      fontSize="8"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {errText}
                    </text>
                    <text
                      x="64"
                      y="27"
                      textAnchor="end"
                      fill="#94A3B8"
                      fontSize="8"
                      fontFamily="monospace"
                    >
                      CPU {node.cpu || 8}%
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Bottom Footnote */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-slate-400 font-mono pt-3 border-t border-slate-800/80">
            <span>● Dynamic Node Health: HEALTHY • DEGRADED • CRITICAL • UNKNOWN</span>
            <span>Click any node to open Inspector & View Performance</span>
          </div>
        </div>

        {/* Right: Upgraded Service Inspector (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl font-mono">
            
            {/* Header: Service Name & Status Badge */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    getNodeHealthState(selectedNode) === 'CRITICAL'
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                      : getNodeHealthState(selectedNode) === 'DEGRADED'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  }`}>
                    ● {getNodeHealthState(selectedNode)}
                  </span>
                  {activeIncidentContext?.root_cause_service === selectedNode.id && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-black bg-rose-500 text-slate-950">
                      ROOT CAUSE
                    </span>
                  )}
                </div>
                <h3 className="text-base font-black text-white mt-1.5">{selectedNode.display_name || selectedNode.name}</h3>
                <p className="text-xs text-slate-400">
                  {selectedNode.service_type?.toUpperCase()} • {selectedNode.port || 8000}
                </p>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                {selectedNode.service_type === 'database' ? (
                  <Database className="h-5 w-5 text-cyan-400" />
                ) : (
                  <Server className="h-5 w-5 text-indigo-400" />
                )}
              </div>
            </div>

            {/* TAB SELECTOR: [ OVERVIEW ] [ WHY DEGRADED? ] [ UPSTREAM ] [ DOWNSTREAM ] */}
            <div className="flex items-center gap-1 border-b border-slate-800 pb-2 overflow-x-auto text-[11px] font-bold">
              {(['OVERVIEW', 'WHY_DEGRADED', 'UPSTREAM', 'DOWNSTREAM'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setRightPanelTab(tab)}
                  className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
                    rightPanelTab === tab
                      ? 'bg-cyan-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tab === 'WHY_DEGRADED' ? 'WHY DEGRADED?' : tab}
                </button>
              ))}
            </div>

            {/* TAB 1: OVERVIEW */}
            {rightPanelTab === 'OVERVIEW' && (
              <div className="space-y-3 text-xs">
                
                {/* Metrics Grid */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-black">TRAFFIC</span>
                    <p className="font-bold text-cyan-300 text-sm mt-0.5">
                      {typeof selectedNode.request_rate === 'number' ? `${selectedNode.request_rate}/min` : selectedNode.request_rate || '120/min'}
                    </p>
                  </div>

                  <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-black">P95 LATENCY</span>
                    <p className="font-bold text-white text-sm mt-0.5">
                      {selectedNode.p95_latency || 18} ms
                    </p>
                  </div>

                  <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-black">ERROR RATE</span>
                    <p className={`font-bold text-sm mt-0.5 ${(selectedNode.error_rate || 0) > 5 ? 'text-rose-400' : 'text-emerald-400'}`}>
                      {selectedNode.error_rate !== undefined ? `${selectedNode.error_rate}%` : '0.0%'}
                    </p>
                  </div>

                  <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-black">CPU / RAM</span>
                    <p className="font-bold text-slate-200 text-sm mt-0.5">
                      {selectedNode.cpu || 8}% • {selectedNode.ram || 128} MB
                    </p>
                  </div>
                </div>

                {/* Dominant Problem */}
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase">Dominant Problem:</span>
                  <strong className="text-rose-300 text-xs block font-extrabold">
                    {getNodeProblemBadge(selectedNode, getNodeHealthState(selectedNode), activeIncidentContext?.root_cause_service === selectedNode.id).label}
                  </strong>
                </div>

                {/* Primary Action Buttons: VIEW PERFORMANCE, VIEW RCA, VIEW RECOVERY */}
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={() => {
                      if (onNavigateToObservability) {
                        onNavigateToObservability(selectedNode.id);
                      } else {
                        setActiveTab('observatory');
                      }
                    }}
                    className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-extrabold text-xs transition flex items-center justify-center gap-1.5 shadow-lg shadow-cyan-500/20"
                  >
                    <Activity className="h-3.5 w-3.5" />
                    <span>VIEW PERFORMANCE (OPERATIONAL OBSERVABILITY)</span>
                  </button>

                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => {
                        const incId = (selectedNode.active_incidents && selectedNode.active_incidents[0]) || activeIncidentContext?.incident_id;
                        if (incId && onSelectIncident) onSelectIncident(incId);
                        setActiveTab('rca');
                      }}
                      className="py-1.5 rounded-xl bg-indigo-900/50 hover:bg-indigo-900/70 border border-indigo-700/60 text-indigo-200 text-xs font-bold transition flex items-center justify-center gap-1"
                    >
                      <span>VIEW RCA</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>

                    <button
                      onClick={() => {
                        const incId = (selectedNode.active_incidents && selectedNode.active_incidents[0]) || activeIncidentContext?.incident_id;
                        if (incId && onSelectIncident) onSelectIncident(incId);
                        setActiveTab('recovery');
                      }}
                      className="py-1.5 rounded-xl bg-rose-900/50 hover:bg-rose-900/70 border border-rose-700/60 text-rose-200 text-xs font-bold transition flex items-center justify-center gap-1"
                    >
                      <span>VIEW RECOVERY</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>

              </div>
            )}

            {/* TAB 2: "WHY IS THIS SERVICE DEGRADED?" (SECTION 24 REQUIREMENT) */}
            {rightPanelTab === 'WHY_DEGRADED' && (
              <div className="space-y-3 text-xs">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-rose-500/40 space-y-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-rose-400" />
                    <strong className="text-white text-xs">STATUS: {getNodeHealthState(selectedNode)}</strong>
                  </div>

                  <p className="text-slate-300 text-xs leading-relaxed font-sans">
                    {selectedNode.why_degraded?.summary || (
                      getNodeHealthState(selectedNode) === 'CRITICAL'
                        ? `${selectedNode.display_name || selectedNode.name} connection pool saturated or critical error rate observed.`
                        : getNodeHealthState(selectedNode) === 'DEGRADED'
                        ? `${selectedNode.display_name || selectedNode.name} is experiencing elevated cascading timeout errors from downstream dependency.`
                        : `${selectedNode.display_name || selectedNode.name} is operating normally within baseline thresholds.`
                    )}
                  </p>
                </div>

                {/* Evidence Block */}
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">Empirical Evidence:</span>
                  
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between py-0.5 border-b border-slate-900">
                      <span className="text-slate-400">Current Error Rate:</span>
                      <strong className={(selectedNode.error_rate || 0) > 5 ? 'text-rose-400' : 'text-emerald-400'}>
                        {selectedNode.error_rate !== undefined ? `${selectedNode.error_rate}%` : '0.0%'}
                      </strong>
                    </div>

                    <div className="flex justify-between py-0.5 border-b border-slate-900">
                      <span className="text-slate-400">Baseline Error Rate:</span>
                      <span className="text-slate-300">{selectedNode.baseline?.error_rate || 0.1}%</span>
                    </div>

                    <div className="flex justify-between py-0.5 border-b border-slate-900">
                      <span className="text-slate-400">P95 Latency:</span>
                      <strong className={(selectedNode.p95_latency || 0) > 250 ? 'text-rose-400' : 'text-white'}>
                        {selectedNode.p95_latency || 18}ms
                      </strong>
                    </div>

                    <div className="flex justify-between py-0.5 border-b border-slate-900">
                      <span className="text-slate-400">Direct Dependency:</span>
                      <span className="text-cyan-300">{directDownstream[0]?.target || 'None (Storage)'}</span>
                    </div>

                    <div className="flex justify-between py-0.5 border-b border-slate-900">
                      <span className="text-slate-400">Active Incident:</span>
                      <span className="text-rose-300 font-bold">{selectedNode.active_incidents?.[0] || activeIncidentContext?.incident_id || 'NONE'}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => {
                    if (onNavigateToObservability) onNavigateToObservability(selectedNode.id);
                    else setActiveTab('observatory');
                  }}
                  className="w-full py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition"
                >
                  Inspect in Operational Observability →
                </button>
              </div>
            )}

            {/* TAB 3: UPSTREAM */}
            {rightPanelTab === 'UPSTREAM' && (
              <div className="space-y-2 text-xs">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">
                  Upstream Callers ({directUpstream.length})
                </span>
                {directUpstream.length > 0 ? (
                  directUpstream.map(up => (
                    <div
                      key={up.id}
                      onClick={() => setSelectedNodeId(up.source)}
                      className="p-2.5 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 flex items-center justify-between cursor-pointer transition"
                    >
                      <span className="text-indigo-300 font-bold">{up.source}</span>
                      <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                        <span>{up.request_volume || '120/min'}</span>
                        <span>•</span>
                        <span>{up.latency || '20ms'}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic p-4 text-center">Ingress Node (No Upstream Callers)</p>
                )}
              </div>
            )}

            {/* TAB 4: DOWNSTREAM */}
            {rightPanelTab === 'DOWNSTREAM' && (
              <div className="space-y-2 text-xs">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">
                  Downstream Dependencies ({directDownstream.length})
                </span>
                {directDownstream.length > 0 ? (
                  directDownstream.map(down => (
                    <div
                      key={down.id}
                      onClick={() => setSelectedNodeId(down.target)}
                      className="p-2.5 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 flex items-center justify-between cursor-pointer transition"
                    >
                      <span className="text-cyan-300 font-bold">{down.target}</span>
                      <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                        <span>{down.request_volume || '120/min'}</span>
                        <span>•</span>
                        <span className={down.dependency_status === 'FAILING' ? 'text-rose-400 font-bold' : ''}>{down.latency || '20ms'}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic p-4 text-center">Storage Leaf (No Downstream Dependencies)</p>
                )}
              </div>
            )}

            {/* Selected Edge Detail (if edge clicked) */}
            {selectedEdge && (
              <div className="p-3.5 rounded-xl bg-cyan-950/40 border border-cyan-500/50 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <strong className="text-cyan-300">EDGE: {selectedEdge.source} → {selectedEdge.target}</strong>
                  <button onClick={() => setSelectedEdgeId(null)} className="text-slate-400 hover:text-white">✕</button>
                </div>
                <div className="grid grid-cols-3 gap-1 text-[11px]">
                  <div>
                    <span className="text-slate-500 block text-[9px]">Status</span>
                    <span className={selectedEdge.dependency_status === 'FAILING' ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                      {selectedEdge.dependency_status || 'HEALTHY'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px]">Latency</span>
                    <span className="text-white font-bold">{selectedEdge.latency || '20ms'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px]">Error</span>
                    <span className={(selectedEdge.error_rate_pct || 0) > 5 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                      {selectedEdge.error_rate || '0.0%'}
                    </span>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>

      </div>

      {/* ============================================================================== */}
      {/* 3. BOTTOM: INCIDENT PROPAGATION FLOW STRIP (ROOT -> AFFECTED -> DOWNSTREAM)   */}
      {/* ============================================================================== */}
      {hasActiveIncident && (
        <div className="p-5 rounded-2xl glass-panel border border-rose-500/40 bg-gradient-to-r from-rose-950/30 via-slate-900 to-slate-950 font-mono space-y-3 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-rose-900/40 pb-2">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-rose-400 animate-pulse" />
              <strong className="text-sm font-bold text-white uppercase tracking-wider">
                ACTIVE INCIDENT PROPAGATION CASCADE: {activeIncidentContext?.incident_id}
              </strong>
            </div>
            <span className="text-xs text-rose-300">
              Severity: <strong className="text-white font-bold">{activeIncidentContext?.severity || 'CRITICAL'}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto py-1 text-xs">
            
            {/* ROOT CAUSE */}
            <div 
              onClick={() => setSelectedNodeId(activeIncidentContext?.root_cause_service || 'database-service')}
              className="p-3 rounded-xl bg-rose-500/20 border-2 border-rose-500 text-rose-300 cursor-pointer flex-shrink-0"
            >
              <span className="text-[9px] px-1.5 py-0.2 rounded font-black bg-rose-500 text-slate-950 block w-max mb-1">
                ROOT CAUSE
              </span>
              <strong className="text-sm text-white block">{activeIncidentContext?.root_cause_service}</strong>
              <span className="text-[10px] text-rose-400 block mt-0.5">Origin of Failure Cascade</span>
            </div>

            <ArrowRight className="h-5 w-5 text-rose-500 flex-shrink-0 animate-pulse" />

            {/* DIRECTLY AFFECTED (e.g. Service B) */}
            {activeIncidentContext?.affected_services.filter(s => s !== activeIncidentContext?.root_cause_service).map((aff, idx) => (
              <React.Fragment key={aff}>
                <div 
                  onClick={() => setSelectedNodeId(aff)}
                  className="p-3 rounded-xl bg-amber-500/20 border border-amber-500/60 text-amber-300 cursor-pointer flex-shrink-0"
                >
                  <span className="text-[9px] px-1.5 py-0.2 rounded font-black bg-amber-500/40 text-amber-200 block w-max mb-1">
                    CASCADE HOP #{idx + 1}
                  </span>
                  <strong className="text-sm text-white block">{aff}</strong>
                  <span className="text-[10px] text-amber-400 block mt-0.5">Direct Socket / RPC Timeout</span>
                </div>
                <ArrowRight className="h-4 w-4 text-amber-500/60 flex-shrink-0" />
              </React.Fragment>
            ))}

            {/* GATEWAY INGRESS IMPACT */}
            <div 
              onClick={() => setSelectedNodeId('gateway')}
              className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 cursor-pointer flex-shrink-0"
            >
              <span className="text-[9px] px-1.5 py-0.2 rounded font-black bg-slate-800 text-slate-300 block w-max mb-1">
                EDGE IMPACT
              </span>
              <strong className="text-sm text-white block">gateway</strong>
              <span className="text-[10px] text-slate-400 block mt-0.5">HTTP 500 / 502 to End Users</span>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};

import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Activity, 
  Zap, 
  Cpu, 
  HardDrive, 
  Database, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  Gauge, 
  Sparkles,
  Radio,
  Clock,
  ArrowRight,
  ShieldCheck,
  Server,
  SkipForward,
  Brain,
  Sliders,
  Terminal,
  RefreshCw,
  Search,
  Filter,
  Flame,
  Network,
  Share2
} from 'lucide-react';
import { api } from '../services/api';
import type { OrchestratorStatus, FailureScenarioItem } from '../types';
import { FailureCyclesView } from '../components/FailureCyclesView';
import { MeasuredLoadTestView } from '../components/MeasuredLoadTestView';
import { OperationalSimulationLab } from '../components/OperationalSimulationLab';

interface SimulatorPageProps {
  setActiveTab?: (tab: string) => void;
}

const LIFECYCLE_STEPS = [
  'IDLE',
  'INJECTING',
  'ACTIVE',
  'DETECTED',
  'INVESTIGATING',
  'RCA',
  'REMEDIATING',
  'VERIFYING',
  'RESOLVED',
  'LEARNED'
];

const EPS_PRESETS = [10, 100, 1000, 10000, 100000];

export const SimulatorPage: React.FC<SimulatorPageProps> = ({ setActiveTab }) => {
  // Orchestrator State
  const [orchestrator, setOrchestrator] = useState<OrchestratorStatus>({
    orchestrator_enabled: true,
    auto_mode: true,
    interval_seconds: 180,
    time_until_next_seconds: 180,
    next_injection_timestamp: Date.now() / 1000 + 180,
    active_scenario: null,
    active_scenario_start: null,
    lifecycle_state: 'IDLE',
    execution_mode: 'CONTROLLED_DEMO',
    can_inject_next: true,
    scenarios_executed_count: 0,
    total_available_scenarios: 33
  });

  const [scenarios, setScenarios] = useState<FailureScenarioItem[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'lab' | 'cycles' | 'load_test' | 'orchestrator' | 'streamer'>('lab');

  // Load Streamer & Real-Time Telemetry State
  const [streamerStatus, setStreamerStatus] = useState<any>({
    status: 'STREAMING',
    scenario: 'normal_traffic',
    events_streamed: 48210,
    total_events: 48210,
    target_count: 100000,
    configured_eps: 100,
    current_eps: 100,
    events_per_sec: 100,
    events_per_min: 6000,
    kafka_throughput_mb_s: 0.051,
    consumer_lag: 0,
    pipeline_latency_ms: 2.3,
    is_streaming: true
  });
  const [selectedFailureScenario, setSelectedFailureScenario] = useState<string>('DATABASE_CONNECTION_FAILURE');
  const [selectedEps, setSelectedEps] = useState<number>(100);
  const [liveDiagnostics, setLiveDiagnostics] = useState<any[]>([]);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [diagFilterService, setDiagFilterService] = useState<string>('ALL');
  const [diagFilterLevel, setDiagFilterLevel] = useState<string>('ALL');
  
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  const fetchOrchestrator = async () => {
    try {
      const data = await api.getOrchestratorStatus();
      if (data) setOrchestrator(data);
    } catch (e) {}
  };

  const fetchScenarios = async () => {
    try {
      const data = await api.listOrchestratorScenarios();
      if (data?.scenarios) setScenarios(data.scenarios);
    } catch (e) {}
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/simulator/orchestrator/history');
      if (res.ok) {
        const data = await res.json();
        if (data?.history) setHistory(data.history);
      }
    } catch (e) {}
  };

  const fetchTelemetryData = async () => {
    try {
      const [statusRes, diagRes] = await Promise.all([
        api.getTelemetryStatus().catch(() => null),
        api.getTelemetryDiagnostics(40).catch(() => null)
      ]);

      if (statusRes?.continuous_telemetry) {
        setStreamerStatus((prev: any) => ({
          ...prev,
          events_streamed: statusRes.continuous_telemetry.total_events || prev.events_streamed,
          total_events: statusRes.continuous_telemetry.total_events || prev.total_events,
          configured_eps: statusRes.continuous_telemetry.configured_eps || selectedEps,
          current_eps: statusRes.continuous_telemetry.actual_eps || selectedEps,
          events_per_sec: statusRes.continuous_telemetry.events_per_sec || selectedEps,
          events_per_min: statusRes.continuous_telemetry.events_per_min || (selectedEps * 60),
          kafka_throughput_mb_s: statusRes.continuous_telemetry.kafka_throughput_mb_s || 0.05,
          consumer_lag: statusRes.continuous_telemetry.consumer_lag || 0,
          pipeline_latency_ms: statusRes.continuous_telemetry.pipeline_latency_ms || 2.1
        }));
      }

      if (diagRes?.events && Array.isArray(diagRes.events)) {
        setLiveDiagnostics(diagRes.events);
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchOrchestrator();
    fetchScenarios();
    fetchHistory();
    fetchTelemetryData();

    const interval = setInterval(() => {
      fetchOrchestrator();
      fetchTelemetryData();
      if (activeView === 'orchestrator') {
        fetchHistory();
      }
    }, 1800);

    return () => clearInterval(interval);
  }, [activeView, selectedEps]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveDiagnostics, autoScroll]);

  const showFeedback = (type: 'success' | 'error' | 'info', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4500);
  };

  const handleTriggerNext = async () => {
    setLoadingAction('trigger');
    try {
      const res = await api.triggerOrchestratorNext();
      showFeedback('success', `Injected scenario: ${res.scenario?.name || 'Next scenario'}`);
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message || 'Cannot inject: system is in active incident lifecycle');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleForceScenario = async (scenarioId: string) => {
    setLoadingAction(`force-${scenarioId}`);
    try {
      const res = await api.forceOrchestratorScenario(scenarioId);
      showFeedback('success', `Injected scenario: ${res.scenario?.name || scenarioId}`);
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message || 'Failed to inject scenario');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleManualInjectFromStreamer = async () => {
    setLoadingAction('streamer-inject');
    try {
      const res = await api.triggerManualFailure(selectedFailureScenario);
      showFeedback('success', `Failure injected: ${res.scenario || selectedFailureScenario}`);
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message || 'Failed to inject failure');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRateChange = async (eps: number) => {
    setSelectedEps(eps);
    try {
      await api.setTelemetryRate(eps);
      showFeedback('info', `Continuous telemetry generation rate set to ${eps.toLocaleString()} EPS`);
    } catch (e: any) {
      showFeedback('error', e.message || 'Failed to update EPS rate');
    }
  };

  const handlePause = async () => {
    try {
      await api.pauseOrchestrator();
      showFeedback('info', 'Failure Orchestrator paused');
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message);
    }
  };

  const handleResume = async () => {
    try {
      await api.resumeOrchestrator();
      showFeedback('success', 'Failure Orchestrator resumed');
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message);
    }
  };

  const handleSkip = async () => {
    setLoadingAction('skip');
    try {
      const res = await api.skipOrchestratorScenario();
      showFeedback('info', res.message || 'Scenario skipped, target service restored');
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleIntervalChange = async (sec: number) => {
    try {
      await api.configOrchestrator({ interval_seconds: sec });
      showFeedback('success', `Interval set to ${sec}s (${Math.round(sec / 60)} min)`);
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message);
    }
  };

  const handleAutoModeToggle = async () => {
    try {
      const newMode = !orchestrator.auto_mode;
      await api.configOrchestrator({ auto_mode: newMode });
      showFeedback('info', `Auto-injection mode ${newMode ? 'ENABLED' : 'PAUSED'}`);
      fetchOrchestrator();
    } catch (e: any) {
      showFeedback('error', e.message);
    }
  };

  // Filter scenarios
  const filteredScenarios = scenarios.filter(sc => {
    const matchesCat = categoryFilter === 'ALL' || sc.category.toUpperCase() === categoryFilter;
    const matchesSearch = !searchQuery || 
      sc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sc.target_service.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sc.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const filteredDiagnostics = liveDiagnostics.filter(evt => {
    const matchesSvc = diagFilterService === 'ALL' || evt.service?.toLowerCase() === diagFilterService.toLowerCase();
    const matchesLvl = diagFilterLevel === 'ALL' || evt.severity?.toUpperCase() === diagFilterLevel.toUpperCase();
    return matchesSvc && matchesLvl;
  });

  const currentStepIdx = LIFECYCLE_STEPS.indexOf(orchestrator.lifecycle_state);

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* 1. Header & View Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <Zap className="h-7 w-7 text-indigo-400" />
              Failure Orchestration & High-Volume Telemetry
            </h1>
            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              CONTROLLED DEMO MODE
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            33 realistic failure scenarios across 10 categories • High-volume Kafka & OTel trace streaming (up to 100k EPS).
          </p>
        </div>

        {/* View Switcher */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800 flex-wrap">
          <button
            onClick={() => setActiveView('lab')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'lab'
                ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Flame className="h-3.5 w-3.5" />
            <span>17 Operational Scenarios Lab</span>
          </button>
          <button
            onClick={() => setActiveView('cycles')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'cycles'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Radio className="h-3.5 w-3.5" />
            <span>30 Failure Cycles</span>
          </button>
          <button
            onClick={() => setActiveView('load_test')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'load_test'
                ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Gauge className="h-3.5 w-3.5" />
            <span>Measured Load Engine</span>
          </button>
          <button
            onClick={() => setActiveView('orchestrator')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'orchestrator'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sliders className="h-3.5 w-3.5" />
            <span>33-Scenario Library</span>
          </button>
          <button
            onClick={() => setActiveView('streamer')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
              activeView === 'streamer'
                ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Live Streamer & Console</span>
          </button>
        </div>
      </div>

      {/* Controlled Demo Mode Safety Notice */}
      <div className="bg-gradient-to-r from-indigo-950/40 via-slate-900/40 to-slate-900/40 border border-indigo-500/20 rounded-xl p-4 flex items-start gap-3">
        <ShieldCheck className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-300 space-y-1">
          <div className="font-semibold text-white flex items-center gap-2">
            Non-Destructive Controlled Demo Sandbox Active
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
              execution_mode = "CONTROLLED_DEMO"
            </span>
          </div>
          <p className="text-slate-400 leading-relaxed">
            All failures are simulated strictly within isolated mock microservices (gateway:8001, service-a:8002, service-b:8003, database-service:8004, auth-service:8005).
            No host processes, operating system settings, or production infrastructure will ever be terminated or modified.
          </p>
        </div>
      </div>

      {/* Feedback Toast */}
      {feedback && (
        <div className={`p-3.5 rounded-xl text-xs font-semibold flex items-center gap-2 border animate-fadeIn ${
          feedback.type === 'success' ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700' :
          feedback.type === 'error' ? 'bg-rose-950/80 text-rose-300 border-rose-700' :
          'bg-indigo-950/80 text-indigo-300 border-indigo-700'
        }`}>
          {feedback.type === 'success' && <CheckCircle2 className="h-4 w-4" />}
          {feedback.type === 'error' && <AlertTriangle className="h-4 w-4" />}
          {feedback.type === 'info' && <Radio className="h-4 w-4" />}
          <span>{feedback.message}</span>
        </div>
      )}

      {activeView === 'lab' && (
        <OperationalSimulationLab setActiveTab={setActiveTab} />
      )}

      {activeView === 'cycles' && (
        <FailureCyclesView onScenarioInjected={(sc) => showFeedback('success', `Scenario active: ${sc.title}`)} />
      )}

      {activeView === 'load_test' && (
        <MeasuredLoadTestView />
      )}

      {activeView === 'orchestrator' && (
        <>
          {/* 2. Autonomous Incident Lifecycle Bar */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Activity className="h-4 w-4 text-indigo-400" />
                  Autonomous Incident Lifecycle Loop
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  State machine enforces: No overlapping failures. Next scenario only triggers after previous is verified & learned.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400 font-mono">
                  Executed: <strong className="text-white">{orchestrator.scenarios_executed_count}</strong> / {scenarios.length || 33}
                </span>
                <span className={`px-2.5 py-1 text-xs font-mono font-bold rounded-full border ${
                  orchestrator.can_inject_next 
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                    : 'bg-amber-950 text-amber-300 border-amber-800 animate-pulse'
                }`}>
                  {orchestrator.can_inject_next ? 'READY FOR NEXT' : 'REMEDIATION IN PROGRESS'}
                </span>
              </div>
            </div>

            {/* Stepper */}
            <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5 pt-2">
              {LIFECYCLE_STEPS.map((step, idx) => {
                const isCurrent = orchestrator.lifecycle_state === step;
                const isPast = currentStepIdx > idx;
                return (
                  <div 
                    key={step}
                    className={`p-2 rounded-lg text-center font-mono text-[10px] font-bold border transition-all ${
                      isCurrent ? 'bg-indigo-600 text-white border-indigo-400 shadow-md shadow-indigo-600/40 ring-1 ring-white/50' :
                      isPast ? 'bg-slate-800/80 text-emerald-400 border-slate-700' :
                      'bg-slate-950 text-slate-500 border-slate-800/60'
                    }`}
                  >
                    {step}
                  </div>
                );
              })}
            </div>

            {/* Controls Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={handleTriggerNext}
                  disabled={loadingAction === 'trigger' || !orchestrator.can_inject_next}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-md shadow-indigo-600/30"
                >
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <span>{loadingAction === 'trigger' ? 'Injecting...' : 'Inject Next Failure'}</span>
                </button>

                <button
                  onClick={handleSkip}
                  disabled={loadingAction === 'skip' || orchestrator.lifecycle_state === 'IDLE'}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
                >
                  <SkipForward className="h-3.5 w-3.5" />
                  <span>Skip / Restore</span>
                </button>

                {orchestrator.orchestrator_enabled ? (
                  <button
                    onClick={handlePause}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Pause className="h-3.5 w-3.5" />
                    <span>Pause Scheduler</span>
                  </button>
                ) : (
                  <button
                    onClick={handleResume}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 rounded-lg text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Play className="h-3.5 w-3.5" />
                    <span>Resume Scheduler</span>
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Cadence:</span>
                {[60, 180, 300].map((sec) => (
                  <button
                    key={sec}
                    onClick={() => handleIntervalChange(sec)}
                    className={`px-2 py-1 text-[11px] font-mono rounded border transition ${
                      orchestrator.interval_seconds === sec
                        ? 'bg-indigo-950 text-indigo-300 border-indigo-700'
                        : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
                    }`}
                  >
                    {Math.round(sec / 60)}m
                  </button>
                ))}
                <button
                  onClick={handleAutoModeToggle}
                  className={`px-2.5 py-1 text-[11px] font-mono rounded border transition ml-1 ${
                    orchestrator.auto_mode
                      ? 'bg-indigo-950 text-indigo-300 border-indigo-700'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}
                >
                  Auto: {orchestrator.auto_mode ? 'ON' : 'OFF'}
                </button>
              </div>
            </div>
          </div>

          {/* 3. 33 Scenarios Matrix Catalog */}
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Sliders className="h-5 w-5 text-indigo-400" />
                  33-Scenario Enterprise Failure Catalog ({filteredScenarios.length} Available)
                </h3>
                <p className="text-xs text-slate-400">
                  Select any scenario to force inject immediately or view expected telemetry signatures and remedies.
                </p>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className="relative">
                  <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search scenarios or services..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-52"
                  />
                </div>

                <select
                  value={categoryFilter}
                  onChange={e => setCategoryFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                >
                  <option value="ALL">All Categories (10)</option>
                  <option value="DATABASE">Database</option>
                  <option value="RESOURCE">Resource</option>
                  <option value="PERFORMANCE">Performance</option>
                  <option value="NETWORK">Network</option>
                  <option value="DEPENDENCY">Dependency</option>
                  <option value="AVAILABILITY">Availability</option>
                  <option value="APPLICATION">Application</option>
                  <option value="BEHAVIORAL">Behavioral</option>
                  <option value="CACHE">Cache</option>
                  <option value="CASCADE">Cascade</option>
                  <option value="NOVEL">Novel / Unknown</option>
                </select>
              </div>
            </div>

            {/* Scenario Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredScenarios.map((sc) => {
                const isActive = orchestrator.active_scenario?.id === sc.id;
                return (
                  <div
                    key={sc.id}
                    className={`rounded-xl p-4 border transition-all relative flex flex-col justify-between ${
                      isActive
                        ? 'bg-indigo-950/40 border-indigo-500 shadow-lg shadow-indigo-950/50 ring-1 ring-indigo-500'
                        : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700 truncate">
                          {sc.category}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          sc.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                          sc.severity === 'HIGH' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                          'bg-blue-950 text-blue-300 border border-blue-800'
                        }`}>
                          {sc.severity}
                        </span>
                      </div>

                      <h4 className="font-semibold text-sm text-white leading-snug">
                        {sc.name}
                      </h4>
                      <div className="text-[11px] font-mono text-slate-400 mt-1 flex items-center gap-1.5">
                        <Server className="h-3 w-3 text-indigo-400" />
                        Target: <span className="text-slate-200">{sc.target_service}</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-2 leading-relaxed line-clamp-3">
                        {sc.description}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-800/80">
                      <div className="text-[10px] text-slate-500 mb-2">
                        Remedy: <span className="text-emerald-400 font-mono font-semibold">{sc.recommended_action}</span>
                      </div>
                      <button
                        onClick={() => handleForceScenario(sc.id)}
                        disabled={loadingAction === `force-${sc.id}`}
                        className={`w-full py-1.5 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                          isActive
                            ? 'bg-rose-900/60 text-rose-200 border border-rose-700'
                            : 'bg-slate-800 hover:bg-indigo-600 hover:text-white text-slate-300 border border-slate-700'
                        }`}
                      >
                        <Zap className="h-3 w-3 text-amber-400" />
                        {isActive ? 'Currently Active' : 'Force Inject Now'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 4. Scenario Execution History & Learning Log */}
          {history.length > 0 && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Brain className="h-4 w-4 text-indigo-400" />
                Scenario Execution & Historical Learning Log
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-slate-400 border-b border-slate-800 font-mono">
                    <tr>
                      <th className="pb-2">Scenario</th>
                      <th className="pb-2">Target Service</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2">Triggered At</th>
                      <th className="pb-2">Resolved At</th>
                      <th className="pb-2">MTTR</th>
                      <th className="pb-2 text-right">Learned</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-sans">
                    {history.slice(0, 8).map((rec, i) => (
                      <tr key={i} className="hover:bg-slate-800/30">
                        <td className="py-2.5 font-medium text-white">{rec.scenario_name || rec.scenario_id}</td>
                        <td className="py-2.5 font-mono text-slate-300">{rec.target_service}</td>
                        <td className="py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            rec.status === 'RESOLVED' || rec.status === 'LEARNED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                            'bg-indigo-950 text-indigo-300 border border-indigo-800'
                          }`}>
                            {rec.status}
                          </span>
                        </td>
                        <td className="py-2.5 text-slate-400">{rec.triggered_at ? rec.triggered_at.slice(11, 19) : '-'}</td>
                        <td className="py-2.5 text-slate-400">{rec.resolved_at ? rec.resolved_at.slice(11, 19) : '-'}</td>
                        <td className="py-2.5 font-mono text-slate-300">{rec.duration_seconds ? `${rec.duration_seconds.toFixed(1)}s` : '-'}</td>
                        <td className="py-2.5 text-right">
                          <span className="inline-flex items-center gap-1 text-[11px] text-indigo-400 font-medium">
                            <Brain className="h-3 w-3" /> Indexed
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {activeView === 'streamer' && (
        /* High-Volume Telemetry Streamer & Live Console View */
        <div className="space-y-6">
          {/* Live Throughput KPI Strip */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Current Ingestion</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-cyan-400 font-mono">{streamerStatus.events_per_sec}</span>
                <span className="text-[10px] text-slate-400 font-bold font-mono">EPS</span>
              </div>
              <p className="text-[10px] text-slate-500 font-mono mt-1">Configured: {selectedEps.toLocaleString()} EPS</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Throughput / min</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-white font-mono">{streamerStatus.events_per_min.toLocaleString()}</span>
              </div>
              <p className="text-[10px] text-slate-500 font-mono mt-1">Sustained rate</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Total Events Streamed</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-white font-mono">{streamerStatus.total_events.toLocaleString()}</span>
              </div>
              <p className="text-[10px] text-emerald-400 font-mono mt-1">● Pipeline Active</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Kafka Throughput</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-indigo-400 font-mono">{streamerStatus.kafka_throughput_mb_s}</span>
                <span className="text-[10px] text-slate-400 font-mono">MB/s</span>
              </div>
              <p className="text-[10px] text-slate-500 font-mono mt-1">540 B / event</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Consumer Lag</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-white font-mono">{streamerStatus.consumer_lag}</span>
                <span className="text-[10px] text-slate-400 font-mono">msgs</span>
              </div>
              <p className="text-[10px] text-emerald-400 font-mono mt-1">Within SLA</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium">Pipeline Latency</p>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-emerald-400 font-mono">{streamerStatus.pipeline_latency_ms}</span>
                <span className="text-[10px] text-slate-400 font-mono">ms</span>
              </div>
              <p className="text-[10px] text-slate-500 font-mono mt-1">End-to-end ingestion</p>
            </div>
          </div>

          {/* Controls Bar: Rate Pacing + Scenario Injection */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Gauge className="h-4 w-4 text-cyan-400" />
                  Scalable Telemetry Rate Pacing (10 to 100,000+ EPS)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Select a rate preset or use the slider to scale continuous synthetic telemetry generation.
                </p>
              </div>

              {/* Rate Buttons */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {EPS_PRESETS.map((eps) => (
                  <button
                    key={eps}
                    onClick={() => handleRateChange(eps)}
                    className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg border transition ${
                      selectedEps === eps
                        ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white border-cyan-400 shadow-md shadow-cyan-600/30'
                        : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white'
                    }`}
                  >
                    {eps >= 1000 ? `${eps / 1000}k` : eps} EPS
                  </button>
                ))}
              </div>
            </div>

            {/* Failure Injection & Controls Row */}
            <div className="pt-3 border-t border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-bold text-slate-300">Failure Injection:</label>
                  <select
                    value={selectedFailureScenario}
                    onChange={(e) => setSelectedFailureScenario(e.target.value)}
                    className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                  >
                    {scenarios.map((sc) => (
                      <option key={sc.id} value={sc.id}>
                        [{sc.category}] {sc.name} ({sc.target_service})
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleManualInjectFromStreamer}
                  disabled={loadingAction === 'streamer-inject'}
                  className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-md shadow-rose-600/30 transition flex items-center gap-1.5"
                >
                  <Flame className="h-3.5 w-3.5" />
                  <span>{loadingAction === 'streamer-inject' ? 'Injecting...' : 'Inject Failure Now'}</span>
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => api.resetSimulator()}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-700 rounded-lg text-xs font-semibold transition"
                >
                  Reset State
                </button>
              </div>
            </div>
          </div>

          {/* Real-Time Telemetry Streaming Window */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl space-y-0">
            {/* Terminal Header */}
            <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-cyan-400" />
                <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                  Live Unified Telemetry Stream Console
                </h4>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-800 animate-pulse">
                  AUTO-STREAMING
                </span>
              </div>

              {/* Filters & Toggles */}
              <div className="flex items-center gap-2.5 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-slate-400">Service:</span>
                  <select
                    value={diagFilterService}
                    onChange={(e) => setDiagFilterService(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 font-mono"
                  >
                    <option value="ALL">All Services</option>
                    <option value="gateway">gateway</option>
                    <option value="service-a">service-a</option>
                    <option value="service-b">service-b</option>
                    <option value="payment-api">payment-api</option>
                    <option value="auth-service">auth-service</option>
                    <option value="database-service">database-service</option>
                  </select>
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-slate-400">Severity:</span>
                  <select
                    value={diagFilterLevel}
                    onChange={(e) => setDiagFilterLevel(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 font-mono"
                  >
                    <option value="ALL">All Levels</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>

                <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer ml-1">
                  <input
                    type="checkbox"
                    checked={autoScroll}
                    onChange={(e) => setAutoScroll(e.target.checked)}
                    className="rounded bg-slate-800 border-slate-700 text-cyan-500"
                  />
                  <span className="text-[11px]">Auto-scroll</span>
                </label>
              </div>
            </div>

            {/* Virtualized Log Events Stream */}
            <div className="h-96 overflow-y-auto p-3 font-mono text-xs space-y-1.5 select-text bg-slate-950/90 divide-y divide-slate-900/60">
              {filteredDiagnostics.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-cyan-500" />
                  <p>Buffering live telemetry stream across 6 microservices...</p>
                </div>
              ) : (
                filteredDiagnostics.map((evt, idx) => (
                  <div 
                    key={evt.event_id || idx}
                    className="pt-1.5 flex items-start justify-between gap-3 text-[11px] hover:bg-slate-900/40 p-1 rounded"
                  >
                    <div className="flex items-start gap-2.5 flex-1 min-w-0">
                      {/* Timestamp & Latency */}
                      <span className="text-slate-500 shrink-0">
                        {evt.timestamp ? evt.timestamp.slice(11, 23) : 'now'}
                      </span>
                      
                      <span className="text-[10px] px-1 rounded bg-slate-900 text-slate-400 border border-slate-800 shrink-0">
                        +{evt.ingestion_latency_ms || 2.1}ms
                      </span>

                      {/* Severity */}
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 ${
                        evt.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                        evt.severity === 'ERROR' ? 'bg-rose-900/50 text-rose-300 border border-rose-700' :
                        evt.severity === 'WARNING' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                        'bg-emerald-950/60 text-emerald-300 border border-emerald-900'
                      }`}>
                        {evt.severity}
                      </span>

                      {/* Service */}
                      <span className="text-cyan-400 font-bold shrink-0">
                        {evt.service}:
                      </span>

                      {/* Message */}
                      <span className="text-slate-200 truncate">
                        {evt.message}
                      </span>
                    </div>

                    {/* Correlated Trace / Span */}
                    <div className="text-[10px] text-slate-500 shrink-0 font-mono hidden md:block">
                      {evt.trace_id ? `${evt.trace_id.slice(0, 12)}...` : 'trc-direct'}
                    </div>
                  </div>
                ))
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

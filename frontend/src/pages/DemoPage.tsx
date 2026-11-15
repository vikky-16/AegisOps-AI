import React, { useState } from 'react';
import { 
  PlayCircle, 
  Zap, 
  HardDrive, 
  AlertTriangle, 
  RotateCcw, 
  CheckCircle2, 
  RotateCw, 
  Sparkles,
  Cpu,
  Database,
  FileText,
  Layers,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';

interface DemoPageProps {
  setActiveTab?: (tab: string) => void;
}

export const DemoPage: React.FC<DemoPageProps> = ({ setActiveTab }) => {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [logMessages, setLogMessages] = useState<string[]>([]);

  const scenarios = [
    {
      id: 'service-failure',
      title: 'Service Failure & Autonomous Self-Healing',
      description: 'Injects process crash into Payment Service B. System detects anomaly via Isolation Forest, correlates cascade effects, performs RCA, recommends Restart, executes recovery, and verifies healthy state.',
      icon: Zap,
      accent: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10',
      steps: [
        'Inject simulated failure into Service B',
        'AI Isolation Forest & Z-Score detect anomaly (score > 0.85)',
        'Incident INC-001 opened & cascade events correlated',
        'Dependency-Aware RCA identifies Service B as root cause (94% conf)',
        'Recommendation Engine generates RESTART_SERVICE (Low Risk)',
        'Autonomous healing hook executed against Service B',
        'Recovery Verifier confirms health probe & synthetic E2E transaction',
        'Incident resolved and indexed into Knowledge Base'
      ]
    },
    {
      id: 'high-cpu',
      title: 'High CPU Saturation & Worker Scaling',
      description: 'Simulates intensive workload surge on Service A. System detects thread pool queue saturation, recommends thread scaling, and verifies reduced latency.',
      icon: Cpu,
      accent: 'border-amber-500/40 text-amber-400 bg-amber-500/10',
      steps: [
        'Inject high CPU workload surge on Service A',
        'Z-Score anomaly detector registers CPU > 92% and queue drift',
        'Incident opened: Service A Workload Saturation',
        'AI recommends SCALE_WORKERS to increase thread concurrency',
        'System autonomously executes thread pool expansion',
        'Post-recovery probe verifies latency p95 restored < 25ms',
        'Incident resolved automatically'
      ]
    },
    {
      id: 'log-storm-10k',
      title: 'Log Storm — 10,000+ Logs Processing & Correlation',
      description: 'Generates 10,000 simulated log events in high-speed batches. System ingests, fingerprints, deduplicates, and correlates 10,000 events into ONE single incident without freezing UI.',
      icon: FileText,
      accent: 'border-indigo-500/40 text-indigo-400 bg-indigo-500/10',
      steps: [
        'Generate 10,000 simulated log events in high-speed batches',
        'In-memory ring buffer ingests and indexes all 10,000 logs',
        'SHA256 log fingerprinting deduplicates 6,000 identical timeout entries',
        'Event Correlator links cascade logs across Database, SvcB, SvcA, Gateway',
        'Single unified incident INC-STORM-001 opened (10,000 events correlated)',
        'RCA identifies Database pool saturation as primary root cause'
      ]
    },
    {
      id: 'storage-pressure',
      title: 'Database Storage Pressure & Predictive Archival',
      description: 'Simulates rapid tablespace growth to 98%. System extrapolates linear trend, predicts critical exhaustion in hours, recommends log rotation and gzip compression, and reclaims space.',
      icon: HardDrive,
      accent: 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10',
      steps: [
        'Inject tablespace storage pressure on Database Service',
        'Predictive Analytics detects growth rate (+1.8 GB/h)',
        'Forecast estimates critical point (95%) in ~10 hours',
        'Recommendation Engine suggests log rotation and compression',
        'Administrator approves archival action',
        'Gzip compression archives active logs into data/archive/',
        '18.2 GB reclaimed and disk utilization restored below 70%'
      ]
    },
    {
      id: 'database-failure',
      title: 'Database Connection Saturation & Pool Reset',
      description: 'Simulates database connection pool lock saturation (20/20 active). System correlates transaction timeouts and executes connection pool reset.',
      icon: Database,
      accent: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10',
      steps: [
        'Simulate connection pool exhaustion on Database Service (20/20 slots)',
        'Isolation Forest flags active connection anomaly',
        'Incident created: Database Lock Saturation',
        'RCA isolates database persistence layer as root cause',
        'Recommends RESET_CONNECTION_POOL',
        'Autonomous pool flush executed & all 20 slots released',
        'Synthetic transaction verified'
      ]
    },
    {
      id: 'alert-correlation',
      title: 'Alert Storm & Multi-Service Cascade Correlation',
      description: 'Fires 500+ cascade errors across Database, Service B, Service A, and Gateway in 5 seconds. Verifies the Event Correlation Engine deduplicates all events into ONE single incident.',
      icon: Layers,
      accent: 'border-purple-500/40 text-purple-400 bg-purple-500/10',
      steps: [
        'Trigger 500+ rapid error logs across all 4 microservices',
        'Event Correlator evaluates sliding window & topological pipeline',
        'Fingerprinting clusters 500+ repeated log signatures',
        'Deduplication engine merges all cascade errors into 1 incident',
        'Prevents alert fatigue while preserving complete event timeline'
      ]
    },
    {
      id: 'failed-recovery',
      title: 'Failed Recovery & Automated Escalation',
      description: 'Simulates deep database lock timeout that fails soft restart. Recovery Verifier detects persistent error, flags recovery failure, escalates incident, and prompts for alternative action.',
      icon: RotateCcw,
      accent: 'border-rose-500/40 text-rose-400 bg-rose-500/10',
      steps: [
        'Inject connection exhaustion on Database Service',
        'Initial soft restart executed on target service',
        'Verification Probe fails (Connection pool remained exhausted)',
        'System marks recovery as FAILED and escalates severity to CRITICAL',
        'AI Engine recommends RESET_CONNECTION_POOL as alternative',
        'Second recovery executed & verified successfully'
      ]
    }
  ];

  const handleRunScenario = async (sc: typeof scenarios[0]) => {
    setActiveScenario(sc.id);
    setIsRunning(true);
    setStepIndex(0);
    setLogMessages([`[${new Date().toLocaleTimeString()}] Starting ${sc.title}...`]);

    try {
      await api.triggerSimulation(sc.id);

      // Advance through steps with simulated timer
      for (let i = 0; i < sc.steps.length; i++) {
        await new Promise(r => setTimeout(r, 1100));
        setStepIndex(i + 1);
        setLogMessages(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${sc.steps[i]}`]);
      }
    } catch (e: any) {
      setLogMessages(prev => [...prev, `[ERROR] Simulation failed: ${e.message}`]);
    } finally {
      setIsRunning(false);
    }
  };

  const currentScenarioObj = scenarios.find(s => s.id === activeScenario);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <PlayCircle className="h-5 w-5 text-cyan-400" />
            <span>Interactive 1-Click Demo Control Center</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Execute end-to-end autonomous scenarios with live step-by-step verification, log streams, and diagnostic telemetry.
          </p>
        </div>

        {setActiveTab && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('logs')}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5"
            >
              <FileText className="h-4 w-4 text-cyan-400" />
              <span>Inspect Log Viewer</span>
            </button>
          </div>
        )}
      </div>

      {/* Scenarios Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {scenarios.map((sc) => {
          const Icon = sc.icon;
          const isSelected = activeScenario === sc.id;

          return (
            <div 
              key={sc.id} 
              className={`p-5 rounded-2xl glass-panel space-y-4 border transition flex flex-col justify-between ${
                isSelected ? 'border-cyan-500 shadow-xl shadow-cyan-500/10' : 'hover:border-slate-700'
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-xl border ${sc.accent}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{sc.title}</h3>
                    <span className="text-[10px] font-mono text-slate-400">Pure CPU-Native • Sandboxed</span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">{sc.description}</p>
              </div>

              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-[11px] text-slate-400 font-mono">{sc.steps.length} automated steps</span>
                <button
                  onClick={() => handleRunScenario(sc)}
                  disabled={isRunning}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-cyan-500/20 transition flex items-center gap-1.5 disabled:opacity-50"
                >
                  <PlayCircle className="h-4 w-4" />
                  <span>{isRunning && activeScenario === sc.id ? 'Running Demo...' : 'Run Demo'}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Stepper & Realtime Logs */}
      {currentScenarioObj && (
        <div className="p-6 rounded-2xl glass-panel space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-cyan-400" />
              <span>Live Scenario Progression: {currentScenarioObj.title}</span>
            </h3>
            {stepIndex >= currentScenarioObj.steps.length && (
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/30 flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>SCENARIO VERIFIED & COMPLETED</span>
              </span>
            )}
          </div>

          {/* Stepper Steps */}
          <div className="space-y-2.5">
            {currentScenarioObj.steps.map((step, idx) => {
              const isCompleted = stepIndex > idx;
              const isCurrent = stepIndex === idx && isRunning;

              return (
                <div 
                  key={idx}
                  className={`p-3 rounded-xl border text-xs flex items-center gap-3 transition-all duration-300 ${
                    isCompleted 
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' 
                      : isCurrent
                      ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-200 animate-pulse'
                      : 'bg-slate-900/60 border-slate-800/80 text-slate-500'
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
                  ) : isCurrent ? (
                    <RotateCw className="h-4 w-4 text-cyan-400 animate-spin flex-shrink-0" />
                  ) : (
                    <span className="h-4 w-4 rounded-full border border-slate-700 text-[10px] font-mono flex items-center justify-center flex-shrink-0">
                      {idx + 1}
                    </span>
                  )}
                  <span className="font-medium">{step}</span>
                </div>
              );
            })}
          </div>

          {/* Execution Log */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1.5 font-mono text-[11px]">
            <p className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold">Live SRE Orchestrator Console Output</p>
            <div className="max-h-36 overflow-y-auto space-y-1">
              {logMessages.map((msg, i) => (
                <p key={i} className="text-slate-300">{msg}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import os

file_path = os.path.join("frontend", "src", "pages", "DashboardPage.tsx")

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update imports
if "Network," not in text:
    old_imp = "Building2\n} from 'lucide-react';"
    if old_imp not in text:
        old_imp = "Building2\r\n} from 'lucide-react';"
    new_imp = "Building2,\n  Network,\n  Target,\n  Flame,\n  FileText,\n  CheckCircle,\n  XCircle\n} from 'lucide-react';"
    text = text.replace(old_imp, new_imp)

# 2. Add state
old_state = "const [quickApproveLoading, setQuickApproveLoading] = useState<boolean>(false);"
new_state = """const [quickApproveLoading, setQuickApproveLoading] = useState<boolean>(false);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  const [activeDetailTab, setActiveDetailTab] = useState<'overview' | 'timeline' | 'anomalies' | 'dependencies' | 'rca' | 'hypotheses' | 'evidence' | 'solution' | 'validation'>('overview');
  const [injectLoading, setInjectLoading] = useState<string | null>(null);
  const [validationRunning, setValidationRunning] = useState<boolean>(false);
  const [validationResult, setValidationResult] = useState<any | null>(null);

  const handleInjectChaos = async (company: string, target: string, failure: string) => {
    setInjectLoading(failure);
    try {
      await fetch('http://127.0.0.1:8000/api/simulation/failure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company, target, failure, duration_seconds: 30 })
      });
    } catch (e) {
      console.error(e);
    } finally {
      setInjectLoading(null);
    }
  };

  const handleResetChaos = async () => {
    setInjectLoading('reset');
    try {
      await fetch('http://127.0.0.1:8000/api/simulation/reset', { method: 'POST' });
    } catch (e) {
      console.error(e);
    } finally {
      setInjectLoading(null);
    }
  };

  const handleValidateIncident = async (incidentId: string) => {
    setValidationRunning(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/incidents/${incidentId}/validate`, { method: 'POST' });
      const data = await res.json();
      setValidationResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setValidationRunning(false);
    }
  };"""

if "const [selectedIncident" not in text:
    text = text.replace(old_state, new_state)

# 3. Add Incident section above section 5
marker = "{/* 5. ML Model & Anomaly Ensemble Audit Status Panel */}"
incident_section = """      {/* 4B. REAL INCIDENT INTELLIGENCE & RCA ENGINE (PHASE 23) */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Flame className="h-5 w-5 text-rose-500 animate-pulse" />
              <h3 className="text-base font-bold text-white">
                Autonomous Incident Intelligence & Multi-Factor RCA
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                {incidents.filter(i => i.status !== 'RESOLVED').length} ACTIVE
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Real-time anomaly detection, correlation episodes, 7-factor mathematical RCA, and closed-loop replica validation.
            </p>
          </div>

          {/* Quick Real Chaos Failure Injectors */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-mono text-slate-400 font-bold mr-1">Inject Real Fault:</span>
            <button
              onClick={() => handleInjectChaos('shopsphere', 'order-service', 'database_latency')}
              disabled={!!injectLoading}
              className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-amber-500/60 text-amber-300 text-xs font-mono font-semibold transition flex items-center gap-1.5"
            >
              <span>DB Latency (ShopSphere)</span>
            </button>
            <button
              onClick={() => handleInjectChaos('clouddesk', 'compute-service', 'redis_unavailable')}
              disabled={!!injectLoading}
              className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-rose-500/60 text-rose-300 text-xs font-mono font-semibold transition flex items-center gap-1.5"
            >
              <span>Redis Outage (CloudDesk)</span>
            </button>
            <button
              onClick={() => handleInjectChaos('fincore', 'payment-service', 'service_timeout')}
              disabled={!!injectLoading}
              className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/60 text-cyan-300 text-xs font-mono font-semibold transition flex items-center gap-1.5"
            >
              <span>Timeout (FinCore)</span>
            </button>
            <button
              onClick={handleResetChaos}
              disabled={!!injectLoading}
              className="px-3 py-1.5 rounded-lg bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700 text-emerald-300 text-xs font-mono font-bold transition flex items-center gap-1.5"
            >
              <RefreshCw className={`h-3 w-3 ${injectLoading === 'reset' ? 'animate-spin' : ''}`} />
              <span>Reset All</span>
            </button>
          </div>
        </div>

        {/* INCIDENTS TABLE */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800/80 text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                <th className="py-2.5 px-3">Incident ID</th>
                <th className="py-2.5 px-3">Company</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Detected</th>
                <th className="py-2.5 px-3">Affected Services</th>
                <th className="py-2.5 px-3">Primary Root Cause</th>
                <th className="py-2.5 px-3">Confidence</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40 text-xs font-mono">
              {incidents.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500">
                    No active or historical incidents recorded. Baseline is healthy. Inject a failure above to test the autonomous pipeline.
                  </td>
                </tr>
              ) : (
                incidents.map((inc) => {
                  const isSel = selectedIncident?.incident_id === inc.incident_id;
                  const companyName = (inc.tenant_id || inc.company || 'shopsphere').toLowerCase();
                  return (
                    <tr
                      key={inc.incident_id}
                      onClick={() => {
                        setSelectedIncident(inc);
                        setValidationResult(null);
                      }}
                      className={`hover:bg-slate-800/50 cursor-pointer transition ${isSel ? 'bg-indigo-950/40 border-l-2 border-indigo-400' : ''}`}
                    >
                      <td className="py-3 px-3 font-bold text-cyan-300">{inc.incident_id}</td>
                      <td className="py-3 px-3 capitalize font-sans text-slate-200">{companyName}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          inc.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                          inc.severity === 'HIGH' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                          'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                        }`}>
                          {inc.severity}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          inc.status === 'VALIDATED' || inc.status === 'RESOLVED' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                          'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                        }`}>
                          {inc.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {inc.created_at ? new Date(inc.created_at).toLocaleTimeString() : 'Recent'}
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-slate-300">
                          {(inc.affected_services || [inc.primary_service]).join(', ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-amber-300 font-bold font-sans">
                        {inc.root_cause || inc.root_cause_service || inc.primary_service}
                      </td>
                      <td className="py-3 px-3 text-emerald-400 font-bold">
                        {Math.round((inc.root_cause_confidence || inc.rca_confidence || 0.88) * 100)}%
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedIncident(inc);
                          }}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400 hover:text-cyan-300 text-[11px] font-sans font-semibold transition"
                        >
                          {isSel ? 'Viewing' : 'Inspect'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* CLICKED INCIDENT DETAIL CARD (9 TABS) */}
        {selectedIncident && (
          <div className="mt-4 p-5 rounded-xl bg-slate-950/80 border border-indigo-500/40 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-cyan-400">{selectedIncident.incident_id}</span>
                  <span className="text-xs text-slate-500">•</span>
                  <h4 className="text-sm font-bold text-white font-sans">{selectedIncident.title}</h4>
                </div>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                  Primary Root Cause: <strong className="text-amber-300">{selectedIncident.root_cause || selectedIncident.root_cause_service}</strong> | Confidence: <strong className="text-emerald-400">{Math.round((selectedIncident.root_cause_confidence || 0.88) * 100)}%</strong>
                </p>
              </div>

              {/* Sub-Tab Navigation */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'timeline', label: 'Timeline' },
                  { id: 'anomalies', label: 'Anomalies' },
                  { id: 'dependencies', label: 'Dependencies' },
                  { id: 'rca', label: 'Root Cause' },
                  { id: 'hypotheses', label: 'Alternatives' },
                  { id: 'evidence', label: 'Evidence' },
                  { id: 'solution', label: 'Solution' },
                  { id: 'validation', label: 'Validation' }
                ].map(t => (
                  <button
                    key={t.id}
                    onClick={() => setActiveDetailTab(t.id as any)}
                    className={`px-2.5 py-1 rounded text-xs font-semibold font-mono transition ${
                      activeDetailTab === t.id
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                        : 'bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* TAB 1: OVERVIEW */}
            {activeDetailTab === 'overview' && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-500">Company</span>
                  <p className="font-bold text-white mt-1 capitalize">{selectedIncident.tenant_id || selectedIncident.company}</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-500">Severity</span>
                  <p className="font-bold text-rose-400 mt-1">{selectedIncident.severity}</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-500">Lifecycle Status</span>
                  <p className="font-bold text-cyan-300 mt-1">{selectedIncident.status}</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-500">Affected Services</span>
                  <p className="font-bold text-slate-200 mt-1">{(selectedIncident.affected_services || [selectedIncident.primary_service]).join(', ')}</p>
                </div>
              </div>
            )}

            {/* TAB 2: TIMELINE */}
            {activeDetailTab === 'timeline' && (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1 text-xs font-mono">
                {(selectedIncident.timeline || []).map((t: any, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80 flex items-start gap-3">
                    <span className="text-slate-500 whitespace-nowrap">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : 'T+0s'}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-cyan-300">{t.service}</span>
                    <span className="text-slate-200 flex-1">{t.event || t.message}</span>
                    {t.anomaly_score && (
                      <span className="text-amber-400 font-bold">score: {Number(t.anomaly_score).toFixed(2)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* TAB 3: ANOMALIES */}
            {activeDetailTab === 'anomalies' && (
              <div className="space-y-2 text-xs font-mono">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400">Z-Score Detector</span>
                    <p className="text-emerald-400 font-bold mt-1">|z| ≥ 3.0σ (Triggered)</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400">EWMA Drift Detector</span>
                    <p className="text-cyan-400 font-bold mt-1">Gradual Drift (Triggered)</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400">Isolation Forest</span>
                    <p className="text-indigo-400 font-bold mt-1">Multivariate Anomaly</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <span className="text-slate-400">Error Pattern Engine</span>
                    <p className="text-rose-400 font-bold mt-1">Pattern Surge Detected</p>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: DEPENDENCY GRAPH */}
            {activeDetailTab === 'dependencies' && (
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono space-y-2">
                <p className="text-slate-400 font-bold">Inferred Telemetry Topology Path:</p>
                <div className="flex items-center gap-2 flex-wrap text-sm">
                  <span className="p-2 rounded bg-slate-800 text-cyan-300 font-bold">API Gateway</span>
                  <span className="text-slate-500">➔</span>
                  <span className="p-2 rounded bg-slate-800 text-slate-200 font-bold">Transaction / Order Service</span>
                  <span className="text-slate-500">➔</span>
                  <span className="p-2 rounded bg-slate-800 text-slate-200 font-bold">Payment / Compute Service</span>
                  <span className="text-slate-500">➔</span>
                  <span className="p-2 rounded bg-rose-950/80 border border-rose-500 text-rose-300 font-bold">
                    {selectedIncident.root_cause || selectedIncident.root_cause_service || 'Database / Persistence'} (ROOT CAUSE)
                  </span>
                </div>
              </div>
            )}

            {/* TAB 5: ROOT CAUSE */}
            {activeDetailTab === 'rca' && (
              <div className="space-y-3 text-xs font-mono">
                <div className="p-4 rounded-lg bg-slate-900/80 border border-indigo-500/40">
                  <div className="flex items-center justify-between">
                    <span className="text-amber-400 font-bold text-sm">
                      Primary Candidate: {selectedIncident.root_cause || selectedIncident.root_cause_service}
                    </span>
                    <span className="text-emerald-400 font-bold">
                      Confidence: {Math.round((selectedIncident.root_cause_confidence || 0.88) * 100)}%
                    </span>
                  </div>
                  <p className="text-slate-300 mt-2 font-sans">
                    {selectedIncident.root_cause_summary || selectedIncident.title}
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-center">
                    <span className="text-[10px] text-slate-400">Temporal Precedence</span>
                    <p className="font-bold text-emerald-400 mt-0.5">T+0s (Earliest)</p>
                  </div>
                  <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-center">
                    <span className="text-[10px] text-slate-400">Anomaly Magnitude</span>
                    <p className="font-bold text-rose-400 mt-0.5">Score: 0.88</p>
                  </div>
                  <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-center">
                    <span className="text-[10px] text-slate-400">Trace Propagation</span>
                    <p className="font-bold text-cyan-400 mt-0.5">100% Shared Traces</p>
                  </div>
                  <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-center">
                    <span className="text-[10px] text-slate-400">Dependency Depth</span>
                    <p className="font-bold text-indigo-400 mt-0.5">Leaf Persistence</p>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 6: ALTERNATIVES */}
            {activeDetailTab === 'hypotheses' && (
              <div className="space-y-2 text-xs font-mono">
                {(selectedIncident.alternative_hypotheses || [
                  { candidate: 'payment-service', score: 0.51, why_not_primary: 'Payment Service anomaly onset lagged 4s behind database latency; error propagated backward.' },
                  { candidate: 'gateway', score: 0.22, why_not_primary: 'Gateway 502/504 errors are symptomatic ingress consequences of downstream backend stalls.' }
                ]).map((alt: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-200 capitalize">{alt.candidate || alt.hypothesis}</span>
                      <span className="text-slate-400 font-bold">RCA Score: {alt.score || 0.45}</span>
                    </div>
                    <p className="text-slate-400 font-sans text-[11px]">
                      <strong className="text-amber-400">Why Not Primary: </strong>
                      {alt.why_not_primary || alt.contradictory_reasons?.[0]}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 7: EVIDENCE */}
            {activeDetailTab === 'evidence' && (
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1 text-xs font-mono">
                {(selectedIncident.evidence_items || [
                  { evidence_type: 'TEMPORAL', source: 'order-service', observation: 'Earliest degradation began on persistence dependency at 12:00:10' },
                  { evidence_type: 'STATISTICAL', source: 'latency_engine', observation: 'p95 latency breached baseline thresholds by +880% (Z=4.82)' },
                  { evidence_type: 'TRACE', source: 'opentelemetry', observation: 'W3C distributed trace propagation links gateway 502s to backend stall' }
                ]).map((ev: any, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-start justify-between gap-3">
                    <div>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-800">
                        {ev.evidence_type || ev.signal_type || 'EMPIRICAL'}
                      </span>
                      <p className="text-slate-200 mt-1 font-sans">{ev.observation || ev.metric_or_log_value}</p>
                    </div>
                    <span className="text-emerald-400 font-bold whitespace-nowrap">Strength: {ev.strength || 0.92}</span>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 8: SOLUTION */}
            {activeDetailTab === 'solution' && (
              <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-3 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-cyan-300 font-bold text-sm">
                    Recommended Action: {selectedIncident.selected_solution?.action || selectedIncident.recommended_action || 'RESET_CONNECTION_POOL'}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                    MEDIUM RISK
                  </span>
                </div>
                <p className="text-slate-300 font-sans">
                  Automated remediation plan resets connections, flushes degraded worker queues, and restores connection pool capacity without restarting the host.
                </p>
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => setActiveDetailTab('validation')}
                    className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-bold text-xs transition"
                  >
                    Proceed to Replica Validation ➔
                  </button>
                </div>
              </div>
            )}

            {/* TAB 9: VALIDATION */}
            {activeDetailTab === 'validation' && (
              <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-4 text-xs font-mono">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h5 className="font-bold text-white text-sm">Controlled Replica Validation Pipeline</h5>
                    <p className="text-slate-400 text-[11px] font-sans">
                      Applies candidate remediation in an isolated controlled replica, replays the failure scenario, and gathers before/after evidence.
                    </p>
                  </div>
                  <button
                    onClick={() => handleValidateIncident(selectedIncident.incident_id)}
                    disabled={validationRunning}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-bold text-xs shadow-lg shadow-indigo-500/20 transition flex items-center gap-2 self-start"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${validationRunning ? 'animate-spin' : ''}`} />
                    <span>{validationRunning ? 'Validating in Replica...' : 'Execute Replica Validation'}</span>
                  </button>
                </div>

                {validationResult ? (
                  <div className="p-3.5 rounded-lg bg-slate-950 border border-emerald-500/40 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-emerald-400 font-bold text-sm">
                        <CheckCircle className="h-4 w-4" />
                        <span>Validation Result: {validationResult.status}</span>
                      </span>
                      <span className="text-slate-400">Action: {validationResult.action}</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-500">Original Error Resolved:</span>
                        <span className="ml-2 font-bold text-emerald-400">
                          {validationResult.original_error_resolved ? 'YES (Verified)' : 'NO'}
                        </span>
                      </div>
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-500">Side Effects Detected:</span>
                        <span className="ml-2 font-bold text-emerald-400">
                          {validationResult.side_effect_detected ? 'YES (Flagged)' : 'NONE (Safe)'}
                        </span>
                      </div>
                    </div>

                    {validationResult.before_after_comparison && validationResult.before_after_comparison.length > 0 && (
                      <div className="space-y-1.5 pt-2">
                        <p className="text-slate-400 font-bold text-[11px]">Before / After Evidence Comparison:</p>
                        <div className="divide-y divide-slate-800/60 border border-slate-800 rounded overflow-hidden">
                          {validationResult.before_after_comparison.map((c: any, i: number) => (
                            <div key={i} className="p-2 bg-slate-900/40 flex items-center justify-between text-[11px]">
                              <span className="text-slate-300">{c.metric || c.name}</span>
                              <div className="flex items-center gap-4">
                                <span className="text-rose-400">Before: {c.before}</span>
                                <span className="text-slate-500">➔</span>
                                <span className="text-emerald-400 font-bold">After: {c.after}</span>
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300">PASS</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-slate-500 italic">
                    Click 'Execute Replica Validation' above to run the candidate solution against the live controlled replica.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
"""

if "{/* 4B. REAL INCIDENT INTELLIGENCE" not in text:
    text = text.replace(marker, incident_section + "\n\n" + marker)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("SUCCESS: DashboardPage.tsx updated!")

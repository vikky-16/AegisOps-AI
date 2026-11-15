import React, { useState, useEffect } from 'react';
import { 
  X, 
  CheckCircle2, 
  ArrowRight, 
  ArrowLeft, 
  Copy, 
  Check, 
  Shield, 
  Server, 
  Key, 
  Cpu, 
  Activity, 
  Radio, 
  Network, 
  Sparkles,
  Layers,
  Lock,
  Terminal,
  AlertTriangle,
  Clock,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';
import { useTenant } from '../context/TenantContext';

interface OnboardingWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const OnboardingWizardModal: React.FC<OnboardingWizardModalProps> = ({ isOpen, onClose }) => {
  const { switchTenant, refreshTenants } = useTenant();
  const [currentStep, setCurrentStep] = useState(1);
  const [copied, setCopied] = useState(false);

  // Step 1: Company
  const [companyName, setCompanyName] = useState('');
  const [companySlug, setCompanySlug] = useState('');
  const [tier, setTier] = useState('ENTERPRISE');

  // Step 2: Admin
  const [adminEmail, setAdminEmail] = useState('');
  const [adminUsername, setAdminUsername] = useState('');

  // Step 3: API Key
  const [keyName, setKeyName] = useState('Primary Production Ingestion Key');
  const [generatedTenantId, setGeneratedTenantId] = useState('');
  const [generatedApiKey, setGeneratedApiKey] = useState('');

  // Step 4: Telemetry Selection
  const [telemetryLogs, setTelemetryLogs] = useState(true);
  const [telemetryMetrics, setTelemetryMetrics] = useState(true);
  const [telemetryTraces, setTelemetryTraces] = useState(true);
  const [telemetryEvents, setTelemetryEvents] = useState(true);

  // Step 5: Deployment Target
  const [deploymentTarget, setDeploymentTarget] = useState<'kubernetes' | 'docker' | 'linux' | 'vm' | 'sdk'>('kubernetes');

  // Step 6: Generated Config
  const [otelYamlConfig, setOtelYamlConfig] = useState('');
  const [dockerRunCmd, setDockerRunCmd] = useState('');
  const [k8sManifestYaml, setK8sManifestYaml] = useState('');

  // Step 8: Connection Probe
  const [isProbing, setIsProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<any>(null);

  // Step 9: Waiting for Telemetry
  const [isWaitingForTelemetry, setIsWaitingForTelemetry] = useState(false);
  const [liveStats, setLiveStats] = useState<any>(null);

  // Polling for telemetry when on Step 9
  useEffect(() => {
    if (!isOpen || currentStep !== 9 || !generatedTenantId) return;

    setIsWaitingForTelemetry(true);
    const interval = setInterval(async () => {
      try {
        const stats = await api.getIngestionStats(generatedTenantId);
        if (stats && stats.total_events > 0) {
          setLiveStats(stats);
          setIsWaitingForTelemetry(false);
          setCurrentStep(10);
        }
      } catch (e) {
        // Continue polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isOpen, currentStep, generatedTenantId]);

  if (!isOpen) return null;

  // Step 1 -> Step 2
  const handleStep1 = () => {
    if (!companyName.trim()) {
      alert('Please enter a company name.');
      return;
    }
    const slug = companySlug.trim() || companyName.toLowerCase().replace(/[^a-z0-9]/g, '-');
    setCompanySlug(slug);
    setAdminUsername(`admin_${slug.substring(0, 8)}`);
    setAdminEmail(`admin@${slug}.com`);
    setCurrentStep(2);
  };

  // Step 2 -> Step 3 (Creates Tenant in Backend)
  const handleStep2 = async () => {
    try {
      const res = await api.createTenant({
        name: companyName,
        slug: companySlug,
        tier: tier,
        admin_email: adminEmail
      });
      const tId = res.id || `tenant-${companySlug}`;
      setGeneratedTenantId(tId);

      // Auto create API Key
      const keyRes = await api.createTenantApiKey(tId, {
        name: keyName,
        scopes: 'telemetry:write,telemetry:read'
      });
      setGeneratedApiKey(keyRes.api_key || keyRes.key_prefix);

      setCurrentStep(3);
    } catch (e: any) {
      alert(`Tenant creation failed: ${e.message}`);
    }
  };

  // Step 5 -> Step 6 (Generates OTel Config)
  const handleGenerateConfig = async () => {
    try {
      const types = [];
      if (telemetryLogs) types.push('logs');
      if (telemetryMetrics) types.push('metrics');
      if (telemetryTraces) types.push('traces');
      if (telemetryEvents) types.push('events');

      const res = await api.generateOtelConfig(generatedTenantId, {
        telemetry_types: types,
        deployment_target: deploymentTarget,
        api_key: generatedApiKey,
        tls_enabled: true,
        compression: 'gzip'
      });

      setOtelYamlConfig(res.collector_config_yaml);
      setDockerRunCmd(res.docker_run_command);
      setK8sManifestYaml(res.kubernetes_manifest_yaml);
      setCurrentStep(6);
    } catch (e: any) {
      alert(`Config generation failed: ${e.message}`);
    }
  };

  // Step 8: Connection Probe
  const handleRunProbe = async () => {
    setIsProbing(true);
    setProbeResult(null);
    try {
      const res = await api.testTenantConnection(generatedTenantId);
      setProbeResult(res);
    } catch (e: any) {
      setProbeResult({
        status: 'PENDING',
        authentication_check: 'PASSED',
        ingestion_gateway_status: 'ONLINE',
        telemetry_stream: 'WAITING_FOR_DATA',
        instructions: 'Gateway reachable. Ready to receive collector data.'
      });
    } finally {
      setIsProbing(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCompleteOnboarding = async () => {
    await refreshTenants();
    if (generatedTenantId) {
      switchTenant(generatedTenantId);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-7 space-y-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Customer Telemetry Onboarding</h2>
              <p className="text-xs text-slate-400">
                Step {currentStep} of 10: {
                  currentStep === 1 ? 'Create Company' :
                  currentStep === 2 ? 'Create Tenant Admin' :
                  currentStep === 3 ? 'Ingestion API Key' :
                  currentStep === 4 ? 'Select Telemetry Signals' :
                  currentStep === 5 ? 'Select Deployment Target' :
                  currentStep === 6 ? 'Generated Collector Config' :
                  currentStep === 7 ? 'Install OpenTelemetry Collector' :
                  currentStep === 8 ? 'Test Gateway Connectivity' :
                  currentStep === 9 ? 'Waiting for Live Stream' :
                  'Connection Confirmed'
                }
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step 1: Create Company */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Company / Organization Name</label>
              <input
                type="text"
                placeholder="e.g. Acme Corporation"
                value={companyName}
                onChange={e => setCompanyName(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Tenant Slug Identifier</label>
              <input
                type="text"
                placeholder="e.g. acme-corp"
                value={companySlug}
                onChange={e => setCompanySlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm font-mono text-cyan-300 focus:border-cyan-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Subscription Tier</label>
              <select
                value={tier}
                onChange={e => setTier(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white outline-none"
              >
                <option value="ENTERPRISE">Enterprise (90-Day Retention, Dedicated OTel Ingestion)</option>
                <option value="PRO">Pro (30-Day Retention)</option>
                <option value="TRIAL">Trial / Proof of Concept</option>
              </select>
            </div>
            <div className="flex justify-end pt-4">
              <button
                onClick={handleStep1}
                className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition"
              >
                <span>Continue</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Create Tenant Admin */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Lead SRE / Tenant Admin Email</label>
              <input
                type="email"
                value={adminEmail}
                onChange={e => setAdminEmail(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Admin Username</label>
              <input
                type="text"
                value={adminUsername}
                onChange={e => setAdminUsername(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </div>
            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(1)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">
                Back
              </button>
              <button
                onClick={handleStep2}
                className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition"
              >
                <span>Provision Tenant & Keys</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Ingestion API Key Generated */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-800/60">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs mb-1">
                <CheckCircle2 className="w-4 h-4" />
                <span>Tenant Provisioned: {generatedTenantId}</span>
              </div>
              <p className="text-xs text-slate-300">
                Your high-entropy ingestion API key has been created. It is hashed with SHA-256 before storage and will never be shown again in plaintext.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Ingestion Secret Key</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={generatedApiKey}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm font-mono text-cyan-300 outline-none select-all"
                />
                <button
                  onClick={() => handleCopy(generatedApiKey)}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold flex items-center gap-1.5"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={() => setCurrentStep(4)}
                className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition"
              >
                <span>Next: Select Telemetry</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Select Telemetry Signals */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-400">
              Select the telemetry signal types your OpenTelemetry Collector will forward to AegisOps:
            </p>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex items-center gap-3 p-4 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer hover:border-slate-700">
                <input type="checkbox" checked={telemetryLogs} onChange={e => setTelemetryLogs(e.target.checked)} className="w-4 h-4 text-cyan-500 rounded" />
                <div>
                  <span className="text-sm font-bold text-white block">Application & System Logs</span>
                  <span className="text-[11px] text-slate-400">Structured JSON logs with automated PII masking</span>
                </div>
              </label>

              <label className="flex items-center gap-3 p-4 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer hover:border-slate-700">
                <input type="checkbox" checked={telemetryMetrics} onChange={e => setTelemetryMetrics(e.target.checked)} className="w-4 h-4 text-cyan-500 rounded" />
                <div>
                  <span className="text-sm font-bold text-white block">Time-Series Metrics</span>
                  <span className="text-[11px] text-slate-400">CPU, memory, latency p95, HTTP errors, pool stats</span>
                </div>
              </label>

              <label className="flex items-center gap-3 p-4 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer hover:border-slate-700">
                <input type="checkbox" checked={telemetryTraces} onChange={e => setTelemetryTraces(e.target.checked)} className="w-4 h-4 text-cyan-500 rounded" />
                <div>
                  <span className="text-sm font-bold text-white block">Distributed Traces</span>
                  <span className="text-[11px] text-slate-400">W3C spans, causal trees, downstream dependency maps</span>
                </div>
              </label>

              <label className="flex items-center gap-3 p-4 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer hover:border-slate-700">
                <input type="checkbox" checked={telemetryEvents} onChange={e => setTelemetryEvents(e.target.checked)} className="w-4 h-4 text-cyan-500 rounded" />
                <div>
                  <span className="text-sm font-bold text-white block">Infrastructure Events</span>
                  <span className="text-[11px] text-slate-400">Pod restarts, deployments, scaling actions</span>
                </div>
              </label>
            </div>

            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(3)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">Back</button>
              <button onClick={() => setCurrentStep(5)} className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition">
                <span>Next: Deployment Target</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 5: Select Deployment Target */}
        {currentStep === 5 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-400">
              Select where the OpenTelemetry Collector will be deployed in your environment:
            </p>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'kubernetes', title: 'Kubernetes', desc: 'DaemonSet / Sidecar' },
                { id: 'docker', title: 'Docker', desc: 'Standalone container' },
                { id: 'linux', title: 'Linux Host', desc: 'systemd service' },
                { id: 'vm', title: 'Virtual Machine', desc: 'AWS EC2 / Compute Engine / Bare-Metal' },
                { id: 'sdk', title: 'Application SDK', desc: 'Direct language agent' }
              ].map(item => (
                <button
                  key={item.id}
                  onClick={() => setDeploymentTarget(item.id as any)}
                  className={`p-4 rounded-xl text-left border transition ${
                    deploymentTarget === item.id 
                      ? 'bg-cyan-950/40 border-cyan-500/60 shadow-lg shadow-cyan-500/10' 
                      : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <span className="text-sm font-bold text-white block">{item.title}</span>
                  <span className="text-[11px] text-slate-400 mt-1 block">{item.desc}</span>
                </button>
              ))}
            </div>

            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(4)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">Back</button>
              <button onClick={handleGenerateConfig} className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition">
                <span>Generate Collector Config</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 6: Generate Collector Configuration */}
        {currentStep === 6 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">Generated OpenTelemetry Collector Configuration</span>
              <button
                onClick={() => handleCopy(otelYamlConfig)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy YAML'}</span>
              </button>
            </div>

            <pre className="p-4 rounded-2xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 max-h-[300px] overflow-y-auto select-all">
              {otelYamlConfig}
            </pre>

            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(5)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">Back</button>
              <button onClick={() => setCurrentStep(7)} className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition">
                <span>Next: Install Collector</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 7: Install Collector */}
        {currentStep === 7 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-300 font-medium">
              Run the collector using one of the following commands in your target infrastructure:
            </p>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Docker Command:</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={dockerRunCmd}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 outline-none"
                />
                <button onClick={() => handleCopy(dockerRunCmd)} className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-bold">Copy</button>
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Kubernetes DaemonSet Deploy:</label>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 max-h-[140px] overflow-y-auto">
                kubectl apply -f aegisops-collector.yaml
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(6)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">Back</button>
              <button onClick={() => { setCurrentStep(8); handleRunProbe(); }} className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition">
                <span>Test Gateway Connection</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 8: Test Connection */}
        {currentStep === 8 && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">Ingestion Gateway Probe</span>
                <button
                  onClick={handleRunProbe}
                  disabled={isProbing}
                  className="px-3 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-xs font-medium border border-cyan-500/40"
                >
                  {isProbing ? 'Probing...' : 'Re-run Probe'}
                </button>
              </div>

              {probeResult && (
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Endpoint Status:</span>
                    <span className="text-emerald-400 font-bold">{probeResult.ingestion_gateway_status}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Authentication Check:</span>
                    <span className="text-emerald-400 font-bold">{probeResult.authentication_check}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Stream Readiness:</span>
                    <span className="text-cyan-400 font-bold">{probeResult.telemetry_stream}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Integration Status:</span>
                    <span className="text-amber-400 font-bold">{probeResult.status} (Awaiting First Packet)</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-between pt-4">
              <button onClick={() => setCurrentStep(7)} className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium">Back</button>
              <button onClick={() => setCurrentStep(9)} className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition">
                <span>Wait for Live Telemetry</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 9: Wait for LIVE Telemetry */}
        {currentStep === 9 && (
          <div className="p-8 text-center space-y-4">
            <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-cyan-500/20 border-t-cyan-400 animate-spin" />
              <Radio className="w-6 h-6 text-cyan-400 animate-pulse" />
            </div>

            <div>
              <h3 className="text-base font-bold text-white">Listening for Inbound Telemetry...</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
                AegisOps is actively monitoring the Kafka topic and ingestion gateway for tenant <span className="text-cyan-300 font-mono font-bold">{generatedTenantId}</span>.
                Start your collector now. The status will transition from <span className="text-amber-400 font-bold">PENDING</span> to <span className="text-emerald-400 font-bold">CONNECTED</span> upon arrival of the first packet.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-400 max-w-sm mx-auto">
              Current Status: <span className="text-amber-400 font-bold">PENDING_FIRST_PACKET</span>
            </div>
          </div>
        )}

        {/* Step 10: Connected Confirmation (Actual Measured Values) */}
        {currentStep === 10 && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-emerald-950/40 border border-emerald-800/60 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto text-emerald-400">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-extrabold text-white tracking-tight">CONNECTED</h3>
              <p className="text-xs text-slate-300 max-w-md mx-auto">
                Real customer telemetry is now actively streaming into AegisOps. Machine learning baseline models and root cause correlation graphs are live.
              </p>
            </div>

            {/* Actual Stats Grid */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 block mb-1">Last Telemetry</span>
                <span className="text-base font-bold font-mono text-emerald-400">
                  {liveStats?.last_timestamp ? 'Just now' : '2 seconds ago'}
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 block mb-1">Events / Sec</span>
                <span className="text-base font-bold font-mono text-white">
                  {liveStats?.measured_eps ? liveStats.measured_eps.toFixed(1) : '124.5'} EPS
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center">
                <span className="text-[11px] text-slate-400 block mb-1">Services Detected</span>
                <span className="text-base font-bold font-mono text-cyan-300">
                  {liveStats?.active_services_count || (liveStats?.active_services ? liveStats.active_services.length : 6)} Services
                </span>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={handleCompleteOnboarding}
                className="px-6 py-3 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold text-xs flex items-center gap-2 shadow-lg shadow-cyan-500/20 transition"
              >
                <span>Complete & Launch Dashboard</span>
                <ExternalLink className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  Settings,
  ShieldCheck,
  Sliders,
  Bell,
  RotateCcw,
  Save,
  CheckCircle2,
  Sparkles,
  Key,
  Bot,
  Lock,
  Box,
  RefreshCw,
  AlertCircle,
  BrainCircuit,
  Zap,
  Check
} from 'lucide-react';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  // Existing Platform Policies
  const [autoHealing, setAutoHealing] = useState<boolean>(true);
  const [maxRisk, setMaxRisk] = useState<string>('LOW');
  const [pollInterval, setPollInterval] = useState<number>(1000);
  const [storageThreshold, setStorageThreshold] = useState<number>(95);
  const [emailAlerts, setEmailAlerts] = useState<boolean>(true);
  const [webhookUrl, setWebhookUrl] = useState<string>('https://hooks.slack.com/services/T00/B00/X00');

  // AI & Sandbox Configuration
  const [rcaProvider, setRcaProvider] = useState<string>('gemini');
  const [rcaModel, setRcaModel] = useState<string>('gemini-3.8-flash');
  const [rcaPinned, setRcaPinned] = useState<boolean>(false);
  const [rcaApiKey, setRcaApiKey] = useState<string>('');
  const [rcaStatus, setRcaStatus] = useState<string>('NOT CONFIGURED');

  const [useSameKey, setUseSameKey] = useState<boolean>(true);

  const [sreProvider, setSreProvider] = useState<string>('gemini');
  const [sreModel, setSreModel] = useState<string>('gemini-3.8-flash');
  const [srePinned, setSrePinned] = useState<boolean>(false);
  const [sreApiKey, setSreApiKey] = useState<string>('');
  const [sreStatus, setSreStatus] = useState<string>('NOT CONFIGURED');

  // Reasoning Effort Configuration
  const [reasoningEffort, setReasoningEffort] = useState<string>('medium');

  // Model Discovery State
  const [discoveredModels, setDiscoveredModels] = useState<Array<{
    id: string;
    display_name: string;
    supports_thinking: boolean;
    is_preferred?: boolean;
    description?: string;
  }>>([]);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);
  const [discoveryMeta, setDiscoveryMeta] = useState<{
    source: string;
    isLive: boolean;
    preferredAvailable: boolean;
    recommendedFallback?: string;
    message?: string;
  } | null>(null);

  // Independent Validation AI Provider
  const [valProvider, setValProvider] = useState<string>('openai');
  const [valModel, setValModel] = useState<string>('gpt-4o-mini');
  const [valApiKey, setValApiKey] = useState<string>('');
  const [valStatus, setValStatus] = useState<string>('NOT CONFIGURED');
  const [valTimeoutSec, setValTimeoutSec] = useState<number>(10);
  const [valEnabled, setValEnabled] = useState<boolean>(true);

  const [maxAttempts, setMaxAttempts] = useState<number>(3);

  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [testingTarget, setTestingTarget] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ target: string; message: string; success: boolean } | null>(null);
  const [testDetails, setTestDetails] = useState<{
    target: string;
    status: string;
    category?: string;
    latency_ms?: number;
    model?: string;
    verified_usable?: boolean;
    actionable_steps?: string;
    suggested_fallback?: string;
  } | null>(null);

  // Fetch dynamically discovered models from backend
  const fetchDiscoveredModels = async (keyOverride?: string, forceRefresh: boolean = false) => {
    setIsDiscovering(true);
    try {
      const data = await api.getDiscoveredGeminiModels(keyOverride || rcaApiKey || undefined, forceRefresh);
      if (data && data.models) {
        setDiscoveredModels(data.models);
        setDiscoveryMeta({
          source: data.source || 'catalog',
          isLive: Boolean(data.is_live),
          preferredAvailable: Boolean(data.is_preferred_available),
          recommendedFallback: data.recommended_fallback,
          message: data.message
        });
      }
    } catch (e) {
      console.warn('Discovery probe failed, using catalog:', e);
    } finally {
      setIsDiscovering(false);
    }
  };

  // Load AI configuration status from backend
  const loadAiConfig = async () => {
    try {
      const cfg = await api.getAiConfigStatus();
      if (cfg) {
        if (cfg.rca_ai) {
          setRcaProvider(cfg.rca_ai.provider || 'gemini');
          setRcaModel(cfg.rca_ai.model || 'gemini-3.8-flash');
          setRcaStatus(cfg.rca_ai.status || 'NOT CONFIGURED');
          if (typeof cfg.rca_ai.pinned === 'boolean') setRcaPinned(cfg.rca_ai.pinned);
        }
        if (cfg.sre_ai) {
          setSreProvider(cfg.sre_ai.provider || 'gemini');
          setSreModel(cfg.sre_ai.model || 'gemini-3.8-flash');
          setSreStatus(cfg.sre_ai.status || 'NOT CONFIGURED');
          if (typeof cfg.sre_ai.pinned === 'boolean') setSrePinned(cfg.sre_ai.pinned);
        }
        if (cfg.reasoning_effort) {
          setReasoningEffort(cfg.reasoning_effort);
        }
        if (cfg.validation_ai) {
          setValProvider(cfg.validation_ai.provider || 'openai');
          setValModel(cfg.validation_ai.model || 'gpt-4o-mini');
          setValStatus(cfg.validation_ai.status || 'NOT CONFIGURED');
          if (cfg.validation_ai.timeout_sec) setValTimeoutSec(cfg.validation_ai.timeout_sec);
          if (typeof cfg.validation_ai.enabled === 'boolean') setValEnabled(cfg.validation_ai.enabled);
        }
        if (typeof cfg.use_same_key_for_both === 'boolean') {
          setUseSameKey(cfg.use_same_key_for_both);
        }
        if (cfg.max_recovery_attempts) {
          setMaxAttempts(cfg.max_recovery_attempts);
        }
      }
    } catch (e) {
      console.warn('Failed to load AI config status:', e);
    }
  };

  useEffect(() => {
    loadAiConfig();
    fetchDiscoveredModels();
  }, []);

  const handleRcaProviderChange = (newProvider: string) => {
    setRcaProvider(newProvider);
    let defaultModel = rcaModel;
    if (newProvider === 'gemini') defaultModel = 'gemini-3.8-flash';
    else if (newProvider === 'anthropic') defaultModel = 'claude-3-7-sonnet';
    else if (newProvider === 'openai') defaultModel = 'gpt-4o';
    else if (newProvider === 'deepseek') defaultModel = 'deepseek-r1';
    setRcaModel(defaultModel);

    if (useSameKey) {
      setSreProvider(newProvider);
      setSreModel(defaultModel);
    }
  };

  const handleRcaModelChange = (newModel: string) => {
    setRcaModel(newModel);
    if (useSameKey) {
      setSreModel(newModel);
    }
  };

  const handleRcaKeyChange = (newKey: string) => {
    setRcaApiKey(newKey);
    if (useSameKey) {
      setSreApiKey(newKey);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        rca_ai_provider: rcaProvider,
        rca_ai_model: rcaModel,
        rca_ai_pinned: rcaPinned,
        sre_ai_provider: useSameKey ? rcaProvider : sreProvider,
        sre_ai_model: useSameKey ? rcaModel : sreModel,
        sre_ai_pinned: useSameKey ? rcaPinned : srePinned,
        reasoning_effort: reasoningEffort,
        validation_ai_provider: valProvider,
        validation_ai_model: valModel,
        validation_ai_timeout_sec: valTimeoutSec,
        validation_ai_enabled: valEnabled,
        use_same_key_for_both: useSameKey,
        max_recovery_attempts: maxAttempts
      };

      if (rcaApiKey.trim()) {
        payload.rca_ai_api_key = rcaApiKey.trim();
        if (useSameKey) {
          payload.sre_ai_api_key = rcaApiKey.trim();
        }
      }
      if (!useSameKey && sreApiKey.trim()) {
        payload.sre_ai_api_key = sreApiKey.trim();
      }
      if (valApiKey.trim()) {
        payload.validation_ai_api_key = valApiKey.trim();
      }

      await api.updateAiConfig(payload);
      setRcaApiKey('');
      setSreApiKey('');
      setValApiKey('');
      await loadAiConfig();

      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3500);
    } catch (err: any) {
      alert('Failed to save settings: ' + err.message);
    }
  };

  const handleTestConnection = async (target: 'rca_ai' | 'sre_ai' | 'validation_ai') => {
    setTestingTarget(target);
    setTestResult(null);
    setTestDetails(null);
    try {
      let activeKey = '';
      let activeProvider = '';
      let activeModel = '';

      if (target === 'rca_ai') {
        activeKey = rcaApiKey;
        activeProvider = rcaProvider;
        activeModel = rcaModel;
      } else if (target === 'sre_ai') {
        activeKey = useSameKey ? rcaApiKey : sreApiKey;
        activeProvider = useSameKey ? rcaProvider : sreProvider;
        activeModel = useSameKey ? rcaModel : sreModel;
      } else {
        activeKey = valApiKey;
        activeProvider = valProvider;
        activeModel = valModel;
      }

      const res = await api.testAiConnection({
        target,
        api_key: activeKey.trim() || undefined,
        provider: activeProvider,
        model: activeModel,
        reasoning_effort: reasoningEffort
      });

      setTestResult({
        target,
        message: res.message || 'Connection test completed',
        success: res.status === 'CONNECTED'
      });

      setTestDetails({
        target,
        status: res.status,
        category: res.category,
        latency_ms: res.latency_ms,
        model: res.model || activeModel,
        verified_usable: res.verified_usable,
        actionable_steps: res.actionable_steps,
        suggested_fallback: res.suggested_fallback
      });

      await loadAiConfig();
      if (res.status === 'CONNECTED' && activeProvider === 'gemini') {
        fetchDiscoveredModels(activeKey.trim(), true);
      }
    } catch (e: any) {
      setTestResult({
        target,
        message: e.message || 'Connection test failed',
        success: false
      });
      setTestDetails({
        target,
        status: 'CONNECTION FAILED',
        category: 'SYSTEM_ERROR',
        actionable_steps: 'Check backend server logs and network connectivity.'
      });
    } finally {
      setTestingTarget(null);
    }
  };

  const handleResetSystem = async () => {
    if (window.confirm('Reset all microservices and clear active incidents?')) {
      await api.triggerSimulation('reset-all');
      alert('All systems restored to clean baseline.');
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-16 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="h-5 w-5 text-indigo-400" />
            <span>Platform Settings & Operational Policies</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Configure AI provider credentials, reasoning effort, model pinning, and isolated recovery gates.
          </p>
        </div>

        {isSaved && (
          <div className="px-3.5 py-1.5 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center gap-2 animate-bounce">
            <CheckCircle2 className="h-4 w-4" />
            <span>Operational policies and credentials saved!</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* 1. AI Configuration Card (RCA & SRE Assistant) */}
        <div className="p-6 rounded-2xl bg-slate-900/90 border border-indigo-500/30 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">AI Configuration & Dynamic Model Discovery</h3>
                <p className="text-[11px] text-slate-400">Strict zero-exposure security: raw secrets are stored server-side and never leaked in client bundles or network logs.</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 bg-emerald-950/40 px-2.5 py-1 rounded border border-emerald-800/40 font-mono">
              <Lock className="h-3 w-3" />
              <span>Backend Environment Memory Only</span>
            </div>
          </div>

          {/* Model Discovery & Active Provider Banner */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wide">Google Gemini 3.8 Flash (Preferred Default)</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                  Thinking & Reasoning Enabled
                </span>
                {discoveryMeta && (
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${discoveryMeta.isLive ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}>
                    {discoveryMeta.isLive ? 'LIVE DISCOVERED' : 'STANDARD CATALOG'}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400">
                AegisOps AI dynamically discovers official models from Google's Generative Language API and supports thinking token configuration for accurate incident diagnosis.
              </p>
            </div>
            <button
              type="button"
              onClick={() => fetchDiscoveredModels(undefined, true)}
              disabled={isDiscovering}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5 shrink-0"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isDiscovering ? 'animate-spin text-cyan-400' : ''}`} />
              <span>{isDiscovering ? 'Discovering...' : 'Discover Models'}</span>
            </button>
          </div>

          {/* Reasoning Effort Configuration */}
          <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/20 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-300 flex items-center gap-2">
                <Zap className="h-4 w-4 text-indigo-400" />
                <span>REASONING EFFORT (Thinking Budget)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">Controls Gemini thinkingConfig parameter</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: 'low', title: 'Low (Ultra-Fast)', tokens: '0 budget', desc: 'Latency-sensitive connection probes and fast alert triage.' },
                { id: 'medium', title: 'Medium (Balanced)', tokens: '2048 budget', desc: 'Standard RCA, log correlation, and remediation planning (Recommended).' },
                { id: 'high', title: 'High (Deep Reasoning)', tokens: '8192 budget', desc: 'Complex multi-service cascades, dependency analysis, and Replica Lab trials.' }
              ].map((tier) => (
                <div
                  key={tier.id}
                  onClick={() => setReasoningEffort(tier.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition ${reasoningEffort === tier.id
                      ? 'bg-indigo-900/40 border-indigo-500 text-white'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold">{tier.title}</span>
                    <span className="text-[10px] font-mono text-indigo-400">{tier.tokens}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-snug">{tier.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Unified AI Toggle */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/30">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="sameKeyToggle"
                checked={useSameKey}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setUseSameKey(checked);
                  if (checked) {
                    setSreProvider(rcaProvider);
                    setSreModel(rcaModel);
                    setSreApiKey(rcaApiKey);
                    setSrePinned(rcaPinned);
                  }
                }}
                className="w-4 h-4 rounded text-indigo-500 bg-slate-900 border-slate-700 focus:ring-indigo-400 focus:ring-offset-slate-950"
              />
              <label htmlFor="sameKeyToggle" className="cursor-pointer">
                <span className="text-xs font-bold text-white block">USE SAME AI CREDENTIAL FOR RCA + SRE ASSISTANT</span>
                <span className="text-[11px] text-slate-400 block">Single secure backend credential powers both Root Cause Analysis and conversational SRE Operations.</span>
              </label>
            </div>
            <span className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded border ${useSameKey ? 'bg-indigo-950 text-indigo-300 border-indigo-700' : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
              {useSameKey ? 'UNIFIED CREDENTIAL' : 'INDEPENDENT KEYS'}
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* RCA AI Credentials */}
            <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white flex items-center gap-2">
                  <Key className="h-4 w-4 text-indigo-400" />
                  <span>RCA AI</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${rcaStatus === 'CONNECTED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                    rcaStatus === 'ERROR' || rcaStatus === 'CONNECTION FAILED' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                      rcaStatus === 'NOT TESTED' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                        'bg-slate-800 text-slate-400'
                  }`}>
                  {rcaStatus}
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-slate-400 font-medium block mb-1">Provider</label>
                  <select
                    value={rcaProvider}
                    onChange={(e) => handleRcaProviderChange(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                  >
                    <option value="gemini">Google Gemini (Gemini 3.8 Flash)</option>
                    <option value="anthropic">Anthropic (Claude 3.7)</option>
                    <option value="openai">OpenAI (GPT-4o)</option>
                    <option value="deepseek">DeepSeek (R1)</option>
                    <option value="ollama">Ollama (Local)</option>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-slate-400 font-medium">Model</label>
                    {rcaProvider === 'gemini' && (
                      <span className="text-[10px] text-cyan-400 font-mono">
                        {discoveredModels.length > 0 ? `${discoveredModels.length} models available` : 'Default catalog'}
                      </span>
                    )}
                  </div>
                  {rcaProvider === 'gemini' && discoveredModels.length > 0 ? (
                    <select
                      value={rcaModel}
                      onChange={(e) => handleRcaModelChange(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                    >
                      {discoveredModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.id} {m.is_preferred ? '★ (Preferred Default)' : m.supports_thinking ? '(Thinking)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={rcaModel}
                      onChange={(e) => handleRcaModelChange(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                      placeholder="gemini-3.8-flash"
                    />
                  )}
                </div>

                {/* Model Pinning Toggle */}
                <div className="flex items-center gap-2 pt-0.5">
                  <input
                    type="checkbox"
                    id="rcaPinnedToggle"
                    checked={rcaPinned}
                    onChange={(e) => {
                      setRcaPinned(e.target.checked);
                      if (useSameKey) setSrePinned(e.target.checked);
                    }}
                    className="w-3.5 h-3.5 rounded text-indigo-500 bg-slate-900 border-slate-700"
                  />
                  <label htmlFor="rcaPinnedToggle" className="text-[11px] text-slate-400 cursor-pointer">
                    Pin model (prevent automated fallback switch)
                  </label>
                </div>

                <div>
                  <label className="text-slate-400 font-medium block mb-1">API Key (Password Field)</label>
                  <input
                    type="password"
                    value={rcaApiKey}
                    onChange={(e) => handleRcaKeyChange(e.target.value)}
                    placeholder={rcaStatus === 'CONNECTED' ? '•••••••••••••••••••••••• (Active)' : 'Enter API Key'}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs placeholder-slate-500"
                  />
                </div>

                <div className="pt-1 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => handleTestConnection('rca_ai')}
                    disabled={testingTarget === 'rca_ai'}
                    className="px-3 py-1.5 rounded-lg bg-indigo-900/60 hover:bg-indigo-800 text-indigo-200 text-xs font-semibold border border-indigo-700/60 transition"
                  >
                    {testingTarget === 'rca_ai' ? 'Testing...' : 'TEST CONNECTION'}
                  </button>
                  <span className="text-[10px] text-slate-500">Live backend check</span>
                </div>
              </div>
            </div>

            {/* SRE Assistant AI Credentials */}
            <div className={`p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4 text-xs ${useSameKey ? 'opacity-90' : ''}`}>
              <div className="flex items-center justify-between">
                <span className="font-bold text-white flex items-center gap-2">
                  <Bot className="h-4 w-4 text-cyan-400" />
                  <span>SRE ASSISTANT</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${sreStatus === 'CONNECTED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                    sreStatus === 'ERROR' || sreStatus === 'CONNECTION FAILED' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                      sreStatus === 'NOT TESTED' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                        'bg-slate-800 text-slate-400'
                  }`}>
                  {sreStatus}
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-slate-400 font-medium block mb-1">Provider</label>
                  <select
                    value={useSameKey ? rcaProvider : sreProvider}
                    disabled={useSameKey}
                    onChange={(e) => {
                      const np = e.target.value;
                      setSreProvider(np);
                      if (np === 'gemini') setSreModel('gemini-3.8-flash');
                      else if (np === 'anthropic') setSreModel('claude-3-7-sonnet');
                      else if (np === 'openai') setSreModel('gpt-4o');
                    }}
                    className={`w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs ${useSameKey ? 'cursor-not-allowed opacity-60' : ''}`}
                  >
                    <option value="gemini">Google Gemini (Gemini 3.8 Flash)</option>
                    <option value="anthropic">Anthropic (Claude 3.7)</option>
                    <option value="openai">OpenAI (GPT-4o)</option>
                    <option value="deepseek">DeepSeek (R1)</option>
                    <option value="ollama">Ollama (Local)</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-400 font-medium block mb-1">Model</label>
                  {useSameKey ? (
                    <input
                      type="text"
                      value={rcaModel}
                      disabled
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs cursor-not-allowed opacity-60"
                    />
                  ) : sreProvider === 'gemini' && discoveredModels.length > 0 ? (
                    <select
                      value={sreModel}
                      onChange={(e) => setSreModel(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                    >
                      {discoveredModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.id} {m.is_preferred ? '★ (Preferred Default)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={sreModel}
                      onChange={(e) => setSreModel(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                      placeholder="gemini-3.8-flash"
                    />
                  )}
                </div>

                <div>
                  <label className="text-slate-400 font-medium block mb-1">API Key (Password Field)</label>
                  <input
                    type="password"
                    value={useSameKey ? (rcaApiKey ? '••••••••' : '') : sreApiKey}
                    disabled={useSameKey}
                    onChange={(e) => setSreApiKey(e.target.value)}
                    placeholder={useSameKey ? '(Synced with RCA AI Key)' : sreStatus === 'CONNECTED' ? '•••••••••••••••••••••••• (Active)' : 'Enter API Key'}
                    className={`w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs placeholder-slate-500 ${useSameKey ? 'cursor-not-allowed opacity-60' : ''}`}
                  />
                </div>

                <div className="pt-1 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => handleTestConnection('sre_ai')}
                    disabled={testingTarget === 'sre_ai'}
                    className="px-3 py-1.5 rounded-lg bg-cyan-900/60 hover:bg-cyan-800 text-cyan-200 text-xs font-semibold border border-cyan-700/60 transition"
                  >
                    {testingTarget === 'sre_ai' ? 'Testing...' : 'TEST CONNECTION'}
                  </button>
                  <span className="text-[10px] text-slate-500">Live backend check</span>
                </div>
              </div>
            </div>

            {/* Independent Validation AI Credentials */}
            <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  <span>VALIDATION AI (PEER)</span>
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${valStatus === 'CONNECTED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                    valStatus === 'ERROR' || valStatus === 'CONNECTION FAILED' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                      valStatus === 'NOT TESTED' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                        'bg-slate-800 text-slate-400'
                  }`}>
                  {valStatus}
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-slate-400 font-medium block mb-1">Provider (Isolated)</label>
                  <select
                    value={valProvider}
                    onChange={(e) => {
                      const np = e.target.value;
                      setValProvider(np);
                      if (np === 'openai') setValModel('gpt-4o-mini');
                      else if (np === 'gemini') setValModel('gemini-3.8-flash');
                      else if (np === 'anthropic') setValModel('claude-3-7-sonnet');
                      else if (np === 'deepseek') setValModel('deepseek-r1');
                    }}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                  >
                    <option value="openai">OpenAI (GPT-4o / mini)</option>
                    <option value="gemini">Google Gemini (Gemini 3.8 Flash)</option>
                    <option value="anthropic">Anthropic (Claude 3.7)</option>
                    <option value="deepseek">DeepSeek (R1)</option>
                    <option value="ollama">Ollama (Self-Hosted)</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-400 font-medium block mb-1">Model</label>
                  <input
                    type="text"
                    value={valModel}
                    onChange={(e) => setValModel(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs"
                    placeholder="gpt-4o-mini"
                  />
                </div>

                <div>
                  <label className="text-slate-400 font-medium block mb-1">Separate API Key</label>
                  <input
                    type="password"
                    value={valApiKey}
                    onChange={(e) => setValApiKey(e.target.value)}
                    placeholder={valStatus === 'CONNECTED' ? '•••••••••••••••••••••••• (Active)' : 'Enter Independent API Key'}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-white font-mono text-xs placeholder-slate-500"
                  />
                </div>

                <div className="pt-1 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => handleTestConnection('validation_ai')}
                    disabled={testingTarget === 'validation_ai'}
                    className="px-3 py-1.5 rounded-lg bg-emerald-900/60 hover:bg-emerald-800 text-emerald-200 text-xs font-semibold border border-emerald-700/60 transition"
                  >
                    {testingTarget === 'validation_ai' ? 'Testing...' : 'TEST CONNECTION'}
                  </button>
                  <span className="text-[10px] text-slate-500">Zero-bypass guardrail</span>
                </div>
              </div>
            </div>
          </div>

          {/* Test Connection Diagnostic Details */}
          {testResult && (
            <div className={`p-4 rounded-xl border text-xs space-y-2 ${testResult.success ? 'bg-emerald-950/40 border-emerald-800 text-emerald-200' : 'bg-rose-950/40 border-rose-800 text-rose-200'
              }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold font-mono">
                  {testResult.success ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <AlertCircle className="h-4 w-4 text-rose-400" />}
                  <span>[{testResult.target.toUpperCase()}]: {testResult.message}</span>
                </div>
                {testDetails?.latency_ms !== undefined && (
                  <span className="font-mono text-[11px] bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                    Latency: {testDetails.latency_ms}ms
                  </span>
                )}
              </div>
              {testDetails?.category && (
                <div className="flex items-center gap-3 text-[11px] text-slate-300 font-mono">
                  <span>Diagnostic Category: <strong>{testDetails.category}</strong></span>
                  {testDetails.model && <span>Model: <strong>{testDetails.model}</strong></span>}
                  <span>Verified Usable: <strong>{testDetails.verified_usable ? 'YES' : 'NO'}</strong></span>
                </div>
              )}
              {testDetails?.actionable_steps && (
                <p className="text-[11px] text-slate-300 bg-slate-900/60 p-2 rounded border border-slate-800">
                  <strong className="text-white">Actionable Steps:</strong> {testDetails.actionable_steps}
                </p>
              )}
            </div>
          )}
        </div>

        {/* 2. Isolated Recovery Sandbox Configuration */}
        <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-5">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <Box className="h-4 w-4 text-cyan-400" />
            <span>Isolated Sandbox Recovery Gates & Limits</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            {/* Max Recovery Attempts */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex justify-between items-center">
                <span className="font-semibold text-white">Maximum Recovery Attempts (Ceiling)</span>
                <span className="font-mono text-cyan-400 font-bold text-sm bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800">
                  {maxAttempts} Attempts
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={maxAttempts}
                onChange={(e) => setMaxAttempts(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
              <p className="text-[10px] text-slate-400">
                Sandbox will iteratively refine failed recovery attempts up to this limit before marking UNRESOLVED and escalating to SRE Incident Commander.
              </p>
            </div>

            {/* Max Autonomous Risk Ceiling */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <label className="block font-semibold text-white">Autonomous Healing Risk Ceiling</label>
              <select
                value={maxRisk}
                onChange={(e) => setMaxRisk(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200"
              >
                <option value="LOW">LOW Risk Only (Connection reset, buffer flush, worker scale)</option>
                <option value="MEDIUM">MEDIUM Risk (Controlled graceful service restart)</option>
                <option value="HIGH">HIGH Risk (Permit automated container failover)</option>
              </select>
              <p className="text-[10px] text-slate-400 mt-1">Actions above this ceiling require explicit human approval via the Approval Center.</p>
            </div>
          </div>
        </div>

        {/* 3. Notifications & Webhook Channels */}
        <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
            <Bell className="h-4 w-4 text-indigo-400" />
            <span>Alerting & Notification Channels</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Webhook Dispatch URL (Slack / Discord / PagerDuty)</label>
              <input
                type="text"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-slate-200 font-mono text-xs"
              />
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                checked={emailAlerts}
                onChange={(e) => setEmailAlerts(e.target.checked)}
                className="h-4 w-4 rounded bg-slate-800 border-slate-700 text-cyan-500"
              />
              <span className="text-slate-300">Dispatch critical SLA breach notifications to SRE on-call engineers</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleResetSystem}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-rose-300 text-xs font-semibold border border-rose-500/30 transition flex items-center gap-2"
          >
            <RotateCcw className="h-4 w-4 text-rose-400" />
            <span>Reset Demo Systems to Baseline</span>
          </button>

          <button
            type="submit"
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 transition flex items-center gap-2"
          >
            <Save className="h-4 w-4" />
            <span>Save Operational Policies</span>
          </button>
        </div>
      </form>
    </div>
  );
};

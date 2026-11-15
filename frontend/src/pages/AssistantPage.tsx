import React, { useState, useRef, useEffect } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  Zap, 
  User, 
  RefreshCw, 
  Activity, 
  AlertTriangle, 
  ShieldCheck, 
  CheckCircle2, 
  Clock, 
  ChevronRight,
  Database,
  ArrowRight,
  Terminal,
  HelpCircle,
  FileSearch,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  sources?: string[];
  evidence_items?: string[];
  suggestedActions?: string[];
  timestamp: string;
  error?: boolean;
  failedQuery?: string;
}

interface AssistantPageProps {
  incidents?: any[];
  selectedIncidentIdProp?: string;
  onSelectIncident?: (incidentId: string) => void;
  setActiveTab?: (tab: string) => void;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({
  incidents = [],
  selectedIncidentIdProp,
  onSelectIncident,
  setActiveTab
}) => {
  const {
    selectedIncidentId: workspaceIncId,
    setSelectedIncidentId: setWorkspaceIncId,
    assistantState,
    updateAssistantState
  } = useWorkspace();

  const [selectedIncId, setSelectedIncId] = useState<string>(
    selectedIncidentIdProp || workspaceIncId || incidents[0]?.incident_id || 'INC-20261008-001'
  );

  const [conversationId, setConversationId] = useState<string>(
    assistantState.conversationId || `CONV-${Date.now()}`
  );

  const welcomeMessage: Message = {
    id: 'welcome',
    sender: 'assistant',
    text: "Hello! I am your **Autonomous SRE Operations Assistant**.\n\nI have real-time access to the live telemetry stream, incident evidence packages, algorithmic root cause determinations, and isolated sandbox validation runs.\n\nAsk me anything about active incidents, root causes, evidence, or sandbox recovery results.",
    sources: ["Live Central Telemetry Bus", "Incident Evidence Package", "Sandbox Validation Engine"],
    evidence_items: ["Grounded Telemetry: 100% Real", "Zero-Hallucination Policy: Active"],
    suggestedActions: [
      "Why did this incident happen?",
      "When did it start?",
      "Which service failed first?",
      "What evidence proves the root cause?",
      "What recovery was attempted?",
      "Did recovery succeed?"
    ],
    timestamp: new Date().toLocaleTimeString()
  };

  const [messages, setMessages] = useState<Message[]>(() => {
    if (assistantState.messages && assistantState.messages.length > 0) {
      return assistantState.messages;
    }
    return [welcomeMessage];
  });

  const [savedConversations, setSavedConversations] = useState<any[]>(assistantState.savedConversations || []);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(assistantState.isLoading || false);
  const [sandboxContext, setSandboxContext] = useState<any | null>(null);
  const [aiConfig, setAiConfig] = useState<any | null>(null);
  const [lastFailedQuery, setLastFailedQuery] = useState<string | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Sync prop changes
  useEffect(() => {
    if (selectedIncidentIdProp && selectedIncidentIdProp !== selectedIncId) {
      setSelectedIncId(selectedIncidentIdProp);
      setWorkspaceIncId(selectedIncidentIdProp);
    }
  }, [selectedIncidentIdProp]);

  // Load saved conversations list from backend
  const loadConversations = async () => {
    try {
      const data = await api.getSreConversations();
      if (data && data.conversations) {
        setSavedConversations(data.conversations);
        updateAssistantState({ savedConversations: data.conversations });
      }
    } catch {
      // ignore
    }
  };

  const assistantPollingRef = useRef<any>(null);

  // Restore conversation from URL on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlCid = urlParams.get('conversation');
    const urlInc = urlParams.get('incident');
    if (urlInc) {
      setSelectedIncId(urlInc);
      setWorkspaceIncId(urlInc);
    }
    const targetCid = urlCid || conversationId;
    if (urlCid && urlCid !== conversationId) {
      setConversationId(urlCid);
    }
    loadConversationHistory(targetCid);
    loadConversations();

    return () => {
      if (assistantPollingRef.current) clearInterval(assistantPollingRef.current);
    };
  }, []);

  // Load message history if resuming existing conversation, and poll if response is generating
  const loadConversationHistory = async (cId: string) => {
    try {
      const res = await api.getSreConversation(cId);
      if (res && res.messages && res.messages.length > 0) {
        const mapped: Message[] = res.messages.map((m: any) => ({
          id: m.id || m.message_id || `msg-${Math.random()}`,
          sender: m.role === 'user' || m.sender === 'user' ? 'user' : 'assistant',
          text: m.content || m.text || '',
          sources: m.sources,
          evidence_items: m.evidence_items,
          suggestedActions: m.suggested_actions || m.suggestedActions,
          timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString(),
          error: m.status === 'FAILED'
        }));
        setMessages(mapped);
        updateAssistantState({ conversationId: cId, messages: mapped });
      }

      // Check if background task is still generating response for this conversation
      if (res && res.is_generating) {
        setIsLoading(true);
        if (assistantPollingRef.current) clearInterval(assistantPollingRef.current);
        assistantPollingRef.current = setInterval(async () => {
          const pollRes = await api.getSreConversation(cId).catch(() => null);
          if (pollRes && !pollRes.is_generating) {
            clearInterval(assistantPollingRef.current);
            setIsLoading(false);
            if (pollRes.messages && pollRes.messages.length > 0) {
              const updatedMapped: Message[] = pollRes.messages.map((m: any) => ({
                id: m.id || m.message_id || `msg-${Math.random()}`,
                sender: m.role === 'user' || m.sender === 'user' ? 'user' : 'assistant',
                text: m.content || m.text || '',
                sources: m.sources,
                evidence_items: m.evidence_items,
                suggestedActions: m.suggested_actions || m.suggestedActions,
                timestamp: m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString(),
                error: m.status === 'FAILED'
              }));
              setMessages(updatedMapped);
              updateAssistantState({ conversationId: cId, messages: updatedMapped, isLoading: false });
            }
          }
        }, 1200);
      }
    } catch {
      // ignore
    }
  };


  // Load AI configuration status
  useEffect(() => {
    const fetchAiConfig = async () => {
      try {
        const conf = await api.getAiConfigStatus();
        setAiConfig(conf);
      } catch (e) {
        // Fallback default
      }
    };
    fetchAiConfig();
  }, []);

  // Load sandbox context for side panel
  useEffect(() => {
    const loadContext = async () => {
      try {
        const sbx = await api.getIncidentSandbox(selectedIncId).catch(() => null);
        if (sbx) setSandboxContext(sbx);
      } catch (e) {
        // Handled
      }
    };
    if (selectedIncId) loadContext();
  }, [selectedIncId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (queryText?: string) => {
    const q = queryText || inputQuery;
    if (!q.trim() || isLoading) return;

    setLastFailedQuery(null);
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString()
    };

    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInputQuery('');
    setIsLoading(true);
    updateAssistantState({
      conversationId,
      selectedIncId,
      messages: nextMessages,
      isLoading: true
    });

    try {
      const res = await api.chatWithSre(q, conversationId, selectedIncId);
      const activeCid = res.conversation_id || conversationId;
      setConversationId(activeCid);

      const url = new URL(window.location.href);
      url.searchParams.set('tab', 'assistant');
      url.searchParams.set('conversation', activeCid);
      window.history.replaceState({}, '', url.toString());

      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        sender: 'assistant',
        text: res.answer,
        sources: res.sources,
        evidence_items: res.evidence_items,
        suggestedActions: res.suggested_actions || res.suggestedActions,
        timestamp: new Date().toLocaleTimeString()
      };

      const updated = [...nextMessages, assistantMsg];
      setMessages(updated);
      updateAssistantState({
        conversationId: activeCid,
        messages: updated,
        isLoading: false
      });
      loadConversations();
    } catch (e: any) {
      setLastFailedQuery(q);
      const errMsg: Message = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: `Error retrieving operational telemetry: ${e.message || "Failed to communicate with orchestrator."}`,
        timestamp: new Date().toLocaleTimeString(),
        error: true,
        failedQuery: q
      };
      const updated = [...nextMessages, errMsg];
      setMessages(updated);
      updateAssistantState({
        messages: updated,
        isLoading: false
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleIncidentSelect = (newId: string) => {
    setSelectedIncId(newId);
    setWorkspaceIncId(newId);
    if (onSelectIncident) onSelectIncident(newId);
    handleSend(`Can you summarize incident ${newId}?`);
  };

  const activeInc = incidents.find(i => i.incident_id === selectedIncId) || {
    incident_id: selectedIncId,
    title: 'Database Connection Pool Exhaustion',
    severity: 'CRITICAL',
    root_cause_service: 'database-service',
    status: 'INVESTIGATING'
  };

  const quickPrompts = [
    "Why did recovery attempt 1 fail?",
    "Compare attempt 1 and attempt 2.",
    "Has this happened before?",
    "Why was this recovery selected?",
    "What evidence proves recovery worked?",
    "Show me the validation proof.",
    "Why did this incident happen?",
    "Which service failed first?",
    "What evidence proves the root cause?",
    "Was there a side effect?",
    "What should we do next?"
  ];

  const isAiConnected = Boolean(aiConfig?.sre_ai?.is_configured);

  return (
    <div className="space-y-4 max-w-7xl mx-auto h-[calc(100vh-120px)] flex flex-col pb-4 animate-fadeIn">
      {/* 1. Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80 flex-shrink-0">
        <div>
          <div className="flex items-center gap-2 text-indigo-400 font-mono text-xs uppercase tracking-wider">
            <Bot className="h-4 w-4" />
            <span>Autonomous Conversational Operations</span>
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            <h2 className="text-xl font-bold text-white tracking-tight">
              SRE Assistant
            </h2>
            <span className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-md border flex items-center gap-1.5 ${
              isAiConnected 
                ? 'bg-purple-950/60 text-purple-300 border-purple-800/80' 
                : 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80'
            }`}>
              <span className={`h-2 w-2 rounded-full ${isAiConnected ? 'bg-purple-400 animate-pulse' : 'bg-emerald-400'}`} />
              {isAiConnected ? `AI + TELEMETRY MODE (${aiConfig?.sre_ai?.provider?.toUpperCase()})` : 'DETERMINISTIC MODE'}
            </span>
          </div>
        </div>

        {/* Incident Selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-900/90 p-1.5 px-3 rounded-xl border border-slate-800 text-xs">
            <span className="text-slate-400">Context:</span>
            <select
              value={selectedIncId}
              onChange={(e) => handleIncidentSelect(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-indigo-300 font-mono font-bold focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              {incidents.length > 0 ? (
                incidents.map((inc) => (
                  <option key={inc.incident_id} value={inc.incident_id}>
                    {inc.incident_id} — {inc.primary_service || inc.root_cause_service}
                  </option>
                ))
              ) : (
                <option value={selectedIncId}>{selectedIncId}</option>
              )}
            </select>
          </div>

          {savedConversations.length > 0 && (
            <div className="flex items-center gap-1.5 bg-slate-900/90 p-1.5 px-3 rounded-xl border border-slate-800 text-xs">
              <span className="text-slate-400">Past Chat:</span>
              <select
                value={conversationId}
                onChange={(e) => {
                  const newCid = e.target.value;
                  setConversationId(newCid);
                  const url = new URL(window.location.href);
                  url.searchParams.set('tab', 'assistant');
                  url.searchParams.set('conversation', newCid);
                  window.history.replaceState({}, '', url.toString());
                  loadConversationHistory(newCid);
                }}
                className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-300 font-mono focus:outline-none focus:border-indigo-500 cursor-pointer max-w-[140px] truncate"
              >
                <option value={conversationId}>Current Session</option>
                {savedConversations.map((c) => (
                  <option key={c.conversation_id} value={c.conversation_id}>
                    {c.title || c.conversation_id}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={() => {
              const newCid = `CONV-${Date.now()}`;
              setConversationId(newCid);
              setMessages([welcomeMessage]);
              updateAssistantState({ conversationId: newCid, messages: [welcomeMessage] });
              const url = new URL(window.location.href);
              url.searchParams.set('tab', 'assistant');
              url.searchParams.set('conversation', newCid);
              window.history.replaceState({}, '', url.toString());
            }}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 transition"
          >
            New Chat
          </button>
        </div>
      </div>

      {/* 2. Main Content: Chat Window (Left) + SRE Context Panel (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 min-h-0">
        {/* Chat Area (3 Columns) */}
        <div className="lg:col-span-3 flex flex-col bg-slate-950/70 border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
          {/* Quick Prompts Strip */}
          <div className="p-2.5 px-4 bg-slate-900/80 border-b border-slate-800/80 flex items-center gap-2 overflow-x-auto no-scrollbar">
            <span className="text-[10px] text-slate-400 font-mono uppercase whitespace-nowrap">Suggested:</span>
            {quickPrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(prompt)}
                disabled={isLoading}
                className="text-[11px] font-medium whitespace-nowrap px-3 py-1 rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 transition disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Messages Feed */}
          <div className="flex-1 p-5 overflow-y-auto space-y-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-3 max-w-[85%] ${
                  m.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
                }`}
              >
                {/* Avatar */}
                <div
                  className={`h-8 w-8 rounded-xl flex items-center justify-center flex-shrink-0 text-xs shadow-md ${
                    m.sender === 'user'
                      ? 'bg-cyan-600 text-white'
                      : 'bg-indigo-600 text-white'
                  }`}
                >
                  {m.sender === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>

                {/* Message Body */}
                <div
                  className={`p-4 rounded-2xl text-xs space-y-2 leading-relaxed shadow-sm ${
                    m.sender === 'user'
                      ? 'bg-gradient-to-r from-cyan-600 to-indigo-600 text-white rounded-tr-none'
                      : 'bg-slate-900 border border-slate-800/80 text-slate-200 rounded-tl-none'
                  }`}
                >
                  <div className="prose prose-invert max-w-none text-xs whitespace-pre-wrap leading-relaxed">
                    {m.text}
                  </div>

                  {/* Evidence Citations & Sources */}
                  {m.sources && m.sources.length > 0 && (
                    <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center gap-1.5 text-[10px]">
                      <span className="text-slate-500 font-mono">Sources:</span>
                      {m.sources.map((s, idx) => (
                        <span key={idx} className="px-2 py-0.5 rounded bg-slate-950 text-indigo-300 border border-slate-800 font-mono">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Evidence Items */}
                  {m.evidence_items && m.evidence_items.length > 0 && (
                    <div className="pt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
                      {m.evidence_items.map((ev, idx) => (
                        <span key={idx} className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-800/40 font-mono">
                          ✓ {ev}
                        </span>
                      ))}
                    </div>
                  )}

                  {m.error && (
                    <div className="pt-2">
                      <button
                        onClick={() => handleSend(m.failedQuery || lastFailedQuery || undefined)}
                        className="px-2.5 py-1 rounded bg-rose-600/30 hover:bg-rose-600 text-rose-200 border border-rose-500/50 text-[11px] font-bold transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <RefreshCw className="h-3 w-3" />
                        <span>Retry Request</span>
                      </button>
                    </div>
                  )}

                  <div className={`text-[9px] font-mono pt-1 text-right ${
                    m.sender === 'user' ? 'text-cyan-200' : 'text-slate-500'
                  }`}>
                    {m.timestamp}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-3 max-w-[80%] mr-auto items-center">
                <div className="h-8 w-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 text-xs animate-pulse">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-400 animate-spin" />
                  <span>Synthesizing live telemetry evidence...</span>
                </div>
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>

          {/* Input Box */}
          <div className="p-3 bg-slate-900/90 border-t border-slate-800/80">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder="Ask about root cause, traces, failure reproduction, or sandbox validation..."
                disabled={isLoading}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-medium"
              />
              <button
                type="submit"
                disabled={!inputQuery.trim() || isLoading}
                className="p-3 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white disabled:opacity-50 transition shadow-lg shadow-cyan-500/20"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right-Side Incident Context Panel (1 Column) */}
        <div className="p-5 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-xl space-y-5 overflow-y-auto">
          <div>
            <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider block">Live Grounding Context</span>
            <h3 className="text-sm font-bold text-white mt-1">Incident Telemetry Snapshot</h3>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-500 uppercase block">Active Incident</span>
              <span className="text-xs font-bold text-indigo-300 block">{selectedIncId}</span>
              <span className="text-[10px] text-slate-400 block">{activeInc.severity} • {activeInc.status}</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-500 uppercase block">Root Cause Component</span>
              <span className="text-xs font-bold text-rose-400 block">{activeInc.root_cause_service || 'database-service'}</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-500 uppercase block">Sandbox Environment</span>
              <span className="text-xs font-bold text-cyan-400 block">{sandboxContext?.sandbox_id || 'SBX-STANDBY'}</span>
              <span className="text-[10px] text-slate-400 block">
                Attempt: {sandboxContext?.attempt_number || 1} / {sandboxContext?.max_attempts || 3}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-500 uppercase block">Validation Outcome</span>
              <span className={`text-xs font-bold block ${
                sandboxContext?.final_outcome === 'RECOVERY_VERIFIED' ? 'text-emerald-400' : 'text-slate-400'
              }`}>
                {sandboxContext?.final_outcome || 'STANDBY'}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 space-y-2">
            <span className="text-[10px] font-mono text-slate-400 uppercase block">Fast Navigation</span>
            <button
              onClick={() => setActiveTab && setActiveTab('rca')}
              className="w-full py-2 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-left text-xs text-slate-300 flex items-center justify-between transition"
            >
              <span>View RCA Evidence</span>
              <ExternalLink className="h-3.5 w-3.5 text-slate-500" />
            </button>
            <button
              onClick={() => setActiveTab && setActiveTab('recovery')}
              className="w-full py-2 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-left text-xs text-slate-300 flex items-center justify-between transition"
            >
              <span>View Sandbox Validation</span>
              <ExternalLink className="h-3.5 w-3.5 text-slate-500" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

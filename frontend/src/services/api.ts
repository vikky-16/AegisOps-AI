import type { 
  ServiceDetail, 
  Incident, 
  ApprovalTicket, 
  ApprovalStats,
  RecoveryExecution, 
  StorageStatus, 
  AssistantResponse,
  PaginatedLogs,
  LogSummary,
  LogFingerprint,
  PlatformSettings,
  ConnectorInfo,
  RunbookInfo,
  DryRunResult,
  OperationFeedItem,
  SimulatorStatus,
  LogHubDatasetInfo,
  LogHubReplayStatus,
  StreamConsumerStatus,
  RemediationRunbook,
  RunbookStepExecution,
  RunbookExecutionRecord,
  TelemetryMode,
  ContinuousTelemetryStatus,
  FailureSchedulerStatus,
  TelemetryDiagnosticsResponse,
  FailureScenarioInfo,
  ServiceDependency,
  DependencyGraphData,
  TelemetryStats,
  CanonicalOperationalState,
  SystemConsistencyAudit
} from '../types';

const API_BASE = 'http://127.0.0.1:8000/api';

export const getAuthHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {};
  const token = localStorage.getItem('aegisops_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const tenantId = localStorage.getItem('aegisops_tenant_id') || 'demo-tenant';
  headers['X-Tenant-ID'] = tenantId;
  const apiKey = localStorage.getItem('aegisops_api_key');
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  return headers;
};

// In-flight request deduplication map to prevent simultaneous duplicate HTTP requests
const inFlightRequests = new Map<string, Promise<any>>();
// Short-lived memory cache for static/read-only metadata
const responseCache = new Map<string, { data: any; expiry: number }>();

export const cachedFetch = async <T = any>(
  url: string,
  options: RequestInit = {},
  ttlMs: number = 0
): Promise<T> => {
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET') {
    const res = await fetch(url, options);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  }

  const tenant = localStorage.getItem('aegisops_tenant_id') || 'demo-tenant';
  const cacheKey = `${tenant}:${url}`;

  if (ttlMs > 0) {
    const cached = responseCache.get(cacheKey);
    if (cached && cached.expiry > Date.now()) {
      return cached.data as T;
    }
  }

  if (inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey) as Promise<T>;
  }

  const promise = (async () => {
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        if (res.status === 401 && !url.includes('/auth/login')) {
          localStorage.removeItem('aegisops_token');
          localStorage.removeItem('aegisops_user');
        }
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      if (ttlMs > 0) {
        responseCache.set(cacheKey, { data, expiry: Date.now() + ttlMs });
      }
      return data;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  })();

  inFlightRequests.set(cacheKey, promise);
  return promise;
};

export const api = {
  clearCache: () => {
    responseCache.clear();
    inFlightRequests.clear();
  },
  // Service Dependencies & Topology Graph
  getDependencies: async (): Promise<ServiceDependency[]> => {
    return cachedFetch<ServiceDependency[]>(`${API_BASE}/dependencies`, { headers: getAuthHeaders() }, 2000);
  },

  getDependencyGraph: async (incidentId?: string): Promise<DependencyGraphData> => {
    const url = incidentId 
      ? `${API_BASE}/dependencies/graph?incident_id=${encodeURIComponent(incidentId)}`
      : `${API_BASE}/dependencies/graph`;
    return cachedFetch<DependencyGraphData>(url, { headers: getAuthHeaders() }, 1500);
  },

  getServiceDependencies: async (serviceId: string): Promise<any> => {
    return cachedFetch(`${API_BASE}/services/${serviceId}/dependencies`, { headers: getAuthHeaders() }, 3000);
  },

  getServiceDependents: async (serviceId: string): Promise<any> => {
    return cachedFetch(`${API_BASE}/services/${serviceId}/dependents`, { headers: getAuthHeaders() }, 3000);
  },

  getServiceObservability: async (serviceId: string, timeRange: string = '15m'): Promise<any> => {
    const url = `${API_BASE}/services/${encodeURIComponent(serviceId)}/observability?time_range=${timeRange}`;
    return cachedFetch(url, { headers: getAuthHeaders() }, 1500);
  },

  getGlobalServiceObservability: async (): Promise<{
    summary: {
      tenant_id?: string;
      total_services: number;
      monitored_services?: number;
      telemetry_coverage_pct?: number;
      healthy: number;
      warning: number;
      degraded: number;
      critical: number;
      unknown: number;
      availability: number;
      overall_error_rate: number;
      overall_request_rate: number;
      p95_latency: number;
      active_incidents: number;
      incidents_by_severity?: {
        CRITICAL: number;
        HIGH: number;
        MEDIUM: number;
        LOW: number;
      };
      degraded_services?: any[];
      uninstrumented_services?: any[];
      early_warning: 'NORMAL' | 'WARNING' | 'DEGRADING' | 'CRITICAL';
      system_health_score?: number;
      last_telemetry_at?: string;
      telemetry_freshness_seconds?: number;
    };
    services: any[];
  }> => {
    return cachedFetch(`${API_BASE}/services/observability/global`, { headers: getAuthHeaders() }, 1500);
  },

  // Services & Metrics
  getServices: async (): Promise<ServiceDetail[]> => {
    return cachedFetch<ServiceDetail[]>(`${API_BASE}/services`, { headers: getAuthHeaders() }, 2000);
  },

  getServiceHistory: async (serviceName: string): Promise<any[]> => {
    return cachedFetch(`${API_BASE}/metrics/${serviceName}/history`, { headers: getAuthHeaders() }, 2000);
  },

  // Incidents
  getIncidents: async (): Promise<Incident[]> => {
    let res = await fetch(`${API_BASE}/incidents`, { headers: getAuthHeaders() });
    if (res.status === 401) {
      localStorage.removeItem('aegisops_token');
      res = await fetch(`${API_BASE}/incidents`, { headers: getAuthHeaders() });
    }
    if (!res.ok) throw new Error('Failed to fetch incidents');
    return res.json();
  },

  getIncidentDetails: async (incidentId: string): Promise<Incident> => {
    let res = await fetch(`${API_BASE}/incidents/${incidentId}`, { headers: getAuthHeaders() });
    if (res.status === 401) {
      localStorage.removeItem('aegisops_token');
      res = await fetch(`${API_BASE}/incidents/${incidentId}`, { headers: getAuthHeaders() });
    }
    if (!res.ok) throw new Error('Failed to fetch incident details');
    return res.json();
  },

  getIncidentTimeline: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/timeline`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch incident timeline');
    return res.json();
  },

  getIncidentEvidence: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/evidence`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch incident evidence');
    return res.json();
  },

  requestIncidentApproval: async (incidentId: string, requester: string = 'SRE Investigator'): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/request-approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requester })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to request approval' }));
      throw new Error(err.detail || 'Failed to request approval');
    }
    return res.json();
  },

  clearAllIncidents: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/clear`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to clear incidents');
    return res.json();
  },

  replayIncident: async (incidentId: string, scenarioId?: string, action?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/replay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ scenario_id: scenarioId, action })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to replay incident scenario' }));
      throw new Error(err.detail || 'Failed to replay incident scenario');
    }
    return res.json();
  },

  // Approvals (Approve / Reject / Defer with RBAC)
  getApprovals: async (status?: string): Promise<ApprovalTicket[]> => {
    const url = status ? `${API_BASE}/approvals?status=${status}` : `${API_BASE}/approvals`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch approval tickets');
    return res.json();
  },

  getApprovalStats: async (): Promise<ApprovalStats> => {
    const res = await fetch(`${API_BASE}/approvals/stats`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch approval stats');
    return res.json();
  },

  getApprovalTicket: async (approvalId: string): Promise<ApprovalTicket> => {
    const res = await fetch(`${API_BASE}/approvals/${approvalId}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch approval ticket ${approvalId}`);
    return res.json();
  },

  approveTicket: async (approvalId: string, reviewer: string = 'Lead SRE Admin', role: string = 'ADMIN', notes?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/approvals/${approvalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ reviewer, role, notes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to approve ticket' }));
      throw new Error(err.detail || 'Failed to approve ticket');
    }
    return res.json();
  },

  rejectTicket: async (approvalId: string, reviewer: string = 'Lead SRE Admin', role: string = 'ADMIN', notes?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/approvals/${approvalId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ reviewer, role, notes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to reject ticket' }));
      throw new Error(err.detail || 'Failed to reject ticket');
    }
    return res.json();
  },

  deferTicket: async (approvalId: string, reviewer: string = 'Lead SRE Admin', role: string = 'ADMIN', notes?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/approvals/${approvalId}/defer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ reviewer, role, notes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to defer ticket' }));
      throw new Error(err.detail || 'Failed to defer ticket');
    }
    return res.json();
  },

  // Recovery & Remediation (Controlled Demo)
  getRecoveryHistory: async (): Promise<RecoveryExecution[]> => {
    const res = await fetch(`${API_BASE}/recovery`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Failed to fetch recovery history (HTTP ${res.status})`);
    }
    return res.json();
  },

  triggerManualRemediation: async (serviceName: string, action: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_name: serviceName, action })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Failed to trigger manual remediation (HTTP ${res.status})`);
    }
    return res.json();
  },

  triggerManualRecovery: async (serviceName: string, action: string): Promise<any> => {
    return api.triggerManualRemediation(serviceName, action);
  },

  getSelfHealingCandidates: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/self-healing/candidates`);
    if (!res.ok) throw new Error('Failed to fetch self-healing candidates');
    return res.json();
  },

  executeRecovery: async (incidentId: string, action?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ action })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Failed to execute recovery (HTTP ${res.status})`);
    }
    return res.json();
  },

  approveRecovery: async (incidentId: string, reason?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ reason })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `Failed to approve recovery (HTTP ${res.status})`);
    }
    return res.json();
  },

  getAllowlistedActions: async (): Promise<Record<string, any>> => {
    const res = await fetch(`${API_BASE}/recovery/actions`);
    if (!res.ok) throw new Error('Failed to fetch allowlisted recovery actions');
    return res.json();
  },

  evaluateSafetyChecks: async (incidentId: string, action?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/safety-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ action })
    });
    if (!res.ok) throw new Error('Failed to evaluate safety checks');
    return res.json();
  },

  getRecoveryState: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/state`);
    if (!res.ok) throw new Error(`Failed to fetch recovery state for ${incidentId}`);
    return res.json();
  },

  replayWorkflow: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/replay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }
    });
    if (!res.ok) throw new Error('Failed to replay workflow');
    return res.json();
  },

  rollbackRecovery: async (incidentId: string, action?: string, reason?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ action, reason })
    });
    if (!res.ok) throw new Error('Failed to rollback recovery');
    return res.json();
  },

  getRecoveryVerification: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/recovery/${encodeURIComponent(incidentId)}/verification`);
    if (!res.ok) throw new Error(`Failed to fetch recovery verification for ${incidentId}`);
    return res.json();
  },

  // Storage Intelligence
  getStorageStatus: async (): Promise<StorageStatus> => {
    const res = await fetch(`${API_BASE}/storage`);
    if (!res.ok) throw new Error('Failed to fetch storage status');
    return res.json();
  },

  getStorage: async (): Promise<StorageStatus> => {
    return api.getStorageStatus();
  },

  optimizeStorage: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/storage/optimize`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to optimize storage');
    return res.json();
  },

  // Logs & High-Throughput Engine
  getLogs: async (params?: { page?: number; page_size?: number; pageSize?: number; service?: string; level?: string; search?: string; grouped?: boolean }): Promise<PaginatedLogs> => {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', params.page.toString());
    const size = params?.page_size || params?.pageSize;
    if (size) query.set('page_size', size.toString());
    if (params?.service) query.set('service', params.service);
    if (params?.level) query.set('level', params.level);
    if (params?.search) query.set('search', params.search);
    if (params?.grouped !== undefined) query.set('grouped', params.grouped.toString());

    const res = await fetch(`${API_BASE}/logs?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch logs');
    return res.json();
  },

  getLogSummary: async (): Promise<LogSummary> => {
    const res = await fetch(`${API_BASE}/logs/summary`);
    if (!res.ok) throw new Error('Failed to fetch log summary');
    return res.json();
  },

  getLogFingerprints: async (): Promise<LogFingerprint[]> => {
    const res = await fetch(`${API_BASE}/logs/fingerprints`);
    if (!res.ok) throw new Error('Failed to fetch log fingerprints');
    return res.json();
  },

  generateLogs: async (count: number = 10000, scenario: string = 'database_storm', triggerAnomaly: boolean = false): Promise<any> => {
    return api.generateSimulatedLogs(count, scenario, triggerAnomaly);
  },

  clearLogs: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/logs/clear`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to clear logs');
    return res.json();
  },

  generateSimulatedLogs: async (count: number, scenario: string, triggerAnomaly: boolean = false): Promise<any> => {
    const res = await fetch(`${API_BASE}/logs/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count, scenario, trigger_anomaly: triggerAnomaly })
    });
    if (!res.ok) throw new Error('Failed to generate logs');
    return res.json();
  },

  // Telemetry Integrations & Connectors
  getIntegrations: async (): Promise<ConnectorInfo[]> => {
    const res = await fetch(`${API_BASE}/integrations`);
    if (!res.ok) throw new Error('Failed to fetch integrations');
    return res.json();
  },

  testIntegration: async (connectorId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/integrations/${connectorId}/test`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to test integration');
    return res.json();
  },

  toggleIntegration: async (connectorId: string, enabled: boolean): Promise<any> => {
    const res = await fetch(`${API_BASE}/integrations/${connectorId}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
    if (!res.ok) throw new Error('Failed to toggle integration');
    return res.json();
  },

  // Synthetic Telemetry Simulator
  getSimulatorStatus: async (): Promise<SimulatorStatus> => {
    const res = await fetch(`${API_BASE}/simulator/status`);
    if (!res.ok) throw new Error('Failed to fetch simulator status');
    return res.json();
  },

  startSimulatorStream: async (scenario: string, targetCount: number = 10000, eps: number = 500): Promise<SimulatorStatus> => {
    const res = await fetch(`${API_BASE}/simulator/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, target_count: targetCount, eps })
    });
    if (!res.ok) throw new Error('Failed to start simulator stream');
    return res.json();
  },

  pauseSimulatorStream: async (): Promise<SimulatorStatus> => {
    const res = await fetch(`${API_BASE}/simulator/pause`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to pause simulator stream');
    return res.json();
  },

  resumeSimulatorStream: async (): Promise<SimulatorStatus> => {
    const res = await fetch(`${API_BASE}/simulator/resume`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to resume simulator stream');
    return res.json();
  },

  stopSimulatorStream: async (): Promise<SimulatorStatus> => {
    const res = await fetch(`${API_BASE}/simulator/stop`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to stop simulator stream');
    return res.json();
  },

  resetSimulator: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reset simulator state');
    return res.json();
  },

  // LogHub Real-World Dataset & Telemetry Replay Subsystem
  getLogHubDatasets: async (): Promise<LogHubDatasetInfo[]> => {
    const res = await fetch(`${API_BASE}/loghub/datasets`);
    if (!res.ok) throw new Error('Failed to fetch LogHub datasets');
    return res.json();
  },

  getLogHubReplayStatus: async (): Promise<LogHubReplayStatus> => {
    const res = await fetch(`${API_BASE}/loghub/replay/status`);
    if (!res.ok) throw new Error('Failed to fetch LogHub replay status');
    return res.json();
  },

  startLogHubReplay: async (dataset: string, targetCount: number = 100000, eps: number = 1000): Promise<LogHubReplayStatus> => {
    const res = await fetch(`${API_BASE}/loghub/replay/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset, target_count: targetCount, eps })
    });
    if (!res.ok) throw new Error('Failed to start LogHub replay');
    return res.json();
  },

  pauseLogHubReplay: async (): Promise<LogHubReplayStatus> => {
    const res = await fetch(`${API_BASE}/loghub/replay/pause`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to pause LogHub replay');
    return res.json();
  },

  resumeLogHubReplay: async (): Promise<LogHubReplayStatus> => {
    const res = await fetch(`${API_BASE}/loghub/replay/resume`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to resume LogHub replay');
    return res.json();
  },

  stopLogHubReplay: async (): Promise<LogHubReplayStatus> => {
    const res = await fetch(`${API_BASE}/loghub/replay/stop`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to stop LogHub replay');
    return res.json();
  },

  resetLogHubReplay: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/loghub/replay/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reset LogHub replay state');
    return res.json();
  },

  // Operations Center Feed & Environment
  getOperationsFeed: async (limit: number = 50): Promise<OperationFeedItem[]> => {
    const res = await fetch(`${API_BASE}/operations/feed?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch operations feed');
    return res.json();
  },

  getOperationsStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/operations/status`);
    if (!res.ok) throw new Error('Failed to fetch operations status');
    return res.json();
  },

  setEnvironmentMode: async (environmentMode: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/operations/environment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ environment_mode: environmentMode })
    });
    if (!res.ok) throw new Error('Failed to set environment mode');
    return res.json();
  },

  // AI SRE Assistant
  askAssistant: async (question: string, incidentId?: string): Promise<AssistantResponse> => {
    const res = await fetch(`${API_BASE}/assistant/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, incident_id: incidentId })
    });
    if (!res.ok) throw new Error('Failed to get answer from assistant');
    return res.json();
  },

  // Settings & Simulations
  getSettings: async (): Promise<PlatformSettings> => {
    const res = await fetch(`${API_BASE}/platform/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  updateSettings: async (settings: Partial<PlatformSettings>): Promise<any> => {
    const res = await fetch(`${API_BASE}/platform/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  },

  getSimulationsOverview: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations`);
    if (!res.ok) throw new Error('Failed to fetch simulations overview');
    return res.json();
  },

  injectSimulation: async (scenario: string, targetService?: string, intensity: number = 1.0): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, service: targetService, intensity })
    });
    if (!res.ok) throw new Error(`Failed to inject simulation '${scenario}'`);
    return res.json();
  },

  triggerSimulation: async (scenario: string, targetService?: string): Promise<any> => {
    return api.injectSimulation(scenario, targetService);
  },

  // Enterprise Remediation Runbooks Engine
  getRunbooks: async (params?: {
    service?: string;
    failure_type?: string;
    risk_level?: string;
  }): Promise<RemediationRunbook[]> => {
    const query = new URLSearchParams();
    if (params?.service) query.set('service', params.service);
    if (params?.failure_type) query.set('failure_type', params.failure_type);
    if (params?.risk_level) query.set('risk_level', params.risk_level);
    const res = await fetch(`${API_BASE}/runbooks?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch operational runbooks');
    const data = await res.json();
    return data.runbooks || [];
  },

  getRecommendedRunbooks: async (incidentId: string): Promise<{
    incident_id: string;
    root_cause?: string;
    recommendations: any[];
    count: number;
  }> => {
    const res = await fetch(`${API_BASE}/runbooks/recommended/${incidentId}`);
    if (!res.ok) throw new Error(`Failed to fetch recommended runbooks for ${incidentId}`);
    return res.json();
  },

  executeRunbook: async (runbookId: string, incidentId: string, caller: string = 'Operations Member'): Promise<RunbookExecutionRecord> => {
    const res = await fetch(`${API_BASE}/runbooks/${runbookId}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident_id: incidentId,
        caller: caller
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to execute runbook' }));
      throw new Error(err.detail || 'Failed to execute runbook');
    }
    return res.json();
  },

  dryRunRunbook: async (runbookId: string, incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/runbooks/${runbookId}/dry-run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident_id: incidentId })
    });
    if (!res.ok) throw new Error('Failed to dry-run runbook');
    return res.json();
  },

  getRunbookExecution: async (executionId: string): Promise<RunbookExecutionRecord> => {
    const res = await fetch(`${API_BASE}/runbooks/executions/${executionId}`);
    if (!res.ok) throw new Error(`Failed to fetch runbook execution ${executionId}`);
    return res.json();
  },

  getRunbookStatistics: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/runbooks/statistics`);
    if (!res.ok) throw new Error('Failed to fetch runbook statistics');
    return res.json();
  },

  approveRunbookIncident: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/runbooks/incidents/${incidentId}/approve`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to approve incident for runbook execution');
    return res.json();
  },

  // Telemetry Control, Ingestion Diagnostics & Failure Engine
  getTelemetryStatus: async (): Promise<{
    operating_mode: TelemetryMode;
    continuous_telemetry: ContinuousTelemetryStatus;
    telemetry_stats?: TelemetryStats;
    failure_scheduler: FailureSchedulerStatus;
    total_active_incidents: number;
    system_health_score: number;
  }> => {
    const res = await fetch(`${API_BASE}/telemetry/status`);
    if (!res.ok) throw new Error('Failed to fetch telemetry status');
    return res.json();
  },

  setTelemetryMode: async (mode: TelemetryMode): Promise<{ success: boolean; operating_mode: TelemetryMode }> => {
    const res = await fetch(`${API_BASE}/telemetry/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    if (!res.ok) throw new Error('Failed to switch operating mode');
    return res.json();
  },

  setTelemetryRate: async (eps: number): Promise<{ success: boolean; configured_eps: number }> => {
    const res = await fetch(`${API_BASE}/telemetry/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eps })
    });
    if (!res.ok) throw new Error('Failed to set telemetry rate');
    return res.json();
  },

  configureFailureScheduler: async (config: { enabled?: boolean; interval_seconds?: number }): Promise<FailureSchedulerStatus> => {
    const res = await fetch(`${API_BASE}/telemetry/failure-scheduler`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error('Failed to configure failure scheduler');
    return res.json();
  },

  triggerFailureScenario: async (scenario: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/telemetry/trigger-failure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    });
    if (!res.ok) throw new Error(`Failed to trigger scenario '${scenario}'`);
    return res.json();
  },

  triggerManualFailure: async (scenario: string): Promise<any> => {
    return api.triggerFailureScenario(scenario);
  },

  getTelemetryDiagnostics: async (limit: number = 30): Promise<TelemetryDiagnosticsResponse> => {
    const res = await fetch(`${API_BASE}/telemetry/diagnostics?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch telemetry diagnostics');
    return res.json();
  },

  getFailureScenarios: async (): Promise<FailureScenarioInfo[]> => {
    const res = await fetch(`${API_BASE}/telemetry/scenarios?all_scenarios=true`);
    if (!res.ok) throw new Error('Failed to fetch failure scenarios');
    return res.json();
  },

  // Platform Self-Observability & Kafka Health
  getPlatformHealth: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/platform/health`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch platform health');
    return res.json();
  },

  getKafkaHealth: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/platform/kafka/health`);
    if (!res.ok) throw new Error('Failed to fetch Kafka health');
    return res.json();
  },

  // Telemetry Federation & Baselines
  getLiveTelemetryFeed: async (params?: { limit?: number; service?: string; severity?: string; trace_id?: string }): Promise<any> => {
    const query = new URLSearchParams(params as any).toString();
    const res = await fetch(`${API_BASE}/telemetry/live?${query}`);
    if (!res.ok) throw new Error('Failed to fetch live telemetry feed');
    return res.json();
  },

  getCorrelatedContext: async (params?: { service?: string; incident_id?: string; trace_id?: string }): Promise<any> => {
    const query = new URLSearchParams(params as any).toString();
    const res = await fetch(`${API_BASE}/telemetry/correlated-context?${query}`);
    if (!res.ok) throw new Error('Failed to fetch correlated context');
    return res.json();
  },

  getAnomalies: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/telemetry/anomalies`);
    if (!res.ok) throw new Error('Failed to fetch anomalies');
    return res.json();
  },

  getBaselines: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/telemetry/baselines`);
    if (!res.ok) throw new Error('Failed to fetch baselines');
    return res.json();
  },

  getIncidentBlastRadius: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/blast-radius`);
    if (!res.ok) throw new Error(`Failed to fetch blast radius for ${incidentId}`);
    return res.json();
  },

  getIncidentTelemetry: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/telemetry`);
    if (!res.ok) throw new Error(`Failed to fetch telemetry for ${incidentId}`);
    return res.json();
  },

  getOtelHealth: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/otel/health`);
    if (!res.ok) throw new Error('Failed to fetch OpenTelemetry health');
    return res.json();
  },

  // 20-Scenario Failure Orchestrator
  getOrchestratorStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/status`);
    if (!res.ok) throw new Error('Failed to fetch orchestrator status');
    return res.json();
  },

  listOrchestratorScenarios: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/scenarios`);
    if (!res.ok) throw new Error('Failed to list orchestrator scenarios');
    return res.json();
  },

  triggerOrchestratorNext: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/trigger`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to trigger next scenario');
    }
    return res.json();
  },

  forceOrchestratorScenario: async (scenarioId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/force`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to force scenario');
    }
    return res.json();
  },

  pauseOrchestrator: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/pause`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to pause orchestrator');
    return res.json();
  },

  resumeOrchestrator: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/resume`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to resume orchestrator');
    return res.json();
  },

  skipOrchestratorScenario: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/skip`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to skip scenario');
    return res.json();
  },

  configOrchestrator: async (config: { interval_seconds?: number; auto_mode?: boolean }): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulator/orchestrator/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error('Failed to configure orchestrator');
    return res.json();
  },

  // Multi-Tenancy & Customer Onboarding
  getTenants: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/tenants`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch tenants');
    return res.json();
  },

  createTenant: async (data: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/tenants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create tenant');
    }
    return res.json();
  },

  getTenantDetails: async (tenantId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/tenants/${tenantId}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch tenant details');
    return res.json();
  },

  updateTenantPolicy: async (tenantId: string, policy: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/tenants/${tenantId}/policy`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(policy)
    });
    if (!res.ok) throw new Error('Failed to update tenant policy');
    return res.json();
  },

  createTenantApiKey: async (tenantId: string, data: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/tenants/${tenantId}/api-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create API key');
    return res.json();
  },

  revokeTenantApiKey: async (tenantId: string, keyId: number): Promise<any> => {
    const res = await fetch(`${API_BASE}/tenants/${tenantId}/api-keys/${keyId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to revoke API key');
    return res.json();
  },

  getTenantIntegrations: async (tenantId: string): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/integrations`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch integrations');
    return res.json();
  },

  addTenantIntegration: async (tenantId: string, data: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/integrations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to add integration');
    return res.json();
  },

  testTenantConnection: async (tenantId: string, integrationId?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/integrations/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ integration_id: integrationId })
    });
    if (!res.ok) throw new Error('Failed to run connection test');
    return res.json();
  },

  rotateIntegrationKey: async (tenantId: string, integrationId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/integrations/${integrationId}/rotate-key`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to rotate integration API key');
    return res.json();
  },

  revokeIntegration: async (tenantId: string, integrationId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/integrations/${integrationId}/revoke`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to revoke integration');
    return res.json();
  },

  generateOtelConfig: async (tenantId: string, data: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/otel-config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to generate OpenTelemetry Collector config');
    return res.json();
  },

  getTenantAuditLogs: async (tenantId: string): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/audit`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    return res.json();
  },

  getIngestionStats: async (tenantId?: string): Promise<any> => {
    const url = tenantId ? `${API_BASE}/v1/telemetry/stats?tenant_id=${tenantId}` : `${API_BASE}/v1/telemetry/stats`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch ingestion throughput statistics');
    return res.json();
  },

  // ==============================================================
  // ENTERPRISE AUTHENTICATION & SESSIONS
  // ==============================================================
  login: async (payload: { username: string; password: string; tenant_id?: string; mfa_code?: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },

  signup: async (payload: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Signup failed' }));
      throw new Error(err.detail || 'Signup failed');
    }
    return res.json();
  },

  forgotPassword: async (email: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) throw new Error('Failed to send password reset');
    return res.json();
  },

  resetPassword: async (payload: { token: string; new_password: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Password reset failed');
    return res.json();
  },

  setupMfa: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/mfa/setup`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to setup MFA');
    return res.json();
  },

  verifyMfa: async (code: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/mfa/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ code })
    });
    if (!res.ok) throw new Error('MFA verification failed');
    return res.json();
  },

  inviteMember: async (payload: { email: string; full_name: string; role: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/invite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to invite member' }));
      throw new Error(err.detail || 'Failed to invite member');
    }
    return res.json();
  },

  switchTenantAuth: async (targetTenantId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/switch-tenant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ target_tenant_id: targetTenantId })
    });
    if (!res.ok) throw new Error('Failed to switch tenant context');
    return res.json();
  },

  firstLoginChangePassword: async (payload: { new_password: string; current_password?: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/first-login-change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Password change failed' }));
      throw new Error(err.detail || 'Password change failed');
    }
    return res.json();
  },

  logout: async (): Promise<any> => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
    } catch (e) {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('aegisops_token');
      localStorage.removeItem('aegisops_user');
      localStorage.removeItem('aegisops_tenant_id');
    }
  },

  getCompanyUsers: async (tenantId?: string): Promise<any[]> => {
    const url = tenantId ? `${API_BASE}/auth/users?tenant_id=${encodeURIComponent(tenantId)}` : `${API_BASE}/auth/users`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch users' }));
      throw new Error(err.detail || 'Failed to fetch users');
    }
    return res.json();
  },

  getCurrentUserProfile: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch user profile');
    return res.json();
  },

  // ==============================================================
  // ORGANIZATIONS & TEAMS
  // ==============================================================
  getOrganizations: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/organizations`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch organizations');
    return res.json();
  },

  getOrganization: async (orgId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch organization');
    return res.json();
  },

  updateOrganization: async (orgId: string, data: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to update organization');
    return res.json();
  },

  getTeams: async (orgId: string): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}/teams`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch teams');
    return res.json();
  },

  createTeam: async (orgId: string, payload: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}/teams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Failed to create team');
    return res.json();
  },

  getOrganizationMembers: async (orgId: string): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}/members`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch members');
    return res.json();
  },

  updateMemberRole: async (orgId: string, userId: number, role: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/organizations/${orgId}/members/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ role })
    });
    if (!res.ok) throw new Error('Failed to update member role');
    return res.json();
  },

  // ==============================================================
  // RELIABILITY ENGINEERING & SLOS
  // ==============================================================
  getReliabilityOverview: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/reliability/overview`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch reliability metrics');
    return res.json();
  },

  getSlos: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/reliability/slos`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch SLOs');
    return res.json();
  },

  createSlo: async (payload: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/reliability/slos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Failed to create SLO');
    return res.json();
  },

  // ==============================================================
  // SECURITY & AUDIT GOVERNANCE
  // ==============================================================
  getSecurityOverview: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/security/overview`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch security posture');
    return res.json();
  },

  getSecurityEvents: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/v1/security/events`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch security telemetry');
    return res.json();
  },

  // ==============================================================
  // 30 FAILURE CYCLES & MEASURED LOAD TEST
  // ==============================================================
  getFailureCycles: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/cycles`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch failure cycles');
    return res.json();
  },

  rotateFailureCycle: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/cycles/rotate`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to rotate failure cycle');
    return res.json();
  },

  injectFailureCycle: async (scenarioId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/cycles/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ scenario_id: scenarioId })
    });
    if (!res.ok) throw new Error('Failed to inject failure scenario');
    return res.json();
  },

  runMeasuredLoadTest: async (profile: string, targetEvents?: number): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/load-test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ profile, target_events: targetEvents })
    });
    if (!res.ok) throw new Error('Failed to run measured load test');
    return res.json();
  },

  getLatestLoadTest: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/simulations/load-test/latest`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch latest load test results');
    return res.json();
  },

  // ==============================================================
  // INCIDENTS & CLOSED-LOOP RECOVERY VALIDATION
  // ==============================================================
  createIncident: async (payload: any): Promise<Incident> => {
    const res = await fetch(`${API_BASE}/incidents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Failed to create incident scenario');
    return res.json();
  },

  getIncidentAttempts: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/attempts`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch incident attempts');
    return res.json();
  },

  getHistoricalMatches: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/historical-matches`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to fetch historical matches');
    return res.json();
  },

  retryIncidentRemediation: async (incidentId: string, notes?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/retry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ notes: notes || 'Retrying remediation in replica' })
    });
    if (!res.ok) throw new Error('Failed to retry incident remediation');
    return res.json();
  },

  approveIncident: async (incidentId: string, notes?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ notes: notes || 'Approved for production' })
    });
    if (!res.ok) throw new Error('Failed to approve incident');
    return res.json();
  },

  rejectIncident: async (incidentId: string, reason?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ reason: reason || 'Remediation rejected' })
    });
    if (!res.ok) throw new Error('Failed to reject incident');
    return res.json();
  },

  // ==============================================================
  // REAL LIVE TELEMETRY PIPELINE & VERIFICATION
  // ==============================================================
  getTelemetrySources: async (tenantId?: string): Promise<any> => {
    const url = tenantId 
      ? `http://127.0.0.1:8000/api/v1/telemetry/sources?tenant_id=${tenantId}`
      : 'http://127.0.0.1:8000/api/v1/telemetry/sources';
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch telemetry sources');
    return res.json();
  },

  getLiveTelemetryEvents: async (params?: { tenant_id?: string; limit?: number; event_type?: string; service?: string }): Promise<any> => {
    const query = new URLSearchParams();
    if (params?.tenant_id) query.set('tenant_id', params.tenant_id);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.service) query.set('service', params.service);
    const res = await fetch(`http://127.0.0.1:8000/api/v1/telemetry/live-events?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch live telemetry events');
    return res.json();
  },

  getTelemetryJourney: async (identifier: string, tenantId: string = 'shopsphere'): Promise<any> => {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/telemetry/journey/${encodeURIComponent(identifier)}?tenant_id=${encodeURIComponent(tenantId)}`);
    if (!res.ok) throw new Error(`Failed to fetch journey for identifier: ${identifier}`);
    return res.json();
  },

  triggerRealTraffic: async (count: number = 5, operation: string = 'order', tenantId: string = 'shopsphere'): Promise<any> => {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/telemetry/traffic/trigger?count=${count}&operation=${operation}&tenant_id=${tenantId}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to trigger real traffic');
    return res.json();
  },

  controlTelemetrySource: async (action: string, tenantId: string = 'shopsphere'): Promise<any> => {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/telemetry/source/control?action=${action}&tenant_id=${tenantId}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(`Failed to control telemetry source with action: ${action}`);
    return res.json();
  },

  // Early Warnings & Proactive Degradation
  getEarlyWarnings: async (tenantId?: string): Promise<any> => {
    const q = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const res = await fetch(`${API_BASE}/early-warnings/alerts${q}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch early warnings');
    return res.json();
  },

  getEarlyWarningSummary: async (tenantId?: string): Promise<any> => {
    const q = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const res = await fetch(`${API_BASE}/early-warnings/summary${q}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch early warning summary');
    return res.json();
  },

  // -------------------------------------------------------------
  // Incident-Specific RCA & Evidence Package APIs
  // -------------------------------------------------------------
  getIncidentRca: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/rca`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch RCA for incident ${incidentId}`);
    return res.json();
  },

  getIncidentEvidencePackage: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/evidence-package`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch evidence package for incident ${incidentId}`);
    return res.json();
  },

  triggerAiRca: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/ai-rca`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to trigger AI RCA for incident ${incidentId}`);
    return res.json();
  },

  getIncidentDualSolutions: async (incidentId: string, forceRegenerate: boolean = false): Promise<any> => {
    const q = forceRegenerate ? '?force_regenerate=true' : '';
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/dual-solutions${q}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch dual solutions for incident ${incidentId}`);
    return res.json();
  },

  selectIncidentSolution: async (incidentId: string, payload: { solution_source: 'AI_PROPOSED' | 'KNOWLEDGE_BASE'; tenant_id?: string; override_action_key?: string; user?: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/solutions/select`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  },

  addKnowledgeBaseArticle: async (incidentId: string, payload: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/knowledge-base/add`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  },

  getIncidentRecoveryPlan: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/recovery-plan`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch recovery plan for ${incidentId}`);
    return res.json();
  },

  executeRecoveryPlanStep: async (
    incidentId: string,
    payload: { plan_id: string; step_number: number; notes?: string; operator?: string; checklist?: Record<string, boolean> }
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/recovery-plan/execute-step`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  },

  getIncidentRemediationRun: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/remediation-run`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  },

  // -------------------------------------------------------------
  // Isolated Sandbox Recovery & Empirical Validation APIs
  // -------------------------------------------------------------
  getIncidentSandbox: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch sandbox state for ${incidentId}`);
    return res.json();
  },

  initIncidentSandbox: async (incidentId: string, action?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/init`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    if (!res.ok) throw new Error(`Failed to initialize sandbox for ${incidentId}`);
    return res.json();
  },

  runFullSandboxCycle: async (incidentId: string, action?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/run-cycle`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    if (!res.ok) throw new Error(`Failed to run sandbox recovery cycle for ${incidentId}`);
    return res.json();
  },

  getLatestSandboxExecution: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/execution/latest`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch latest execution for ${incidentId}`);
    return res.json();
  },

  getSandboxExecution: async (incidentId: string, executionId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/execution/${encodeURIComponent(executionId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch execution ${executionId}`);
    return res.json();
  },


  refineAndRetrySandbox: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/refine-retry`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to refine recovery for ${incidentId}`);
    return res.json();
  },

  getSandboxHistory: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/history`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch sandbox history for ${incidentId}`);
    return res.json();
  },

  getRecoveryProof: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/proof`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch recovery proof for ${incidentId}`);
    return res.json();
  },

  getDecisionScores: async (incidentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/sandbox/decision-scores`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch recovery decision scores for ${incidentId}`);
    return res.json();
  },

  getVerifiedRecoveryPatterns: async (tenantId: string = 'demo-tenant'): Promise<any> => {
    const res = await fetch(`${API_BASE}/incidents/recovery/verified-patterns?tenant_id=${encodeURIComponent(tenantId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch verified recovery patterns');
    return res.json();
  },

  // -------------------------------------------------------------
  // Conversational SRE Assistant APIs
  // -------------------------------------------------------------
  chatWithSre: async (message: string, conversationId?: string, incidentId?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/sre-assistant/chat`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, incident_id: incidentId })
    });
    if (!res.ok) throw new Error('Failed to communicate with SRE Assistant');
    return res.json();
  },

  getSreConversations: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/sre-assistant/conversations`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to list SRE conversations');
    return res.json();
  },

  getSreConversation: async (conversationId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/sre-assistant/conversations/${encodeURIComponent(conversationId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to load conversation ${conversationId}`);
    return res.json();
  },

  // -------------------------------------------------------------
  // AI Provider & Key Configuration APIs (Strictly Masked)
  // -------------------------------------------------------------
  getAiConfigStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/ai-config/status`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch AI configuration status');
    return res.json();
  },

  getDiscoveredGeminiModels: async (apiKey?: string, forceRefresh?: boolean): Promise<any> => {
    const params = new URLSearchParams();
    if (apiKey) params.append('api_key', apiKey);
    if (forceRefresh) params.append('force_refresh', 'true');
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/ai-config/models${qs}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to discover Gemini models');
    return res.json();
  },

  updateAiConfig: async (config: {
    rca_ai_provider?: string;
    rca_ai_model?: string;
    rca_ai_pinned?: boolean;
    rca_ai_api_key?: string;
    sre_ai_provider?: string;
    sre_ai_model?: string;
    sre_ai_pinned?: boolean;
    sre_ai_api_key?: string;
    reasoning_effort?: string;
    validation_ai_provider?: string;
    validation_ai_model?: string;
    validation_ai_api_key?: string;
    validation_ai_timeout_sec?: number;
    validation_ai_enabled?: boolean;
    use_same_key_for_both?: boolean;
    max_recovery_attempts?: number;
  }): Promise<any> => {
    const res = await fetch(`${API_BASE}/ai-config/update`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error('Failed to update AI configuration');
    return res.json();
  },

  testAiConnection: async (payload: string | { target: string; api_key?: string; provider?: string; model?: string; reasoning_effort?: string } = 'rca_ai'): Promise<any> => {
    const body = typeof payload === 'string' ? { target: payload } : payload;
    const target = body.target || 'rca_ai';
    const res = await fetch(`${API_BASE}/ai-config/test-connection`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`Failed to test connection for ${target}`);
    return res.json();
  },

  getTelemetryAnalysis: async (timeRange: string = '15m'): Promise<any> => {
    const res = await fetch(`${API_BASE}/services/observability/telemetry-analysis?time_range=${timeRange}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch telemetry analysis');
    return res.json();
  },

  // -------------------------------------------------------------
  // Testing & Simulation Lab APIs (Parts 15-21, 33)
  // -------------------------------------------------------------
  getTestingStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/testing/status`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch testing lab status');
    return res.json();
  },

  getTestingScenarios: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/testing/scenarios`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch failure scenarios');
    return res.json();
  },

  runTestingScenario: async (payload: {
    scenario_id: string;
    service?: string;
    severity?: string;
    duration_sec?: number;
    tenant_id?: string;
    simulate_refinement?: boolean;
    simulate_unresolved?: boolean;
    simulate_side_effect?: boolean;
  }): Promise<any> => {
    const res = await fetch(`${API_BASE}/testing/run`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Test execution failed' }));
      throw new Error(err.detail || 'Test execution failed');
    }
    return res.json();
  },

  getTestingRuns: async (params?: { service?: string; failure_type?: string; severity?: string; result?: string; limit?: number }): Promise<any[]> => {
    const query = new URLSearchParams();
    if (params?.service && params.service !== 'all') query.set('service', params.service);
    if (params?.failure_type && params.failure_type !== 'all') query.set('failure_type', params.failure_type);
    if (params?.severity && params.severity !== 'all') query.set('severity', params.severity);
    if (params?.result && params.result !== 'all') query.set('result', params.result);
    if (params?.limit) query.set('limit', params.limit.toString());
    const res = await fetch(`${API_BASE}/testing/runs?${query.toString()}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch test runs');
    return res.json();
  },

  getTestingRun: async (testId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/testing/runs/${encodeURIComponent(testId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch test run ${testId}`);
    return res.json();
  },

  getActiveTestingRun: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/testing/runs/active`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch active test run');
    return res.json();
  },


  getTestingMatrix: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/testing/matrix`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch chaos matrix');
    return res.json();
  },

  // Canonical Operational State & Truth Auditor (Parts 1, 8, 39)
  getServicesStatus: async (tenantId?: string): Promise<{
    tenant_id: string;
    checked_at: string;
    system_health: {
      health_score: number;
      counts: Record<string, number>;
      total_services: number;
      formula: string;
      calculation_details: Record<string, string>;
    };
    services: CanonicalOperationalState[];
  }> => {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const res = await fetch(`${API_BASE}/services/status${query}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch canonical services status');
    return res.json();
  },

  getSingleServiceState: async (serviceId: string, tenantId?: string): Promise<CanonicalOperationalState> => {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const res = await fetch(`${API_BASE}/services/${encodeURIComponent(serviceId)}/state${query}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch canonical state for ${serviceId}`);
    return res.json();
  },

  getSystemConsistency: async (tenantId?: string): Promise<SystemConsistencyAudit> => {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    const res = await fetch(`${API_BASE}/system/consistency${query}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch system consistency report');
    return res.json();
  },

  // Architecture & Operational Workflow Models
  getArchitectureInventory: async (tenantId: string = 'shopsphere') => {
    const res = await fetch(`${API_BASE}/architecture/inventory?tenant_id=${encodeURIComponent(tenantId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch architecture inventory');
    return res.json();
  },

  getArchitectureWorkflows: async (tenantId: string = 'shopsphere') => {
    const res = await fetch(`${API_BASE}/architecture/workflows?tenant_id=${encodeURIComponent(tenantId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch architecture workflows');
    return res.json();
  },

  triggerArchitectureDiscovery: async (tenantId: string = 'shopsphere', source: string = 'AUTHORIZED_CLOUD_PROBE') => {
    const res = await fetch(`${API_BASE}/architecture/discover?tenant_id=${encodeURIComponent(tenantId)}&source=${encodeURIComponent(source)}`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to trigger architecture discovery');
    return res.json();
  },

  // Isolated Remediation Lab & Multi-Candidate Trials
  runRemediationTrial: async (data: { incident_id: string; tenant_id?: string; candidates?: any[]; incident_context?: any }) => {
    const res = await fetch(`${API_BASE}/testing/remediation-trial`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to execute remediation trial');
    return res.json();
  },

  listRemediationTrials: async (limit: number = 20) => {
    const res = await fetch(`${API_BASE}/testing/remediation-trials?limit=${limit}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch remediation trials');
    return res.json();
  },

  getActiveRemediationTrial: async () => {
    const res = await fetch(`${API_BASE}/testing/remediation-trials/active`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch active remediation trial');
    return res.json();
  },

  getRemediationTrialDetail: async (runId: string) => {
    const res = await fetch(`${API_BASE}/testing/remediation-trials/${encodeURIComponent(runId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch remediation trial details');
    return res.json();
  },

  validateNineLayers: async (data: any) => {
    const res = await fetch(`${API_BASE}/testing/validate-nine-layers`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to run 9-layer validation');
    return res.json();
  },

  requestIndependentReview: async (data: any) => {
    const res = await fetch(`${API_BASE}/testing/independent-review`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to request independent AI review');
    return res.json();
  },

  // Verified Knowledge Base Resolutions
  recordIncidentResolution: async (data: any) => {
    const res = await fetch(`${API_BASE}/testing/resolutions`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to record resolution');
    return res.json();
  },

  listIncidentResolutions: async (tenantId?: string, status?: string) => {
    const params = new URLSearchParams();
    if (tenantId) params.append('tenant_id', tenantId);
    if (status) params.append('status', status);
    const res = await fetch(`${API_BASE}/testing/resolutions?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to list resolutions');
    return res.json();
  },

  searchResolutionsWithCompatibility: async (data: { incident: any; tenant_id?: string }) => {
    const res = await fetch(`${API_BASE}/testing/resolutions/search`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to search resolutions');
    return res.json();
  },

  // -------------------------------------------------------------------------
  // Digital Twin & Recovery Sandbox (Replica Lab)
  // -------------------------------------------------------------------------
  getReplicaInventory: async (tenantId?: string): Promise<any> => {
    const params = new URLSearchParams();
    if (tenantId && tenantId !== 'all' && tenantId !== '*') params.append('tenant_id', tenantId);
    const res = await fetch(`${API_BASE}/replica/inventory?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch replica inventory');
    return res.json();
  },

  createReplica: async (data: { tenant_id?: string; target_service?: string; environment_type?: string }): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/create`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create replica instance');
    return res.json();
  },

  getReplicaScenarios: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/scenarios`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch replica scenarios');
    return res.json();
  },

  injectFaultToReplica: async (replicaId: string, scenarioId: string, parameters?: any): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/${encodeURIComponent(replicaId)}/fault-inject`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId, parameters })
    });
    if (!res.ok) throw new Error('Failed to inject fault to replica');
    return res.json();
  },

  resetReplica: async (replicaId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/${encodeURIComponent(replicaId)}/reset`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to reset replica');
    return res.json();
  },

  runReplicaExperiment: async (data: {
    incident_id: string;
    tenant_id?: string;
    replica_id?: string;
    scenario_id?: string;
    target_service?: string;
    candidates?: any[];
  }): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/experiments/run`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to execute replica experiment');
    return res.json();
  },

  getReplicaExperiments: async (tenantId?: string, incidentId?: string): Promise<any> => {
    const params = new URLSearchParams();
    if (tenantId && tenantId !== 'all' && tenantId !== '*') params.append('tenant_id', tenantId);
    if (incidentId) params.append('incident_id', incidentId);
    const res = await fetch(`${API_BASE}/replica/experiments?${params.toString()}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch replica experiments');
    return res.json();
  },

  getReplicaExperiment: async (experimentId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/experiments/${encodeURIComponent(experimentId)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to fetch experiment ${experimentId}`);
    return res.json();
  },

  approveReplicaExperiment: async (experimentId: string, approver?: string, comments?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/experiments/${encodeURIComponent(experimentId)}/approve`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver, comments })
    });
    if (!res.ok) throw new Error('Failed to approve replica experiment');
    return res.json();
  },

  deployReplicaExperimentToTarget: async (experimentId: string, operator?: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/replica/experiments/${encodeURIComponent(experimentId)}/deploy-to-target`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator })
    });
    if (!res.ok) throw new Error('Failed to deploy experiment to target');
    return res.json();
  },

  generateTenantDemoData: async (tenantId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/v1/tenants/${encodeURIComponent(tenantId)}/generate-demo-data`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to generate demo data for tenant ${tenantId}`);
    return res.json();
  }
};




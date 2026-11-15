import React, { useState, useEffect } from 'react';
import { AppLayout } from './layouts/AppLayout';
import { OperationsCenterPage } from './pages/OperationsCenterPage';
import { LiveTelemetryPage } from './pages/LiveTelemetryPage';
import { ReplayPage } from './pages/ReplayPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { DashboardPage } from './pages/DashboardPage';
import { ObservatoryPage } from './pages/ObservatoryPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { RcaPage } from './pages/RcaPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { RunbooksPage } from './pages/RunbooksPage';
import { RecoveryPage } from './pages/RecoveryPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { StoragePage } from './pages/StoragePage';
import { LogsPage } from './pages/LogsPage';
import { AssistantPage } from './pages/AssistantPage';
import { DemoPage } from './pages/DemoPage';
import { SettingsPage } from './pages/SettingsPage';
import { LogsDashboard } from './pages/LogsDashboard';
import { DependencyMapPage } from './pages/DependencyMapPage';
import { TelemetryExplorerPage } from './pages/TelemetryExplorerPage';
import { LiveTelemetryVerificationPage } from './pages/LiveTelemetryVerificationPage';
import { PlatformAdminPage } from './pages/PlatformAdminPage';
import { AuthPages } from './pages/AuthPages';
import { TestingSimulationLabPage } from './pages/TestingSimulationLabPage';
import { IncidentNotificationToast } from './components/IncidentNotificationToast';
import { TenantProvider, useTenant } from './context/TenantContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { ShieldAlert } from 'lucide-react';

import { useWebSocket } from './hooks/useWebSocket';
import { api } from './services/api';
import type { 
  ServiceDetail, 
  Incident, 
  ApprovalTicket, 
  ServiceMetric, 
  EnvironmentMode,
  TelemetryMode,
  ContinuousTelemetryStatus,
  FailureSchedulerStatus,
  TelemetryDiagnosticItem,
  DependencyGraphData
} from './types';

function AuthenticatedAppContent() {
  const { isAuthenticated, currentUser, activeTenant } = useTenant();

  const getInitialTab = () => {
    const path = window.location.pathname.toLowerCase();
    const hash = window.location.hash.toLowerCase();
    const searchParams = new URLSearchParams(window.location.search);
    const tabParam = (searchParams.get('tab') || '').toLowerCase();

    if (tabParam === 'recovery' || path.includes('/recovery') || hash.includes('recovery')) {
      return 'recovery';
    }
    if (tabParam === 'rca' || path.includes('/rca') || hash.includes('rca')) {
      return 'rca';
    }
    if (tabParam === 'approvals' || path.includes('/approvals') || hash.includes('approvals')) {
      return 'approvals';
    }
    if (path.includes('/admin/logs') || path === '/logs/live' || hash.includes('logs-live') || hash.includes('admin/logs')) {
      return 'live_logs';
    }
    if (path.includes('/login') || hash.includes('login') || path === '/auth' || hash.includes('auth')) {
      return 'auth';
    }
    return 'dashboard';
  };

  const [activeTab, setActiveTab] = useState<string>(getInitialTab);
  const [environmentMode, setEnvironmentMode] = useState<EnvironmentMode>('DEMO');
  const [operatingMode, setOperatingMode] = useState<TelemetryMode>('CONTROLLED_DEMO');
  const [services, setServices] = useState<ServiceDetail[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([]);
  const [healthScore, setHealthScore] = useState<number>(100.0);
  const [storagePct, setStoragePct] = useState<number>(82.4);
  const [storageHours, setStorageHours] = useState<number>(10.0);
  const [continuousStatus, setContinuousStatus] = useState<ContinuousTelemetryStatus | undefined>(undefined);
  const [schedulerStatus, setSchedulerStatus] = useState<FailureSchedulerStatus | undefined>(undefined);
  const [diagnostics, setDiagnostics] = useState<TelemetryDiagnosticItem[]>([]);
  const [targetedApprovalId, setTargetedApprovalId] = useState<string | undefined>(undefined);
  const [targetedDependencyService, setTargetedDependencyService] = useState<string | undefined>(undefined);
  const [targetedIncidentId, setTargetedIncidentId] = useState<string | undefined>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('incident') || undefined;
  });

  const handleOperatingModeChange = async (mode: TelemetryMode) => {
    setOperatingMode(mode);
    try {
      await api.setTelemetryMode(mode);
    } catch (e) {
      // Handled
    }
  };

  // Live WebSocket Connection
  const { data: wsData, isConnected: isWsConnected } = useWebSocket('ws://127.0.0.1:8000/ws/telemetry');

  // Fallback Poller for Initial Data & Robustness
  const refreshData = async () => {
    try {
      const [svcData, incData, appData] = await Promise.all([
        api.getServices(),
        api.getIncidents(),
        api.getApprovals()
      ]);
      setServices(svcData);
      setIncidents(incData);
      setApprovals(appData);
    } catch (e) {
      // Backend starting up
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      refreshData();
      const interval = setInterval(refreshData, 2500);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, activeTenant.id]);

  useEffect(() => {
    const handleUrlChange = () => {
      const path = window.location.pathname.toLowerCase();
      const hash = window.location.hash.toLowerCase();
      const searchParams = new URLSearchParams(window.location.search);
      const tabParam = (searchParams.get('tab') || '').toLowerCase();
      const incParam = searchParams.get('incident');

      if (incParam) {
        setTargetedIncidentId(incParam);
      }

      if (tabParam === 'recovery' || path.includes('/recovery') || hash.includes('recovery')) {
        setActiveTab('recovery');
      } else if (tabParam === 'rca' || path.includes('/rca') || hash.includes('rca')) {
        setActiveTab('rca');
      } else if (tabParam === 'approvals' || path.includes('/approvals') || hash.includes('approvals')) {
        setActiveTab('approvals');
      } else if (path.includes('/admin/logs') || path === '/logs/live' || hash.includes('logs-live') || hash.includes('admin/logs')) {
        setActiveTab('live_logs');
      } else if (path.includes('/login') || hash.includes('login') || path === '/auth' || hash.includes('auth')) {
        setActiveTab('auth');
      } else if (path.includes('/dashboard') || hash.includes('dashboard')) {
        setActiveTab('dashboard');
      }
    };
    window.addEventListener('popstate', handleUrlChange);
    window.addEventListener('hashchange', handleUrlChange);

    return () => {
      window.removeEventListener('popstate', handleUrlChange);
      window.removeEventListener('hashchange', handleUrlChange);
    };
  }, []);

  // Update real-time state immediately upon WebSocket push
  useEffect(() => {
    if (wsData) {
      setHealthScore(wsData.health_score);
      setStoragePct(wsData.storage_percentage);
      setStorageHours(wsData.storage_critical_hours);
      if (wsData.environment_mode) {
        setEnvironmentMode(wsData.environment_mode as EnvironmentMode);
      }
      
      if (wsData.operating_mode) {
        setOperatingMode(wsData.operating_mode);
      }
      if (wsData.continuous_telemetry) {
        setContinuousStatus(wsData.continuous_telemetry);
      }
      if (wsData.failure_scheduler) {
        setSchedulerStatus(wsData.failure_scheduler);
      }
      if (wsData.diagnostics) {
        setDiagnostics(wsData.diagnostics);
      }
      
      if ((wsData as any).all_incidents && Array.isArray((wsData as any).all_incidents)) {
        setIncidents((wsData as any).all_incidents);
      } else if ((wsData as any).active_incidents && Array.isArray((wsData as any).active_incidents)) {
        const liveActive = (wsData as any).active_incidents as Incident[];
        setIncidents(prev => {
          const activeMap = new Map(liveActive.map(i => [i.incident_id, i]));
          const merged = liveActive.slice();
          for (const oldInc of prev) {
            if (!activeMap.has(oldInc.incident_id)) {
              merged.push(oldInc);
            }
          }
          return merged;
        });
      }
      if ((wsData as any).type === 'INCIDENT_CREATED' || (wsData as any).event_type === 'INCIDENT_CREATED') {
        const newInc = (wsData as any).incident;
        if (newInc) {
          setIncidents(prev => {
            if (prev.some(i => i.incident_id === newInc.incident_id)) {
              return prev.map(i => i.incident_id === newInc.incident_id ? { ...i, ...newInc } : i);
            }
            return [newInc, ...prev];
          });
        }
      }
      if ((wsData as any).type === 'INCIDENT_UPDATED' || (wsData as any).event_type === 'INCIDENT_UPDATED') {
        const updInc = (wsData as any).incident;
        if (updInc) {
          setIncidents(prev => prev.map(i => i.incident_id === updInc.incident_id ? { ...i, ...updInc } : i));
        }
      }
      if ((wsData as any).type === 'INCIDENT_RESOLVED' || (wsData as any).event_type === 'INCIDENT_RESOLVED') {
        const resId = (wsData as any).incident_id;
        if (resId) {
          setIncidents(prev => prev.map(i => i.incident_id === resId ? { ...i, status: 'RESOLVED', lifecycle_state: 'VALIDATED' } : i));
        }
      }
      if ((wsData as any).type === 'RECOVERY_STARTED') {
        const rId = (wsData as any).incident_id;
        if (rId) {
          setIncidents(prev => prev.map(i => i.incident_id === rId ? { ...i, status: 'RECOVERING', lifecycle_state: 'RECOVERING' } : i));
        }
      }
      if ((wsData as any).type === 'VERIFICATION_STARTED') {
        const vId = (wsData as any).incident_id;
        if (vId) {
          setIncidents(prev => prev.map(i => i.incident_id === vId ? { ...i, status: 'VERIFYING', lifecycle_state: 'VERIFYING' } : i));
        }
      }

      if ((wsData as any).type === 'APPROVAL_CREATED' || (wsData as any).event_type === 'APPROVAL_CREATED' || (wsData as any).type === 'APPROVAL_DECISION' || (wsData as any).event_type === 'APPROVAL_DECISION') {
        refreshData();
      }

      // Update services from WS
      if (wsData.services) {
        setServices(prev => {
          return prev.map(s => {
            const match = wsData.services.find(m => m.service_name === s.name);
            const hMatch = wsData.services_health?.[s.name];
            if (match) {
              return {
                ...s,
                status: hMatch?.state || (match.healthy ? 'HEALTHY' : 'CRASHED'),
                healthy: match.healthy,
                cpu_percent: match.cpu_percent,
                memory_mb: match.memory_mb,
                request_count: match.request_count,
                error_count: match.error_count,
                error_rate: match.error_rate,
                latency_p50_ms: match.latency_p50_ms,
                latency_p95_ms: match.latency_p95_ms,
                active_connections: match.active_connections,
                anomaly_score: match.anomaly_score,
                is_anomaly: match.is_anomaly
              };
            }
            return s;
          });
        });
      }
    }
  }, [wsData]);

  // Convert ServiceDetail to ServiceMetric list for Dashboard
  const serviceMetricsList: ServiceMetric[] = services.map(s => ({
    service_name: s.name,
    timestamp: new Date().toISOString(),
    status: s.status,
    healthy: s.healthy,
    cpu_percent: s.cpu_percent,
    memory_mb: s.memory_mb,
    request_count: s.request_count,
    error_count: s.error_count,
    error_rate: s.error_rate,
    latency_p50_ms: s.latency_p50_ms,
    latency_p95_ms: s.latency_p95_ms,
    active_connections: s.active_connections,
    anomaly_score: s.anomaly_score,
    is_anomaly: s.is_anomaly
  }));

  const pendingApprovalsCount = approvals.filter(
    t => t.status === 'PENDING' || t.status === 'PENDING_APPROVAL' || t.status === 'AWAITING_APPROVAL'
  ).length;

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#080C14] text-slate-100 flex items-center justify-center p-4">
        <AuthPages onLoginSuccess={() => setActiveTab('dashboard')} />
      </div>
    );
  }

  if (currentUser?.must_change_password) {
    return (
      <div className="min-h-screen bg-[#080C14] text-slate-100 flex items-center justify-center p-4">
        <AuthPages initialMode="first-login-change" onLoginSuccess={() => setActiveTab('dashboard')} />
      </div>
    );
  }

  return (
    <AppLayout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      healthScore={healthScore}
      pendingApprovalsCount={pendingApprovalsCount}
      activeIncidentsCount={incidents.filter(i => i.status !== 'RESOLVED').length}
      isWsConnected={isWsConnected}
      environmentMode={environmentMode}
      setEnvironmentMode={setEnvironmentMode}
      operatingMode={operatingMode}
      onOperatingModeChange={handleOperatingModeChange}
    >

        {activeTab === 'operations' && (
          <OperationsCenterPage incidents={incidents} setActiveTab={setActiveTab} />
        )}

        {activeTab === 'telemetry_verification' && (
          <LiveTelemetryVerificationPage />
        )}

        {activeTab === 'telemetry_explorer' && (
          <TelemetryExplorerPage />
        )}

        {activeTab === 'telemetry' && (
          <LiveTelemetryPage
          operatingMode={operatingMode}
          onModeChange={handleOperatingModeChange}
          streamStatus={wsData?.stream_status}
          continuousStatus={continuousStatus}
          schedulerStatus={schedulerStatus}
          diagnostics={diagnostics}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'historical' && (
        <ReplayPage setActiveTab={setActiveTab} />
      )}

      {activeTab === 'simulator' && (
        <SimulatorPage setActiveTab={setActiveTab} />
      )}

      {activeTab === 'testing_lab' && (
        <TestingSimulationLabPage />
      )}



      {activeTab === 'dashboard' && (
        <DashboardPage
          healthScore={healthScore}
          services={serviceMetricsList}
          incidents={incidents}
          approvals={approvals}
          storagePct={storagePct}
          storageHours={storageHours}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'dependencies' && (
        <DependencyMapPage
          services={services}
          incidents={incidents}
          liveGraphData={wsData?.dependencies}
          highlightedServiceId={targetedDependencyService}
          setActiveTab={setActiveTab}
          onSelectIncident={(incId) => {
            setTargetedIncidentId(incId);
          }}
          onNavigateToObservability={(svcId) => {
            setTargetedDependencyService(svcId);
            setActiveTab('observatory');
          }}
        />
      )}

      {activeTab === 'observatory' && (
        <ObservatoryPage 
          services={services} 
          incidents={incidents}
          initialSelectedService={targetedDependencyService}
          initialSelectedIncidentId={targetedIncidentId}
          onSelectIncident={(incId) => setTargetedIncidentId(incId)}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'incidents' && (
        <IncidentsPage 
          incidents={incidents} 
          setActiveTab={setActiveTab}
          selectedIncidentIdProp={targetedIncidentId}
          onNavigateToDependencyMap={(svcId) => {
            setTargetedDependencyService(svcId);
            setActiveTab('dependencies');
          }}
          onSelectIncidentForApproval={(incId) => {
            const existing = approvals.find(a => a.incident_id === incId);
            setTargetedApprovalId(existing ? existing.approval_id : incId);
            setActiveTab('approvals');
          }}
        />
      )}

      {activeTab === 'rca' && (
        <RcaPage 
          incidents={incidents} 
          setActiveTab={setActiveTab} 
          selectedIncidentIdProp={targetedIncidentId}
          onSelectIncident={setTargetedIncidentId}
        />
      )}

      {activeTab === 'approvals' && (
        <ApprovalsPage 
          approvals={approvals} 
          incidents={incidents}
          selectedApprovalId={targetedApprovalId}
          setActiveTab={setActiveTab}
          onSelectIncident={(incId) => setTargetedIncidentId(incId)}
          onActionComplete={refreshData} 
        />
      )}

      {activeTab === 'runbooks' && (
        <RunbooksPage />
      )}

      {activeTab === 'recovery' && (
        <RecoveryPage 
          incidents={incidents}
          selectedIncidentIdProp={targetedIncidentId}
          onSelectIncident={setTargetedIncidentId}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'integrations' && (
        <IntegrationsPage />
      )}

      {activeTab === 'storage' && (
        <StoragePage />
      )}

      {activeTab === 'logs' && (
        <LogsPage />
      )}

      {activeTab === 'assistant' && (
        <AssistantPage 
          incidents={incidents}
          selectedIncidentIdProp={targetedIncidentId}
          onSelectIncident={setTargetedIncidentId}
          setActiveTab={setActiveTab}
        />
      )}

      {activeTab === 'demo' && (
        <DemoPage setActiveTab={setActiveTab} />
      )}

      {activeTab === 'settings' && (
        <SettingsPage />
      )}

      {activeTab === 'live_logs' && (
        <LogsDashboard />
      )}

      {activeTab === 'platform_admin' && (
        (currentUser?.is_platform_admin || currentUser?.role === 'PLATFORM_OWNER_ADMIN') ? (
          <PlatformAdminPage />
        ) : (
          <div className="max-w-xl mx-auto mt-16 p-8 rounded-2xl bg-slate-900/90 border border-rose-500/30 text-center space-y-4 shadow-2xl">
            <div className="inline-flex p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
              <ShieldAlert className="h-8 w-8" />
            </div>
            <h2 className="text-xl font-bold text-white">Platform Owner Access Required</h2>
            <p className="text-sm text-slate-400">
              Your account ({currentUser?.username} - {currentUser?.role}) is scoped to company <span className="font-mono text-cyan-300 font-bold">{activeTenant.name}</span>. Cross-company platform administration is restricted to Platform Owner Admins.
            </p>
            <button
              onClick={() => setActiveTab('dashboard')}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs transition"
            >
              Return to Company Dashboard
            </button>
          </div>
        )
      )}

      <IncidentNotificationToast
        activeIncidents={incidents}
        pendingApprovals={approvals}
        onNavigateToIncident={(incId) => {
          setTargetedIncidentId(incId);
          setActiveTab('incidents');
        }}
        onNavigateToApproval={(appId) => {
          setTargetedApprovalId(appId);
          setActiveTab('approvals');
        }}
        onNavigateToIncidents={() => setActiveTab('incidents')}
        onNavigateToApprovals={() => setActiveTab('approvals')}
      />
    </AppLayout>
  );
}

export function App() {
  return (
    <TenantProvider>
      <WorkspaceProvider>
        <AuthenticatedAppContent />
      </WorkspaceProvider>
    </TenantProvider>
  );
}

export default App;

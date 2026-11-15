import React, { createContext, useContext, useState, useEffect } from 'react';

export interface RecoveryWorkspaceState {
  selectedIncId: string;
  selectedAction: string;
  isProcessing: boolean;
  cycleStep: string;
  sandbox: any | null;
  recoveryProof: any | null;
  elapsedSec: number;
  startTime: number | null;
  errorMsg: string | null;
}

export interface SimulationWorkspaceState {
  selectedScenarioId: string;
  selectedService: string;
  selectedSeverity: string;
  durationSec: number;
  trafficLevel: string;
  simulateRefinement: boolean;
  simulateUnresolved: boolean;
  simulateSideEffect: boolean;
  activeTab: 'catalog' | 'timeline' | 'matrix' | 'history' | 'remediation_lab' | 'architecture' | 'resolutions';
  isRunning: boolean;
  currentRun: any | null;
}

export interface AssistantWorkspaceState {
  conversationId: string;
  selectedIncId: string;
  messages: any[];
  isLoading: boolean;
  savedConversations: any[];
}

interface WorkspaceContextType {
  selectedIncidentId: string | null;
  setSelectedIncidentId: (id: string | null) => void;
  
  recoveryState: RecoveryWorkspaceState;
  updateRecoveryState: (patch: Partial<RecoveryWorkspaceState>) => void;
  resetRecoveryState: () => void;

  simulationState: SimulationWorkspaceState;
  updateSimulationState: (patch: Partial<SimulationWorkspaceState>) => void;
  resetSimulationState: () => void;

  assistantState: AssistantWorkspaceState;
  updateAssistantState: (patch: Partial<AssistantWorkspaceState>) => void;
}

const defaultRecoveryState: RecoveryWorkspaceState = {
  selectedIncId: '',
  selectedAction: 'RESET_CONNECTION_POOL',
  isProcessing: false,
  cycleStep: 'READY',
  sandbox: null,
  recoveryProof: null,
  elapsedSec: 0,
  startTime: null,
  errorMsg: null,
};

const defaultSimulationState: SimulationWorkspaceState = {
  selectedScenarioId: 'DATABASE_CONNECTION_EXHAUSTION',
  selectedService: 'database-service',
  selectedSeverity: 'CRITICAL',
  durationSec: 30,
  trafficLevel: 'High',
  simulateRefinement: false,
  simulateUnresolved: false,
  simulateSideEffect: false,
  activeTab: 'catalog',
  isRunning: false,
  currentRun: null,
};

const defaultAssistantState: AssistantWorkspaceState = {
  conversationId: `CONV-${Date.now()}`,
  selectedIncId: '',
  messages: [],
  isLoading: false,
  savedConversations: [],
};

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 1. Persistent Selected Incident ID
  const [selectedIncidentId, setSelectedIncidentIdState] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('aegisops_selected_incident') || null;
    } catch {
      return null;
    }
  });

  const setSelectedIncidentId = (id: string | null) => {
    setSelectedIncidentIdState(id);
    try {
      if (id) {
        sessionStorage.setItem('aegisops_selected_incident', id);
      } else {
        sessionStorage.removeItem('aegisops_selected_incident');
      }
    } catch {
      // ignore
    }
  };

  // 2. Recovery & Validation Workspace State
  const [recoveryState, setRecoveryState] = useState<RecoveryWorkspaceState>(defaultRecoveryState);

  const updateRecoveryState = (patch: Partial<RecoveryWorkspaceState>) => {
    setRecoveryState(prev => ({ ...prev, ...patch }));
  };

  const resetRecoveryState = () => {
    setRecoveryState(defaultRecoveryState);
  };

  // 3. Testing & Simulation Lab Workspace State
  const [simulationState, setSimulationState] = useState<SimulationWorkspaceState>(defaultSimulationState);

  const updateSimulationState = (patch: Partial<SimulationWorkspaceState>) => {
    setSimulationState(prev => ({ ...prev, ...patch }));
  };

  const resetSimulationState = () => {
    setSimulationState(defaultSimulationState);
  };

  // 4. SRE Assistant Workspace State
  const [assistantState, setAssistantState] = useState<AssistantWorkspaceState>(defaultAssistantState);

  const updateAssistantState = (patch: Partial<AssistantWorkspaceState>) => {
    setAssistantState(prev => ({ ...prev, ...patch }));
  };

  return (
    <WorkspaceContext.Provider
      value={{
        selectedIncidentId,
        setSelectedIncidentId,
        recoveryState,
        updateRecoveryState,
        resetRecoveryState,
        simulationState,
        updateSimulationState,
        resetSimulationState,
        assistantState,
        updateAssistantState,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = (): WorkspaceContextType => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
};

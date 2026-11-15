import React, { useState } from 'react';
import { 
  Shield, 
  Activity, 
  Server, 
  AlertTriangle, 
  FileSearch, 
  CheckSquare, 
  Zap, 
  HardDrive, 
  FileText, 
  Bot, 
  PlayCircle, 
  Settings, 
  Radio, 
  RefreshCw, 
  Sparkles,
  Network,
  FileCode,
  Terminal,
  Cpu,
  Cloud,
  PlusCircle,
  Users,
  Lock,
  Building2,
  Compass,
  FlaskConical,
  Database,
  LogOut
} from 'lucide-react';
import { api } from '../services/api';
import type { EnvironmentMode, TelemetryMode } from '../types';
import { useTenant } from '../context/TenantContext';
import { OnboardingWizardModal } from '../components/OnboardingWizardModal';

interface AppLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  healthScore: number;
  pendingApprovalsCount: number;
  activeIncidentsCount: number;
  isWsConnected: boolean;
  environmentMode: EnvironmentMode;
  setEnvironmentMode: (mode: EnvironmentMode) => void;
  operatingMode?: TelemetryMode;
  onOperatingModeChange?: (mode: TelemetryMode) => void;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  children,
  activeTab,
  setActiveTab,
  healthScore,
  pendingApprovalsCount,
  activeIncidentsCount,
  isWsConnected,
  environmentMode,
  setEnvironmentMode,
  operatingMode = 'CONTROLLED_DEMO',
  onOperatingModeChange
}) => {
  const [isResetting, setIsResetting] = useState(false);
  const { 
    activeTenant, 
    availableTenants, 
    currentUser, 
    switchTenant, 
    logout,
    isOnboardingOpen, 
    openOnboarding, 
    closeOnboarding 
  } = useTenant();

  const handleResetAll = async () => {
    setIsResetting(true);
    try {
      await api.resetLogHubReplay();
      setTimeout(() => setIsResetting(false), 800);
    } catch (e) {
      setIsResetting(false);
    }
  };

  interface NavItem {
    id: string;
    label: string;
    icon: any;
    isSpecial?: boolean;
    highlight?: boolean;
    badge?: string | number;
    badgeColor?: string;
  }

  interface NavSection {
    title: string;
    items: NavItem[];
  }

  const navSections: NavSection[] = [
    {
      title: 'CORE PLATFORM',
      items: [
        { id: 'dashboard', label: 'Executive Overview', icon: Activity, highlight: true },
        { id: 'observatory', label: 'Operational Observability', icon: Server },
        { 
          id: 'incidents', 
          label: 'Incident Center', 
          icon: AlertTriangle,
          badge: activeIncidentsCount > 0 ? activeIncidentsCount : undefined,
          badgeColor: 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
        },
        { id: 'rca', label: 'Root Cause Analysis', icon: FileSearch, highlight: true },
        { id: 'recovery', label: 'Recovery & Validation', icon: Zap },
        { 
          id: 'approvals', 
          label: 'Approval Center', 
          icon: CheckSquare,
          badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
          badgeColor: 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
        },
        { 
          id: 'testing_lab', 
          label: 'Replica Lab & Digital Twin', 
          icon: FlaskConical, 
          badge: 'TWIN', 
          badgeColor: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono', 
          highlight: true 
        },
        { id: 'settings', label: 'Settings & Integrations', icon: Settings },
      ]
    },
    {
      title: 'DEEP DIAGNOSTICS',
      items: [
        { id: 'dependencies', label: 'Service Dependency Map', icon: Network },
        { id: 'telemetry', label: 'Live Telemetry Stream', icon: Radio },
        { id: 'assistant', label: 'SRE Assistant', icon: Bot, highlight: true },
        ...((currentUser?.is_platform_admin || currentUser?.role === 'PLATFORM_OWNER_ADMIN') ? [
          { id: 'platform_admin', label: 'Security & Admin', icon: Shield, highlight: true }
        ] : []),
      ]
    }
  ];

  const getHealthColor = (score: number) => {
    if (score >= 85) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (score >= 60) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B0F19] text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col justify-between border-r border-slate-800/80 bg-slate-950/70 backdrop-blur-xl z-20">
        <div>
          {/* Brand Header */}
          <div className="px-5 py-4 border-b border-slate-800/80 flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="font-bold text-lg tracking-tight text-white">AegisOps</h1>
                <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">AI</span>
              </div>
              <p className="text-[10px] text-slate-400 font-medium">Real-Time Autonomous AIOps</p>
            </div>
          </div>

          {/* Navigation Links organized into 5 Sections */}
          <nav className="p-3 space-y-3.5 overflow-y-auto max-h-[calc(100vh-210px)]">
            {navSections.map((sec) => (
              <div key={sec.title} className="space-y-1">
                <span className="px-3 text-[10px] font-mono font-bold tracking-wider text-slate-500 uppercase">
                  {sec.title}
                </span>
                <div className="space-y-0.5 mt-1">
                  {sec.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;
                    
                    return (
                      <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                          isActive 
                            ? 'bg-gradient-to-r from-indigo-600/90 to-cyan-600/90 text-white shadow-md shadow-indigo-500/20' 
                            : item.highlight
                            ? 'text-cyan-300 hover:bg-cyan-500/10 border border-cyan-500/20'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Icon className={`h-4 w-4 ${isActive ? 'text-white' : item.isSpecial ? 'text-indigo-400' : 'text-slate-400'}`} />
                          <span>{item.label}</span>
                        </div>
                        {item.badge !== undefined && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${item.badgeColor}`}>
                            {item.badge}
                          </span>
                        )}
                        {item.isSpecial && !item.badge && (
                          <Sparkles className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>


        {/* Sidebar Footer User Info & Secure Sign Out */}
        <div className="p-3.5 border-t border-slate-800/80 bg-slate-950/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 w-full">
              <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-xs text-cyan-400 flex-shrink-0">
                {currentUser?.username ? currentUser.username.substring(0, 2).toUpperCase() : 'AO'}
              </div>
              <div className="overflow-hidden flex-1">
                <p className="text-xs font-semibold text-slate-200 truncate">{currentUser?.username || 'Authenticated User'}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 truncate">
                    {currentUser?.role || 'MEMBER'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                id="btn-sidebar-logout"
                onClick={logout}
                title="Sign out of AegisOps AI"
                className="p-1.5 rounded-lg hover:bg-rose-950/40 text-slate-400 hover:text-rose-400 border border-transparent hover:border-rose-900/50 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-16 border-b border-slate-800/80 bg-slate-950/50 backdrop-blur-md px-6 flex items-center justify-between z-10 flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* If Platform Owner Admin: show Platform Company Switcher among the 3 authorized companies */}
            {currentUser && (currentUser.is_platform_admin || currentUser.role === 'PLATFORM_OWNER_ADMIN') ? (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-800">
                <Building2 className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-[10px] uppercase font-bold text-slate-400 font-mono">Company Switcher:</span>
                <select
                  id="platform-company-switcher"
                  value={activeTenant.id}
                  onChange={(e) => switchTenant(e.target.value)}
                  className="bg-transparent text-xs font-bold text-cyan-300 outline-none cursor-pointer font-sans"
                >
                  {availableTenants.map(t => (
                    <option key={t.id} value={t.id} className="bg-slate-950 text-white">
                      {t.name} ({t.id})
                    </option>
                  ))}
                </select>
                <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-semibold font-mono">
                  Platform Admin
                </span>
              </div>
            ) : (
              /* If Company User: Locked company badge, switcher strictly disabled */
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-800">
                <Lock className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-[10px] uppercase font-bold text-slate-400 font-mono">Company:</span>
                <span className="text-xs font-bold text-cyan-300 font-sans">
                  {activeTenant.name}
                </span>
                <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                  {activeTenant.id}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">

            {/* Live WS Status */}
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-xs">
              <Radio className={`h-3 w-3 ${isWsConnected ? 'text-emerald-400 animate-pulse' : 'text-slate-500'}`} />
              <span className={`text-[11px] font-mono font-medium ${isWsConnected ? 'text-emerald-400' : 'text-slate-400'}`}>
                {isWsConnected ? 'STREAM (1s)' : 'CONNECTING...'}
              </span>
            </div>

            {/* Health Score Pill */}
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-semibold ${getHealthColor(healthScore)}`}>
              <Activity className="h-3.5 w-3.5" />
              <span>Health: {healthScore}%</span>
            </div>

            {/* Reset All Button */}
            <button
              onClick={handleResetAll}
              disabled={isResetting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
              title="Restores microservices and clears incidents"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isResetting ? 'animate-spin text-cyan-400' : ''}`} />
              <span>{isResetting ? 'Resetting...' : 'Reset'}</span>
            </button>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#0B0F19]/90">
          {children}
        </main>
      </div>

      {/* 9-Step Customer Onboarding Wizard Modal */}
      <OnboardingWizardModal isOpen={isOnboardingOpen} onClose={closeOnboarding} />
    </div>
  );
};

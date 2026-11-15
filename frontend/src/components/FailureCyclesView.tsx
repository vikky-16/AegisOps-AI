import React, { useState, useEffect } from 'react';
import { 
  Radio, 
  RotateCw, 
  Zap, 
  AlertTriangle, 
  CheckCircle2, 
  ShieldCheck, 
  Clock, 
  Layers, 
  Server, 
  ArrowRight, 
  Flame, 
  Cpu, 
  Database, 
  Network, 
  Lock, 
  RefreshCw,
  Search,
  Filter
} from 'lucide-react';
import { api } from '../services/api';

interface FailureCyclesViewProps {
  onScenarioInjected?: (scenario: any) => void;
}

export const FailureCyclesView: React.FC<FailureCyclesViewProps> = ({ onScenarioInjected }) => {
  const [cycles, setCycles] = useState<any[]>([]);
  const [currentCycleIndex, setCurrentCycleIndex] = useState(0);
  const [currentCycle, setCurrentCycle] = useState<any>(null);
  const [secondsUntilNext, setSecondsUntilNext] = useState(180);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  useEffect(() => {
    fetchCycles();
    const interval = setInterval(() => {
      setSecondsUntilNext(prev => {
        if (prev <= 1) {
          fetchCycles();
          return 240;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchCycles = async () => {
    try {
      const data = await api.getFailureCycles();
      if (data?.cycles) {
        setCycles(data.cycles);
        setCurrentCycleIndex(data.current_cycle_index || 0);
        setCurrentCycle(data.current_cycle || data.cycles[data.current_cycle_index || 0]);
        if (data.seconds_until_next_rotation !== undefined) {
          setSecondsUntilNext(data.seconds_until_next_rotation);
        }
      }
    } catch (e) {
      console.warn("Failed to fetch failure cycles from backend:", e);
    }
  };

  const handleRotate = async () => {
    setIsLoading(true);
    try {
      const res = await api.rotateFailureCycle();
      setCurrentCycleIndex(res.new_index);
      setCurrentCycle(res.active_cycle);
      setSecondsUntilNext(240);
      setActionNotice({ type: 'success', msg: `Rotated to cycle ${res.active_cycle.id}: ${res.active_cycle.title}` });
      onScenarioInjected?.(res.active_cycle);
    } catch (e: any) {
      setActionNotice({ type: 'error', msg: e.message || 'Failed to rotate failure cycle' });
    } finally {
      setIsLoading(false);
      setTimeout(() => setActionNotice(null), 4000);
    }
  };

  const handleInject = async (scenarioId: string) => {
    setIsLoading(true);
    try {
      const res = await api.injectFailureCycle(scenarioId);
      setCurrentCycle(res.cycle);
      setActionNotice({ type: 'success', msg: `Injected scenario ${res.cycle.id}: ${res.cycle.title}` });
      onScenarioInjected?.(res.cycle);
    } catch (e: any) {
      setActionNotice({ type: 'error', msg: e.message || 'Failed to inject scenario' });
    } finally {
      setIsLoading(false);
      setTimeout(() => setActionNotice(null), 4000);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const categories = ['ALL', ...Array.from(new Set(cycles.map(c => c.category)))];

  const filteredCycles = cycles.filter(c => {
    const matchesCat = selectedCategory === 'ALL' || c.category === selectedCategory;
    const matchesSearch = !searchQuery || 
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.service.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner with CONTROLLED_CUSTOMER_TEST Badge */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-md border border-emerald-500/20 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              CONTROLLED_CUSTOMER_TEST
            </span>
            <span className="text-xs text-slate-500">•</span>
            <span className="text-xs text-slate-400 font-medium">30 Continuous Scenario Cycles</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Failure Simulation & Chaos Console</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated 30-scenario failure cycle executing every 3-6 minutes across 10 failure domains with non-destructive container sandbox isolation.
          </p>
        </div>

        {/* Live Auto-Rotation Countdown & Controls */}
        <div className="flex items-center gap-3">
          <div className="bg-slate-950 border border-slate-800 px-3 py-2 rounded-lg text-xs text-slate-300 flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            <span>Next Auto-Cycle:</span>
            <strong className="font-mono text-cyan-300">{formatTime(secondsUntilNext)}</strong>
          </div>

          <button
            onClick={handleRotate}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm transition disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Rotate Scenario
          </button>
        </div>
      </div>

      {actionNotice && (
        <div className={`p-3 rounded-lg text-xs flex items-center gap-2 border ${
          actionNotice.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
        }`}>
          {actionNotice.type === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-rose-400" />}
          <span>{actionNotice.msg}</span>
        </div>
      )}

      {/* Currently Active Scenario Card */}
      {currentCycle && (
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950/30 to-slate-900 border border-indigo-500/30 rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/30">
                ACTIVE CYCLE {currentCycle.id}
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs font-medium text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                {currentCycle.category}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              Target Service: <strong className="text-white font-mono">{currentCycle.service}</strong>
            </div>
          </div>

          <div>
            <h3 className="text-xl font-bold text-white">{currentCycle.title}</h3>
            <p className="text-xs text-slate-300 mt-1">{currentCycle.description}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs pt-2">
            <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-400 block mb-1 font-semibold uppercase text-[10px]">Blast Radius</span>
              <span className="text-amber-400 font-medium">{currentCycle.blast_radius}</span>
            </div>
            <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-400 block mb-1 font-semibold uppercase text-[10px]">Expected Root Cause</span>
              <span className="text-slate-200">{currentCycle.expected_rca}</span>
            </div>
            <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-400 block mb-1 font-semibold uppercase text-[10px]">Remediation Action</span>
              <span className="text-emerald-400 font-medium">{currentCycle.remediation}</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs text-slate-400 font-medium">Domain:</span>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-2.5 py-1 text-xs rounded-lg transition font-medium ${
                selectedCategory === cat
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200 bg-slate-800/60'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search 30 failure cycles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500 w-full md:w-64"
          />
        </div>
      </div>

      {/* 30 Failure Scenarios Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCycles.map((cycle) => {
          const isActive = currentCycle?.id === cycle.id;
          return (
            <div
              key={cycle.id}
              className={`bg-slate-900 border rounded-xl p-5 flex flex-col justify-between transition hover:border-slate-700 ${
                isActive ? 'border-indigo-500 bg-indigo-950/20 shadow-md shadow-indigo-500/10' : 'border-slate-800'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[11px] font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                    {cycle.id}
                  </span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                    cycle.severity === 'CRITICAL' 
                      ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' 
                      : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                  }`}>
                    {cycle.severity}
                  </span>
                </div>

                <h4 className="text-sm font-semibold text-white mb-1 line-clamp-1">
                  {cycle.title}
                </h4>
                <p className="text-xs text-slate-400 line-clamp-2 mb-3">
                  {cycle.description}
                </p>

                <div className="space-y-1 text-[11px] text-slate-300 font-mono border-t border-slate-800/80 pt-2 mb-4">
                  <div className="flex justify-between">
                    <span className="text-slate-500 font-sans">Service:</span>
                    <span className="text-indigo-300">{cycle.service}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 font-sans">Category:</span>
                    <span className="text-purple-300 font-sans">{cycle.category}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800">
                {isActive ? (
                  <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                    Currently Active
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">Standby</span>
                )}

                <button
                  onClick={() => handleInject(cycle.id)}
                  disabled={isLoading}
                  className="px-3 py-1 text-xs font-semibold text-white bg-slate-800 hover:bg-indigo-600 border border-slate-700 hover:border-indigo-500 rounded-lg transition"
                >
                  Inject Failure
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

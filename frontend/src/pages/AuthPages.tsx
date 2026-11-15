import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Lock, 
  Mail, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle, 
  Key, 
  RefreshCw,
  Server,
  Activity,
  Check
} from 'lucide-react';
import { api } from '../services/api';
import { useTenant } from '../context/TenantContext';

export interface AuthPageProps {
  initialMode?: 'login' | 'forgot-password' | 'reset-password' | 'first-login-change';
  sessionExpired?: boolean;
  onLoginSuccess: (userData: any) => void;
}

export const AuthPages: React.FC<AuthPageProps> = ({ 
  initialMode = 'login', 
  sessionExpired = false,
  onLoginSuccess 
}) => {
  const [mode, setMode] = useState<'login' | 'forgot-password' | 'reset-password' | 'first-login-change'>(initialMode);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSessionExpired, setIsSessionExpired] = useState(sessionExpired);

  // First-login password change fields
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [pendingUser, setPendingUser] = useState<any>(null);

  // Forgot / Reset password fields
  const [resetEmail, setResetEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [resetNewPassword, setResetNewPassword] = useState('');

  const { updateUser } = useTenant();

  useEffect(() => {
    // Check url for expired flag
    if (window.location.search.includes('expired=true')) {
      setIsSessionExpired(true);
    }
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please provide your work email or username and password.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await api.login({
        username: username.trim(),
        password: password
      });

      // Store tokens
      localStorage.setItem('aegisops_token', res.access_token);
      localStorage.setItem('aegisops_user', JSON.stringify(res.user));
      if (res.tenant_id) {
        localStorage.setItem('aegisops_tenant_id', res.tenant_id);
      }

      // Check if first-login password change is required
      if (res.must_change_password || res.user?.must_change_password) {
        setPendingUser(res.user);
        setMode('first-login-change');
        setSuccessMessage('First-time login detected. Please set a secure permanent password.');
        return;
      }

      // Successful regular login
      updateUser(res.user);
      onLoginSuccess(res.user);
    } catch (err: any) {
      setError(err.message || 'Invalid credentials. Please verify your username and password.');
    } finally {
      setLoading(false);
    }
  };

  const handleFirstLoginPasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.firstLoginChangePassword({
        new_password: newPassword,
        current_password: password
      });

      localStorage.setItem('aegisops_token', res.access_token);
      if (res.user) {
        localStorage.setItem('aegisops_user', JSON.stringify(res.user));
        updateUser(res.user);
      }
      setSuccessMessage('Password changed successfully! Redirecting to your secure dashboard...');
      setTimeout(() => {
        onLoginSuccess(res.user || pendingUser);
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Failed to update password.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetEmail.trim()) {
      setError('Please provide your work email address.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.forgotPassword(resetEmail.trim());
      setSuccessMessage(res.message || 'Password reset token generated.');
      if (res.reset_token) {
        setResetToken(res.reset_token);
        setTimeout(() => setMode('reset-password'), 1500);
      }
    } catch (err: any) {
      setError(err.message || 'Password recovery request failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetToken.trim() || resetNewPassword.length < 8) {
      setError('Valid reset token and password of at least 8 characters required.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await api.resetPassword({
        token: resetToken.trim(),
        new_password: resetNewPassword
      });
      setSuccessMessage('Password updated successfully. You may now sign in.');
      setTimeout(() => {
        setSuccessMessage(null);
        setMode('login');
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#080C14] text-slate-100 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden font-sans selection:bg-cyan-500/20 selection:text-cyan-300">
      {/* Topology / Telemetry Background Traces */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="telemetry-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" strokeWidth="0.75" />
              <circle cx="0" cy="0" r="1.5" fill="#0EA5E9" opacity="0.4" />
            </pattern>
            <linearGradient id="trace-glow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#2563EB" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.0" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#telemetry-grid)" />
          {/* Subtle Topology Lines */}
          <path d="M 100 200 Q 300 150, 500 300 T 900 250 T 1400 400" fill="none" stroke="url(#trace-glow)" strokeWidth="1.5" strokeDasharray="6 4" />
          <path d="M 50 600 Q 400 550, 700 700 T 1200 650" fill="none" stroke="url(#trace-glow)" strokeWidth="1" strokeDasharray="4 4" />
        </svg>
      </div>

      {/* Atmospheric Radial Gradients */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[850px] h-[550px] bg-gradient-to-b from-cyan-600/10 via-blue-700/10 to-indigo-900/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-5 right-10 w-96 h-96 bg-cyan-900/10 rounded-full blur-3xl pointer-events-none" />

      {/* Brand Header */}
      <div className="flex flex-col items-center mb-6 relative z-10">
        <div className="relative group mb-3">
          <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 rounded-2xl blur-md opacity-70 group-hover:opacity-100 transition duration-500" />
          <div className="relative w-16 h-16 bg-[#0B132B] border border-cyan-500/40 rounded-2xl flex items-center justify-center shadow-2xl">
            <Shield className="w-8 h-8 text-cyan-400" />
            <span className="absolute bottom-1 right-1 w-2.5 h-2.5 bg-cyan-400 rounded-full animate-ping opacity-75" />
          </div>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          AEGISOPS <span className="text-[11px] uppercase tracking-widest px-2.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-400 font-semibold border border-cyan-500/30">AI</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1 font-medium tracking-wide">
          Enterprise Security Operations & Autonomous Incident Platform
        </p>
      </div>

      {/* Main Authentication Card */}
      <div className="w-full max-w-md bg-[#0D1527]/90 border border-slate-800/90 rounded-2xl shadow-2xl p-7 relative z-10 backdrop-blur-xl ring-1 ring-white/5">
        
        {/* Session Expired Banner */}
        {isSessionExpired && (
          <div className="mb-5 p-3 rounded-lg bg-amber-950/60 border border-amber-800/80 text-amber-300 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-400" />
            <div>
              <span className="font-semibold">Session Expired:</span> Your secure authenticated session has timed out. Please sign in to verify your identity.
            </div>
          </div>
        )}

        {/* Dynamic Error & Success Banners */}
        {error && (
          <div id="auth-error-banner" className="mb-5 p-3 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-start gap-2.5 animate-fadeIn">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-400" />
            <span>{error}</span>
          </div>
        )}
        {successMessage && (
          <div id="auth-success-banner" className="mb-5 p-3 rounded-lg bg-emerald-950/60 border border-emerald-800/80 text-emerald-300 text-xs flex items-start gap-2.5 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5 text-emerald-400" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* 1. LOGIN FORM */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="auth-username" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Work Email or Username
              </label>
              <div className="relative">
                <input
                  id="auth-username"
                  name="username"
                  type="text"
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. fincore.admin or owner@aegisops.ai"
                  className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-colors"
                />
                <Mail className="w-4 h-4 text-slate-500 absolute right-3.5 top-3 pointer-events-none" />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="auth-password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Password
                </label>
                <button
                  type="button"
                  id="auth-forgot-link"
                  onClick={() => {
                    setError(null);
                    setSuccessMessage(null);
                    setMode('forgot-password');
                  }}
                  className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors focus:outline-none focus:underline"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  id="auth-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-colors"
                />
                <button
                  type="button"
                  id="auth-toggle-pwd"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3 text-slate-500 hover:text-slate-300 focus:outline-none"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              id="auth-signin-btn"
              disabled={loading}
              className="w-full bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all mt-3 focus:outline-none focus:ring-2 focus:ring-cyan-400/50"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  <span>Verifying Identity...</span>
                </div>
              ) : (
                <>
                  <span>Sign In to Platform</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}

        {/* 2. FIRST-LOGIN PASSWORD CHANGE */}
        {mode === 'first-login-change' && (
          <form onSubmit={handleFirstLoginPasswordChange} className="space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Key className="w-4 h-4 text-cyan-400" />
                Set Permanent Password
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                For security compliance, temporary credentials must be changed before accessing operational dashboards.
              </p>
            </div>

            <div>
              <label htmlFor="auth-new-password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                New Password (minimum 8 characters)
              </label>
              <div className="relative">
                <input
                  id="auth-new-password"
                  type={showNewPassword ? 'text' : 'password'}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new strong password"
                  className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3.5 top-3 text-slate-500 hover:text-slate-300 focus:outline-none"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="auth-confirm-password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Confirm New Password
              </label>
              <input
                id="auth-confirm-password"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-colors"
              />
            </div>

            <button
              type="submit"
              id="auth-first-login-submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all mt-2"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  <span>Updating Security Credentials...</span>
                </div>
              ) : (
                <>
                  <span>Activate Account & Enter Platform</span>
                  <Check className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}

        {/* 3. FORGOT PASSWORD FLOW */}
        {mode === 'forgot-password' && (
          <form onSubmit={handleForgotPassword} className="space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-white">Reset Account Password</h2>
              <p className="text-xs text-slate-400 mt-1">
                Enter your authorized work email. A cryptographically expiring reset token will be issued.
              </p>
            </div>

            <div>
              <label htmlFor="auth-reset-email" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Work Email Address
              </label>
              <input
                id="auth-reset-email"
                type="email"
                required
                value={resetEmail}
                onChange={(e) => setResetEmail(e.target.value)}
                placeholder="e.g. admin@fincore.internal"
                className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500"
              />
            </div>

            <button
              type="submit"
              id="auth-forgot-submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-all"
            >
              {loading ? 'Generating Reset Token...' : 'Send Recovery Instructions'}
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setSuccessMessage(null);
                  setMode('login');
                }}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                ← Return to Sign In
              </button>
            </div>
          </form>
        )}

        {/* 4. RESET PASSWORD FORM */}
        {mode === 'reset-password' && (
          <form onSubmit={handleResetPassword} className="space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-sm font-semibold text-white">Complete Password Recovery</h2>
              <p className="text-xs text-slate-400 mt-1">
                Enter the recovery token and specify your new permanent password.
              </p>
            </div>

            <div>
              <label htmlFor="auth-reset-token" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Recovery Token
              </label>
              <input
                id="auth-reset-token"
                type="text"
                required
                value={resetToken}
                onChange={(e) => setResetToken(e.target.value)}
                placeholder="Paste recovery token"
                className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>

            <div>
              <label htmlFor="auth-reset-new-password" className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                New Password
              </label>
              <input
                id="auth-reset-new-password"
                type="password"
                required
                value={resetNewPassword}
                onChange={(e) => setResetNewPassword(e.target.value)}
                placeholder="••••••••••••••••"
                className="w-full bg-[#070B16] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>

            <button
              type="submit"
              id="auth-reset-submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-all"
            >
              {loading ? 'Updating Password...' : 'Save New Password & Sign In'}
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setSuccessMessage(null);
                  setMode('login');
                }}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                ← Return to Sign In
              </button>
            </div>
          </form>
        )}

        {/* Security Compliance Footer */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-cyan-500/70" />
            <span>End-to-End Company Isolated</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-blue-500/70" />
            <span>Zero-Trust RBAC</span>
          </div>
        </div>
      </div>
    </div>
  );
};

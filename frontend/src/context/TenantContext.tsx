import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

export type EnvironmentModeBadge = 
  | 'LIVE_CUSTOMER'
  | 'CONTROLLED_CUSTOMER_TEST'
  | 'LOAD_TEST'
  | 'LIVE_EXTERNAL_TENANT'
  | 'LIVE_DEMO_ENVIRONMENT'
  | 'SIMULATED_DEMO';

export interface TenantInfo {
  id: string;
  name: string;
  slug: string;
  plan: string;
  environment_mode: EnvironmentModeBadge;
  is_active: boolean;
  apiKeyPreview?: string;
}

export type EnterpriseRole = 
  | 'PLATFORM_OWNER_ADMIN'
  | 'COMPANY_ADMIN'
  | 'APPROVER'
  | 'DEVELOPER_SECURITY'
  | 'SUPER_ADMIN' 
  | 'ORG_ADMIN' 
  | 'CEO' 
  | 'CTO' 
  | 'SRE_LEAD' 
  | 'DEVOPS_ENGINEER' 
  | 'SECURITY_ENGINEER' 
  | 'DEVELOPER' 
  | 'INCIDENT_COMMANDER' 
  | 'VIEWER' 
  | 'PLATFORM_ADMIN' 
  | 'TENANT_ADMIN' 
  | 'SRE_MANAGER' 
  | 'SRE_ENGINEER' 
  | 'OPERATOR';

export interface UserSession {
  user_id?: number;
  id?: number;
  username: string;
  email?: string;
  full_name?: string;
  role: EnterpriseRole;
  tenant_id?: string;
  is_platform_admin: boolean;
  must_change_password?: boolean;
  permissions?: string[];
}

interface TenantContextType {
  activeTenant: TenantInfo;
  currentTenant: TenantInfo;
  availableTenants: TenantInfo[];
  currentUser: UserSession | null;
  isAuthenticated: boolean;
  switchTenant: (tenantId: string) => Promise<boolean>;
  updateUser: (user: UserSession) => void;
  logout: () => Promise<void>;
  refreshTenants: () => Promise<void>;
  isOnboardingOpen: boolean;
  openOnboarding: () => void;
  openOnboardingModal: () => void;
  closeOnboarding: () => void;
}

// Strictly the three existing companies: FinCore, ShopSphere, and CloudDesk
export const AUTHORIZED_COMPANIES: TenantInfo[] = [
  {
    id: 'fincore',
    name: 'FinCore Financial Platform',
    slug: 'fincore',
    plan: 'ENTERPRISE_FINTECH',
    environment_mode: 'LIVE_CUSTOMER',
    is_active: true,
    apiKeyPreview: 'agt_live_fin_...2222'
  },
  {
    id: 'shopsphere',
    name: 'ShopSphere E-Commerce',
    slug: 'shopsphere',
    plan: 'ENTERPRISE_CORE',
    environment_mode: 'LIVE_CUSTOMER',
    is_active: true,
    apiKeyPreview: 'agt_live_shop_...1111'
  },
  {
    id: 'clouddesk',
    name: 'CloudDesk SaaS Platform',
    slug: 'clouddesk',
    plan: 'ENTERPRISE_CLOUD',
    environment_mode: 'LIVE_CUSTOMER',
    is_active: true,
    apiKeyPreview: 'agt_live_desk_...3333'
  }
];

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const TenantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [availableTenants, setAvailableTenants] = useState<TenantInfo[]>(AUTHORIZED_COMPANIES);
  const [activeTenant, setActiveTenant] = useState<TenantInfo>(() => {
    const savedId = localStorage.getItem('aegisops_tenant_id');
    const matched = AUTHORIZED_COMPANIES.find(t => t.id === savedId);
    return matched || AUTHORIZED_COMPANIES[0];
  });
  
  const [currentUser, setCurrentUser] = useState<UserSession | null>(() => {
    const savedUser = localStorage.getItem('aegisops_user');
    const token = localStorage.getItem('aegisops_token');
    if (token && savedUser) {
      try { return JSON.parse(savedUser); } catch (e) {}
    }
    return null;
  });

  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);

  // Sync / validate user profile on startup
  useEffect(() => {
    const token = localStorage.getItem('aegisops_token');
    if (token) {
      api.getCurrentUserProfile().then(profile => {
        if (profile && profile.username) {
          const userSession: UserSession = {
            id: profile.id,
            user_id: profile.id,
            username: profile.username,
            email: profile.email,
            full_name: profile.full_name || profile.username,
            role: profile.role,
            tenant_id: profile.tenant_id,
            is_platform_admin: Boolean(profile.is_platform_admin || profile.role === 'PLATFORM_OWNER_ADMIN'),
            must_change_password: Boolean(profile.must_change_password),
            permissions: profile.permissions || []
          };
          setCurrentUser(userSession);
          localStorage.setItem('aegisops_user', JSON.stringify(userSession));

          if (profile.tenant_id) {
            const matched = AUTHORIZED_COMPANIES.find(t => t.id === profile.tenant_id);
            if (matched) {
              setActiveTenant(matched);
              localStorage.setItem('aegisops_tenant_id', matched.id);
            }
          }
        }
      }).catch(() => {
        // Token invalid or expired - clear local state
        localStorage.removeItem('aegisops_token');
        localStorage.removeItem('aegisops_user');
        localStorage.removeItem('aegisops_tenant_id');
        setCurrentUser(null);
      });
    }
  }, []);

  const refreshTenants = async () => {
    try {
      const serverTenants = await api.getTenants();
      if (Array.isArray(serverTenants) && serverTenants.length > 0) {
        // Filter strictly to FinCore, ShopSphere, and CloudDesk
        const filtered = serverTenants.filter(t => ['fincore', 'shopsphere', 'clouddesk'].includes(t.id));
        if (filtered.length > 0) {
          const mapped: TenantInfo[] = filtered.map(t => ({
            id: t.id,
            name: t.name,
            slug: t.slug || t.id,
            plan: t.plan || 'ENTERPRISE',
            environment_mode: 'LIVE_CUSTOMER',
            is_active: t.is_active !== false
          }));
          setAvailableTenants(mapped);
        }
      }
    } catch (e) {
      // Keep defaults
    }
  };

  const switchTenant = async (tenantId: string): Promise<boolean> => {
    // Only platform owner admin can switch company context
    if (!currentUser || (!currentUser.is_platform_admin && currentUser.role !== 'PLATFORM_OWNER_ADMIN')) {
      console.warn("Tenant switching blocked: only Platform Owner Admin can switch companies.");
      return false;
    }

    const target = AUTHORIZED_COMPANIES.find(t => t.id === tenantId);
    if (!target) return false;

    try {
      const res = await api.switchTenantAuth(tenantId);
      if (res && res.access_token) {
        localStorage.setItem('aegisops_token', res.access_token);
      }
      api.clearCache();
      setActiveTenant(target);
      localStorage.setItem('aegisops_tenant_id', target.id);
      return true;
    } catch (err) {
      console.error("Failed to switch tenant on server:", err);
      return false;
    }
  };

  const updateUser = (user: UserSession) => {
    setCurrentUser(user);
    localStorage.setItem('aegisops_user', JSON.stringify(user));
    if (user.tenant_id) {
      const matched = AUTHORIZED_COMPANIES.find(t => t.id === user.tenant_id);
      if (matched) {
        setActiveTenant(matched);
        localStorage.setItem('aegisops_tenant_id', matched.id);
      }
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch (e) {}
    api.clearCache();
    setCurrentUser(null);
    localStorage.removeItem('aegisops_token');
    localStorage.removeItem('aegisops_user');
    localStorage.removeItem('aegisops_tenant_id');
  };

  return (
    <TenantContext.Provider value={{
      activeTenant,
      currentTenant: activeTenant,
      availableTenants,
      currentUser,
      isAuthenticated: Boolean(currentUser && localStorage.getItem('aegisops_token')),
      switchTenant,
      updateUser,
      logout,
      refreshTenants,
      isOnboardingOpen,
      openOnboarding: () => setIsOnboardingOpen(true),
      openOnboardingModal: () => setIsOnboardingOpen(true),
      closeOnboarding: () => setIsOnboardingOpen(false)
    }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = () => {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return ctx;
};

'use client';

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { Building2, ChevronDown, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import { Organization } from '@/types';
import { usePermissions } from '@/components/PermissionGuard';

interface OrgContextType {
  organizations: Organization[];
  selectedOrg: Organization | null;
  setSelectedOrg: (org: Organization | null) => void;
  loading: boolean;
  isOrgScoped: boolean;
  refresh: () => Promise<void>;
}

const OrgContext = createContext<OrgContextType>({
  organizations: [],
  selectedOrg: null,
  setSelectedOrg: () => {},
  loading: true,
  isOrgScoped: false,
  refresh: async () => {},
});

export function useOrgContext() {
  return useContext(OrgContext);
}

interface OrgContextProviderProps {
  children: ReactNode;
}

export function OrgContextProvider({ children }: OrgContextProviderProps) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const { isSuperAdmin, user, loading: permLoading } = usePermissions();

  // Org-scoped means the user is NOT a super admin but might be an org admin
  const isOrgScoped = !permLoading && !isSuperAdmin() && user !== null;

  const loadOrganizations = useCallback(async () => {
    try {
      setLoading(true);
      const orgs = await api.getOrganizations();
      const orgList = Array.isArray(orgs) ? orgs : [];
      setOrganizations(orgList);

      // If org-scoped and there are orgs, select the first one by default
      if (isOrgScoped && orgList.length > 0) {
        setSelectedOrg((current) => current ?? orgList[0]);
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setOrganizations([]);
    } finally {
      setLoading(false);
    }
  }, [isOrgScoped]);

  useEffect(() => {
    if (!permLoading) {
      loadOrganizations();
    }
  }, [loadOrganizations, permLoading]);

  return (
    <OrgContext.Provider
      value={{
        organizations,
        selectedOrg,
        setSelectedOrg,
        loading,
        isOrgScoped,
        refresh: loadOrganizations,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}

// Visual component for switching org context
interface OrgContextSwitcherProps {
  className?: string;
}

export function OrgContextSwitcher({ className = '' }: OrgContextSwitcherProps) {
  const { organizations, selectedOrg, setSelectedOrg, loading } = useOrgContext();
  const { isSuperAdmin } = usePermissions();
  const [isOpen, setIsOpen] = useState(false);

  // Super admins see all orgs but can choose to scope; org admins must select from their orgs
  if (loading) {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 ${className}`}>
        <Building2 className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading...</span>
      </div>
    );
  }

  if (organizations.length === 0) {
    return null;
  }

  return (
    <div className={`relative ${className}`}>
      <Button
        variant="ghost"
        size="sm"
        className="w-full justify-between"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4" />
          <span className="truncate max-w-[120px]">
            {selectedOrg ? selectedOrg.name : 'All Organizations'}
          </span>
        </div>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute top-full left-0 mt-1 w-full min-w-[180px] bg-popover border rounded-md shadow-lg z-50 py-1">
            {/* All orgs option (only for super admins) */}
            {isSuperAdmin() && (
              <button
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted text-left"
                onClick={() => {
                  setSelectedOrg(null);
                  setIsOpen(false);
                }}
              >
                <Building2 className="h-4 w-4" />
                <span className="flex-1">All Organizations</span>
                {!selectedOrg && <Check className="h-4 w-4 text-primary" />}
              </button>
            )}

            {/* Divider */}
            {isSuperAdmin() && organizations.length > 0 && (
              <div className="border-t my-1" />
            )}

            {/* Organization list */}
            {organizations.map((org) => (
              <button
                key={org.id}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted text-left"
                onClick={() => {
                  setSelectedOrg(org);
                  setIsOpen(false);
                }}
              >
                <Building2 className="h-4 w-4" />
                <span className="flex-1 truncate">{org.name}</span>
                {selectedOrg?.id === org.id && <Check className="h-4 w-4 text-primary" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// Helper hook to get filtered data based on org context
export function useOrgFilteredData<T extends { org_id?: number }>(data: T[]): T[] {
  const { selectedOrg } = useOrgContext();

  if (!selectedOrg) {
    return data;
  }

  return data.filter((item) => item.org_id === selectedOrg.id);
}

export default OrgContextSwitcher;

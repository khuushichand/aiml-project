'use client';

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { Building2, ChevronDown, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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

const ORG_SELECTION_STORAGE_KEY = 'selectedOrgId';

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

  const handleSetSelectedOrg = useCallback((org: Organization | null) => {
    setSelectedOrg(org);
    if (typeof window === 'undefined') {
      return;
    }
    try {
      if (org) {
        localStorage.setItem(ORG_SELECTION_STORAGE_KEY, String(org.id));
      } else {
        localStorage.removeItem(ORG_SELECTION_STORAGE_KEY);
      }
    } catch (error) {
      console.warn('Failed to persist org selection:', error);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      setLoading(true);
      const orgs = await api.getOrganizations();
      const orgList = Array.isArray(orgs) ? orgs : [];
      setOrganizations(orgList);
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setOrganizations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (organizations.length === 0 || selectedOrg) {
      return;
    }
    let storedId: number | null = null;
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem(ORG_SELECTION_STORAGE_KEY);
        if (stored) {
          const parsed = Number.parseInt(stored, 10);
          if (!Number.isNaN(parsed)) {
            storedId = parsed;
          }
        }
      } catch (error) {
        console.warn('Failed to load persisted org selection:', error);
      }
    }

    if (storedId !== null) {
      const storedOrg = organizations.find((org) => org.id === storedId);
      if (storedOrg) {
        handleSetSelectedOrg(storedOrg);
        return;
      }
      if (typeof window !== 'undefined') {
        try {
          localStorage.removeItem(ORG_SELECTION_STORAGE_KEY);
        } catch (error) {
          console.warn('Failed to clear invalid org selection:', error);
        }
      }
    }

    if (isOrgScoped) {
      handleSetSelectedOrg(organizations[0]);
    }
  }, [handleSetSelectedOrg, isOrgScoped, organizations, selectedOrg]);

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
        setSelectedOrg: handleSetSelectedOrg,
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

  // Super admins see all orgs but can choose to scope; org admins must select from their orgs
  if (!isSuperAdmin()) {
    return null;
  }
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
    <div className={className}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="group w-full justify-between">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              <span className="truncate max-w-[120px]">
                {selectedOrg ? selectedOrg.name : 'All Organizations'}
              </span>
            </div>
            <ChevronDown className="h-4 w-4 transition-transform group-data-[state=open]:rotate-180" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[200px]">
          {isSuperAdmin() && (
            <DropdownMenuItem
              className="flex items-center gap-2"
              onSelect={() => setSelectedOrg(null)}
            >
              <Building2 className="h-4 w-4" />
              <span className="flex-1">All Organizations</span>
              {!selectedOrg && <Check className="h-4 w-4 text-primary" />}
            </DropdownMenuItem>
          )}

          {isSuperAdmin() && organizations.length > 0 && <DropdownMenuSeparator />}

          {organizations.map((org) => (
            <DropdownMenuItem
              key={org.id}
              className="flex items-center gap-2"
              onSelect={() => setSelectedOrg(org)}
            >
              <Building2 className="h-4 w-4" />
              <span className="flex-1 truncate">{org.name}</span>
              {selectedOrg?.id === org.id && <Check className="h-4 w-4 text-primary" />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
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

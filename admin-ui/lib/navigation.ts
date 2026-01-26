import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  BarChart3,
  Bug,
  Building2,
  Cpu,
  Database,
  FileText,
  Flag,
  Gauge,
  AlertTriangle,
  ScrollText,
  Key,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  Settings,
  Shield,
  ShieldAlert,
  UserCog,
  Users,
  Wallet,
} from 'lucide-react';

export type NavigationItem = {
  name: string;
  href: string;
  icon: LucideIcon;
  permission?: string;
  role?: string[];
};

export type NavigationSection = {
  title: string;
  items: NavigationItem[];
};

const navigationItems = {
  dashboard: { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  users: { name: 'Users', href: '/users', icon: Users, permission: 'read:users' },
  organizations: { name: 'Organizations', href: '/organizations', icon: Building2, permission: 'read:orgs' },
  teams: { name: 'Teams', href: '/teams', icon: UserCog, permission: 'read:teams' },
  rolesPermissions: { name: 'Roles & Permissions', href: '/roles', icon: Shield, role: ['admin', 'super_admin', 'owner'] },
  apiKeys: { name: 'API Keys', href: '/api-keys', icon: Key, permission: 'read:api_keys' },
  byok: { name: 'BYOK', href: '/byok', icon: KeyRound, role: ['admin', 'super_admin', 'owner'] },
  providers: { name: 'LLM Providers', href: '/providers', icon: Cpu, permission: 'read:config' },
  resourceGovernor: { name: 'Resource Governor', href: '/resource-governor', icon: Gauge, role: ['admin', 'super_admin', 'owner'] },
  security: { name: 'Security', href: '/security', icon: ShieldAlert, role: ['admin', 'super_admin', 'owner'] },
  auditLogs: { name: 'Audit Logs', href: '/audit', icon: FileText, permission: 'read:audit' },
  monitoring: { name: 'Monitoring', href: '/monitoring', icon: Activity, role: ['admin', 'super_admin', 'owner'] },
  jobs: { name: 'Jobs', href: '/jobs', icon: ListChecks, role: ['admin', 'super_admin', 'owner'] },
  usage: { name: 'Usage', href: '/usage', icon: BarChart3, role: ['admin', 'super_admin', 'owner'] },
  budgets: { name: 'Budgets', href: '/budgets', icon: Wallet, role: ['admin', 'super_admin', 'owner'] },
  dataOps: { name: 'Data Ops', href: '/data-ops', icon: Database, role: ['admin', 'super_admin', 'owner'] },
  logs: { name: 'Logs', href: '/logs', icon: ScrollText, role: ['admin', 'super_admin', 'owner'] },
  flags: { name: 'Flags', href: '/flags', icon: Flag, role: ['admin', 'super_admin', 'owner'] },
  incidents: { name: 'Incidents', href: '/incidents', icon: AlertTriangle, role: ['admin', 'super_admin', 'owner'] },
  debug: { name: 'Debug', href: '/debug', icon: Bug, role: ['super_admin', 'owner'] },
  configuration: { name: 'Configuration', href: '/config', icon: Settings, role: ['super_admin', 'owner'] },
} satisfies Record<string, NavigationItem>;

// Grouped navigation for sidebar sections
export const navigationSections: NavigationSection[] = [
  {
    title: 'Overview',
    items: [
      navigationItems.dashboard,
    ],
  },
  {
    title: 'Users & Access',
    items: [
      navigationItems.users,
      navigationItems.organizations,
      navigationItems.teams,
      navigationItems.rolesPermissions,
    ],
  },
  {
    title: 'API & Keys',
    items: [
      navigationItems.apiKeys,
      navigationItems.byok,
      navigationItems.providers,
    ],
  },
  {
    title: 'System',
    items: [
      navigationItems.monitoring,
      navigationItems.jobs,
      navigationItems.auditLogs,
      navigationItems.logs,
      navigationItems.incidents,
    ],
  },
  {
    title: 'Configuration',
    items: [
      navigationItems.resourceGovernor,
      navigationItems.security,
      navigationItems.dataOps,
      navigationItems.usage,
      navigationItems.budgets,
      navigationItems.flags,
      navigationItems.configuration,
      navigationItems.debug,
    ],
  },
];

// Flat navigation list for backwards compatibility
export const navigation: NavigationItem[] = navigationSections.flatMap((section) => section.items);

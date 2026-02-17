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
  Mic,
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
  keywords?: string[];
};

export type NavigationSection = {
  title: string;
  items: NavigationItem[];
};

const navigationItems = {
  dashboard: { name: 'Dashboard', href: '/', icon: LayoutDashboard, keywords: ['overview', 'home', 'stats'] },
  users: { name: 'Users', href: '/users', icon: Users, permission: 'read:users', keywords: ['accounts', 'people'] },
  organizations: { name: 'Organizations', href: '/organizations', icon: Building2, permission: 'read:orgs', keywords: ['orgs', 'tenants'] },
  teams: { name: 'Teams', href: '/teams', icon: UserCog, permission: 'read:teams', keywords: ['groups'] },
  rolesPermissions: { name: 'Roles & Permissions', href: '/roles', icon: Shield, role: ['admin', 'super_admin', 'owner'], keywords: ['rbac', 'authz'] },
  apiKeys: { name: 'API Keys', href: '/api-keys', icon: Key, permission: 'read:api_keys', keywords: ['credentials', 'tokens'] },
  byok: { name: 'BYOK', href: '/byok', icon: KeyRound, role: ['admin', 'super_admin', 'owner'], keywords: ['provider keys', 'bring your own key'] },
  providers: { name: 'LLM Providers', href: '/providers', icon: Cpu, permission: 'read:config', keywords: ['models', 'inference'] },
  resourceGovernor: { name: 'Resource Governor', href: '/resource-governor', icon: Gauge, role: ['admin', 'super_admin', 'owner'], keywords: ['limits', 'quotas', 'rate limits'] },
  security: { name: 'Security', href: '/security', icon: ShieldAlert, role: ['admin', 'super_admin', 'owner'], keywords: ['risk', 'mfa', 'sessions'] },
  auditLogs: { name: 'Audit Logs', href: '/audit', icon: FileText, permission: 'read:audit', keywords: ['audit', 'events', 'history'] },
  monitoring: { name: 'Monitoring', href: '/monitoring', icon: Activity, role: ['admin', 'super_admin', 'owner'], keywords: ['health', 'alerts', 'metrics'] },
  jobs: { name: 'Jobs', href: '/jobs', icon: ListChecks, role: ['admin', 'super_admin', 'owner'], keywords: ['queue', 'workers', 'tasks'] },
  usage: { name: 'Usage', href: '/usage', icon: BarChart3, role: ['admin', 'super_admin', 'owner'], keywords: ['analytics', 'consumption'] },
  budgets: { name: 'Budgets', href: '/budgets', icon: Wallet, role: ['admin', 'super_admin', 'owner'], keywords: ['cost', 'spend'] },
  dataOps: { name: 'Data Ops', href: '/data-ops', icon: Database, role: ['admin', 'super_admin', 'owner'], keywords: ['backup', 'retention', 'export'] },
  logs: { name: 'Logs', href: '/logs', icon: ScrollText, role: ['admin', 'super_admin', 'owner'], keywords: ['system logs'] },
  flags: { name: 'Flags', href: '/flags', icon: Flag, role: ['admin', 'super_admin', 'owner'], keywords: ['feature flags', 'maintenance'] },
  incidents: { name: 'Incidents', href: '/incidents', icon: AlertTriangle, role: ['admin', 'super_admin', 'owner'], keywords: ['outages', 'response'] },
  voiceCommands: { name: 'Voice Commands', href: '/voice-commands', icon: Mic, role: ['admin', 'super_admin', 'owner'], keywords: ['speech', 'commands'] },
  debug: { name: 'Debug', href: '/debug', icon: Bug, role: ['super_admin', 'owner'], keywords: ['diagnostics'] },
  configuration: { name: 'Configuration', href: '/config', icon: Settings, role: ['super_admin', 'owner'], keywords: ['settings', 'system config'] },
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
    title: 'Identity & Access',
    items: [
      navigationItems.users,
      navigationItems.organizations,
      navigationItems.teams,
      navigationItems.rolesPermissions,
      navigationItems.apiKeys,
    ],
  },
  {
    title: 'AI & Models',
    items: [
      navigationItems.providers,
      navigationItems.byok,
      navigationItems.voiceCommands,
    ],
  },
  {
    title: 'Operations',
    items: [
      navigationItems.monitoring,
      navigationItems.incidents,
      navigationItems.jobs,
      navigationItems.auditLogs,
      navigationItems.logs,
    ],
  },
  {
    title: 'Governance',
    items: [
      navigationItems.security,
      navigationItems.resourceGovernor,
      navigationItems.budgets,
      navigationItems.usage,
      navigationItems.flags,
      navigationItems.dataOps,
    ],
  },
  {
    title: 'Advanced',
    items: [
      navigationItems.configuration,
      navigationItems.debug,
    ],
  },
];

export const matchesNavigationQuery = (
  item: NavigationItem,
  sectionTitle: string,
  query: string
): boolean => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  const searchableParts = [
    item.name,
    sectionTitle,
    ...(item.keywords ?? []),
  ];
  return searchableParts.some((part) => part.toLowerCase().includes(normalizedQuery));
};

// Flat navigation list for backwards compatibility
export const navigation: NavigationItem[] = navigationSections.flatMap((section) => section.items);

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

// Flat navigation list for backwards compatibility
export const navigation: NavigationItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Users', href: '/users', icon: Users, permission: 'read:users' },
  { name: 'Organizations', href: '/organizations', icon: Building2, permission: 'read:orgs' },
  { name: 'Teams', href: '/teams', icon: UserCog, permission: 'read:teams' },
  { name: 'Roles & Permissions', href: '/roles', icon: Shield, role: ['admin', 'super_admin', 'owner'] },
  { name: 'API Keys', href: '/api-keys', icon: Key, permission: 'read:api_keys' },
  { name: 'BYOK', href: '/byok', icon: KeyRound, role: ['admin', 'super_admin', 'owner'] },
  { name: 'LLM Providers', href: '/providers', icon: Cpu, permission: 'read:config' },
  { name: 'Resource Governor', href: '/resource-governor', icon: Gauge, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Security', href: '/security', icon: ShieldAlert, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Audit Logs', href: '/audit', icon: FileText, permission: 'read:audit' },
  { name: 'Monitoring', href: '/monitoring', icon: Activity, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Jobs', href: '/jobs', icon: ListChecks, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Usage', href: '/usage', icon: BarChart3, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Budgets', href: '/budgets', icon: Wallet, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Data Ops', href: '/data-ops', icon: Database, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Logs', href: '/logs', icon: ScrollText, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Flags', href: '/flags', icon: Flag, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Incidents', href: '/incidents', icon: AlertTriangle, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Debug', href: '/debug', icon: Bug, role: ['super_admin', 'owner'] },
  { name: 'Configuration', href: '/config', icon: Settings, role: ['super_admin', 'owner'] },
];

// Grouped navigation for sidebar sections
export const navigationSections: NavigationSection[] = [
  {
    title: 'Overview',
    items: [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Users & Access',
    items: [
      { name: 'Users', href: '/users', icon: Users, permission: 'read:users' },
      { name: 'Organizations', href: '/organizations', icon: Building2, permission: 'read:orgs' },
      { name: 'Teams', href: '/teams', icon: UserCog, permission: 'read:teams' },
      { name: 'Roles & Permissions', href: '/roles', icon: Shield, role: ['admin', 'super_admin', 'owner'] },
    ],
  },
  {
    title: 'API & Keys',
    items: [
      { name: 'API Keys', href: '/api-keys', icon: Key, permission: 'read:api_keys' },
      { name: 'BYOK', href: '/byok', icon: KeyRound, role: ['admin', 'super_admin', 'owner'] },
      { name: 'LLM Providers', href: '/providers', icon: Cpu, permission: 'read:config' },
    ],
  },
  {
    title: 'System',
    items: [
      { name: 'Monitoring', href: '/monitoring', icon: Activity, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Jobs', href: '/jobs', icon: ListChecks, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Audit Logs', href: '/audit', icon: FileText, permission: 'read:audit' },
      { name: 'Logs', href: '/logs', icon: ScrollText, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Incidents', href: '/incidents', icon: AlertTriangle, role: ['admin', 'super_admin', 'owner'] },
    ],
  },
  {
    title: 'Configuration',
    items: [
      { name: 'Resource Governor', href: '/resource-governor', icon: Gauge, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Security', href: '/security', icon: ShieldAlert, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Data Ops', href: '/data-ops', icon: Database, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Usage', href: '/usage', icon: BarChart3, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Budgets', href: '/budgets', icon: Wallet, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Flags', href: '/flags', icon: Flag, role: ['admin', 'super_admin', 'owner'] },
      { name: 'Settings', href: '/config', icon: Settings, role: ['super_admin', 'owner'] },
      { name: 'Debug', href: '/debug', icon: Bug, role: ['super_admin', 'owner'] },
    ],
  },
];

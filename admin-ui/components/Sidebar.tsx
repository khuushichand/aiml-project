'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Building2,
  Users,
  LayoutDashboard,
  LogOut,
  Key,
  Shield,
  Settings,
  FileText,
  Activity,
  Cpu,
  UserCog,
  Keyboard,
} from 'lucide-react';
import { logout, getCurrentUser, type AdminUser } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ThemeToggle';
import { OrgContextSwitcher } from '@/components/OrgContextSwitcher';
import { usePermissions } from '@/components/PermissionGuard';
import { useToast } from '@/components/ui/toast';

// Navigation items with required permissions/roles
const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Users', href: '/users', icon: Users, permission: 'read:users' },
  { name: 'Organizations', href: '/organizations', icon: Building2, permission: 'read:orgs' },
  { name: 'Teams', href: '/teams', icon: UserCog, permission: 'read:teams' },
  { name: 'Roles & Permissions', href: '/roles', icon: Shield, role: ['admin', 'super_admin', 'owner'] },
  { name: 'API Keys', href: '/api-keys', icon: Key, permission: 'read:api_keys' },
  { name: 'LLM Providers', href: '/providers', icon: Cpu, permission: 'read:config' },
  { name: 'Audit Logs', href: '/audit', icon: FileText, permission: 'read:audit' },
  { name: 'Monitoring', href: '/monitoring', icon: Activity, role: ['admin', 'super_admin', 'owner'] },
  { name: 'Configuration', href: '/config', icon: Settings, role: ['super_admin', 'owner'] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const { hasPermission, hasRole, loading: permLoading } = usePermissions();
  const { error: showError } = useToast();

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      setUser(null);
      router.push('/login');
    } catch (error) {
      console.error('Logout failed:', error);
      showError('Logout failed', 'Please try again.');
    }
  };

  // Filter navigation based on permissions
  const visibleNavigation = navigation.filter((item) => {
    // Always show items without permission requirements
    if (!item.permission && !item.role) return true;

    // While loading permissions, show all items (will be hidden if unauthorized)
    if (permLoading) return true;

    // Check permission if specified
    if (item.permission && hasPermission(item.permission)) return true;

    // Check role if specified
    if (item.role && hasRole(item.role)) return true;

    return false;
  });

  return (
    <div className="flex h-screen w-64 flex-col bg-card border-r">
      <div className="flex h-16 items-center justify-between border-b px-6">
        <h1 className="text-xl font-bold">tldw Admin</h1>
        <ThemeToggle />
      </div>

      {user && (
        <div className="border-b px-4 py-3">
          <p className="text-sm font-medium truncate">{user.username || user.email}</p>
          <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
        </div>
      )}

      {/* Org Context Switcher */}
      <div className="border-b px-3 py-2">
        <OrgContextSwitcher />
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
        {visibleNavigation.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'text-foreground hover:bg-muted'
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t px-3 py-4 space-y-2">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground"
          onClick={() => {
            // Trigger the keyboard shortcut for help
            const event = new KeyboardEvent('keydown', { key: '?', shiftKey: true });
            window.dispatchEvent(event);
          }}
        >
          <Keyboard className="h-5 w-5" />
          Shortcuts
          <kbd className="ml-auto px-1.5 py-0.5 bg-muted border rounded text-xs font-mono">
            ?
          </kbd>
        </Button>
        <Button
          variant="outline"
          className="w-full justify-start gap-3"
          onClick={handleLogout}
        >
          <LogOut className="h-5 w-5" />
          Logout
        </Button>
      </div>
    </div>
  );
}

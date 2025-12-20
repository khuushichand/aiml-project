'use client';

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
} from 'lucide-react';
import { logout, getCurrentUser } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ThemeToggle';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Users', href: '/users', icon: Users },
  { name: 'Organizations', href: '/organizations', icon: Building2 },
  { name: 'Teams', href: '/teams', icon: UserCog },
  { name: 'Roles & Permissions', href: '/roles', icon: Shield },
  { name: 'API Keys', href: '/api-keys', icon: Key },
  { name: 'LLM Providers', href: '/providers', icon: Cpu },
  { name: 'Audit Logs', href: '/audit', icon: FileText },
  { name: 'Monitoring', href: '/monitoring', icon: Activity },
  { name: 'Configuration', href: '/config', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getCurrentUser();

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

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

      <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
        {navigation.map((item) => {
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

      <div className="border-t px-3 py-4">
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

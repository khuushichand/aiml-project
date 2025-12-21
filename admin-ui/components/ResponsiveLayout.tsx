'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
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
  Menu,
  X,
} from 'lucide-react';
import { logout, getCurrentUser } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ThemeToggle';
import { OrgContextSwitcher } from '@/components/OrgContextSwitcher';
import { usePermissions } from '@/components/PermissionGuard';

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

// Mobile menu context
interface MobileMenuContextType {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

const MobileMenuContext = createContext<MobileMenuContextType>({
  isOpen: false,
  open: () => {},
  close: () => {},
  toggle: () => {},
});

export function useMobileMenu() {
  return useContext(MobileMenuContext);
}

// Mobile header with hamburger menu
function MobileHeader() {
  const { toggle } = useMobileMenu();

  return (
    <div className="lg:hidden fixed top-0 left-0 right-0 z-40 flex h-14 items-center justify-between border-b bg-card px-4">
      <Button variant="ghost" size="icon" onClick={toggle}>
        <Menu className="h-5 w-5" />
      </Button>
      <h1 className="text-lg font-bold">tldw Admin</h1>
      <ThemeToggle />
    </div>
  );
}

// Sidebar content (shared between mobile and desktop)
function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = getCurrentUser();
  const { hasPermission, hasRole, loading: permLoading } = usePermissions();

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const handleNavClick = () => {
    if (onNavigate) onNavigate();
  };

  // Filter navigation based on permissions
  const visibleNavigation = navigation.filter((item) => {
    if (!item.permission && !item.role) return true;
    if (permLoading) return true;
    if (item.permission && hasPermission(item.permission)) return true;
    if (item.role && hasRole(item.role)) return true;
    return false;
  });

  return (
    <>
      {/* Header - hidden on mobile since we have MobileHeader */}
      <div className="hidden lg:flex h-16 items-center justify-between border-b px-6">
        <h1 className="text-xl font-bold">tldw Admin</h1>
        <ThemeToggle />
      </div>

      {/* User info */}
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

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
        {visibleNavigation.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={handleNavClick}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'text-foreground hover:bg-muted'
              )}
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              <span className="truncate">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
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
    </>
  );
}

// Desktop sidebar
function DesktopSidebar() {
  return (
    <div className="hidden lg:flex h-screen w-64 flex-col bg-card border-r flex-shrink-0">
      <SidebarContent />
    </div>
  );
}

// Mobile sidebar (slide-out drawer)
function MobileSidebar() {
  const { isOpen, close } = useMobileMenu();

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50"
          onClick={close}
        />
      )}

      {/* Drawer */}
      <div
        className={cn(
          'lg:hidden fixed inset-y-0 left-0 z-50 w-64 bg-card border-r transform transition-transform duration-200 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Close button */}
        <div className="flex h-14 items-center justify-between border-b px-4">
          <h1 className="text-lg font-bold">tldw Admin</h1>
          <Button variant="ghost" size="icon" onClick={close}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex flex-col h-[calc(100%-3.5rem)]">
          <SidebarContent onNavigate={close} />
        </div>
      </div>
    </>
  );
}

// Main responsive layout component
interface ResponsiveLayoutProps {
  children: ReactNode;
}

export function ResponsiveLayout({ children }: ResponsiveLayoutProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  // Close mobile menu on route change
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setIsOpen(false);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [isOpen, pathname]);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  return (
    <MobileMenuContext.Provider
      value={{
        isOpen,
        open: () => setIsOpen(true),
        close: () => setIsOpen(false),
        toggle: () => setIsOpen(!isOpen),
      }}
    >
      <div className="flex h-screen bg-background">
        {/* Desktop sidebar */}
        <DesktopSidebar />

        {/* Mobile sidebar */}
        <MobileSidebar />

        {/* Mobile header */}
        <MobileHeader />

        {/* Main content */}
        <main className="flex-1 overflow-y-auto pt-14 lg:pt-0">
          {children}
        </main>
      </div>
    </MobileMenuContext.Provider>
  );
}

export default ResponsiveLayout;

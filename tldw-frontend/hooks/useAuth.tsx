import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import { useRouter } from 'next/router';
import { authService, getAuthMode, User } from '@/lib/auth';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check if user is logged in on mount
    const checkAuth = async () => {
      try {
        const mode = getAuthMode();

        // Env-based auth: synthesize a user and treat as authenticated
        if (mode === 'env_single_user' || mode === 'env_bearer') {
          const envUser = authService.getUser();
          if (envUser) {
            setUser(envUser);
          }
          return;
        }

        // JWT-based auth: validate token against backend and hydrate user profile
        if (mode === 'jwt') {
          const isValid = await authService.validateToken();
          if (isValid) {
            const currentUser = authService.getUser();
            if (currentUser) {
              setUser(currentUser);
            }
          } else {
            authService.logout();
            router.push('/login');
          }
        }
      } catch (error) {
        console.error('Auth check failed:', error);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [router]);

  const login = async (username: string, password: string) => {
    await authService.login({ username, password });
    const loggedInUser = authService.getUser();
    setUser(loggedInUser);
    router.push('/');
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

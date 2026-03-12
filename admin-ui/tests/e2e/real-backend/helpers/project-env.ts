export const REAL_BACKEND_PROJECTS = ['chromium-real-jwt', 'chromium-real-single-user'] as const;

export type RealBackendProjectName = (typeof REAL_BACKEND_PROJECTS)[number];
export type RealBackendAuthMode = 'multi_user' | 'single_user';

export type RealBackendProjectEnv = {
  projectName: RealBackendProjectName;
  authMode: RealBackendAuthMode;
  uiPort: number;
  apiPort: number;
  uiBaseUrl: string;
  apiBaseUrl: string;
  serverLabel: string;
};

const PROJECT_ENV: Record<RealBackendProjectName, RealBackendProjectEnv> = {
  'chromium-real-jwt': {
    projectName: 'chromium-real-jwt',
    authMode: 'multi_user',
    uiPort: 3101,
    apiPort: 8101,
    uiBaseUrl: 'http://127.0.0.1:3101',
    apiBaseUrl: 'http://127.0.0.1:8101',
    serverLabel: 'admin-ui-real-jwt',
  },
  'chromium-real-single-user': {
    projectName: 'chromium-real-single-user',
    authMode: 'single_user',
    uiPort: 3102,
    apiPort: 8102,
    uiBaseUrl: 'http://127.0.0.1:3102',
    apiBaseUrl: 'http://127.0.0.1:8102',
    serverLabel: 'admin-ui-real-single-user',
  },
};

export const isRealBackendProjectName = (value: string): value is RealBackendProjectName =>
  REAL_BACKEND_PROJECTS.includes(value as RealBackendProjectName);

export const getProjectEnv = (projectName: string): RealBackendProjectEnv => {
  if (!isRealBackendProjectName(projectName)) {
    throw new Error(`Unsupported real-backend project: ${projectName}`);
  }
  return PROJECT_ENV[projectName];
};

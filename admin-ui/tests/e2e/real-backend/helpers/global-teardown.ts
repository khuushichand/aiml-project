import { getProjectEnv, REAL_BACKEND_PROJECTS, shouldManageBackend } from './project-env';
import { stopManagedBackend } from './backend-lifecycle';

const shouldManageBackends = (): boolean =>
  process.argv.some((arg) => arg.includes('real-backend') || arg.includes('chromium-real-'));

export default async function globalTeardown(): Promise<void> {
  if (!shouldManageBackends()) {
    return;
  }

  for (const projectName of REAL_BACKEND_PROJECTS) {
    if (!shouldManageBackend(projectName)) {
      continue;
    }
    await stopManagedBackend(getProjectEnv(projectName)).catch(() => undefined);
  }
}

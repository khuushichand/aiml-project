import { getProjectEnv, REAL_BACKEND_PROJECTS } from './project-env';
import { startManagedBackend, stopManagedBackend, waitForManagedBackend } from './backend-lifecycle';

const shouldManageBackends = (): boolean =>
  process.argv.some((arg) => arg.includes('real-backend') || arg.includes('chromium-real-'));

const wait = async (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const warmUiRoute = async (
  baseUrl: string,
  path: string,
  init: RequestInit,
  acceptableStatuses: number[],
  timeoutMs = 60_000,
): Promise<void> => {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: {
          Accept: 'application/json, text/html;q=0.9, */*;q=0.8',
          ...(init.headers || {}),
        },
      });
      if (acceptableStatuses.includes(response.status)) {
        return;
      }
    } catch {
      // Keep polling until timeout.
    }
    await wait(250);
  }

  throw new Error(`UI route ${path} did not become ready for ${baseUrl} within ${timeoutMs}ms`);
};

export default async function globalSetup(): Promise<void> {
  if (!shouldManageBackends()) {
    return;
  }

  for (const projectName of REAL_BACKEND_PROJECTS) {
    const project = getProjectEnv(projectName);
    await stopManagedBackend(project).catch(() => undefined);
    await startManagedBackend(project);
  }

  for (const projectName of REAL_BACKEND_PROJECTS) {
    const project = getProjectEnv(projectName);
    await waitForManagedBackend(project);
    await warmUiRoute(project.uiBaseUrl, '/login', { method: 'GET' }, [200]);
    await warmUiRoute(
      project.uiBaseUrl,
      '/api/proxy/users/me',
      { method: 'GET' },
      [200, 401, 403],
    );
    if (project.authMode === 'multi_user') {
      await warmUiRoute(
        project.uiBaseUrl,
        '/api/auth/login',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: 'username=probe&password=probe',
        },
        [200, 400, 401, 403],
      );
    }
    if (project.authMode === 'single_user') {
      await warmUiRoute(
        project.uiBaseUrl,
        '/api/auth/apikey',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ apiKey: 'probe' }),
        },
        [200, 400, 401, 403],
      );
    }
  }
}

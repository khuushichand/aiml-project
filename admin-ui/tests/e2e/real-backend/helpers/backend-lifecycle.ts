import { spawn, type ChildProcess } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { type RealBackendProjectEnv } from './project-env';

export type ManagedBackendProcess = {
  process: ChildProcess;
  command: string;
  args: string[];
};

const currentDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(currentDir, '../../../../..');
const lifecycleScript = resolve(repoRoot, 'tldw_Server_API/scripts/server_lifecycle.py');

const getPythonCommand = (): string => process.env.TLDW_ADMIN_E2E_PYTHON || 'python';

export const buildBackendEnv = (
  project: RealBackendProjectEnv,
  overrides: Record<string, string> = {},
): NodeJS.ProcessEnv => ({
  ...process.env,
  SERVER_LABEL: project.serverLabel,
  SERVER_PORT: String(project.apiPort),
  E2E_TEST_BASE_URL: project.apiBaseUrl,
  AUTH_MODE: project.authMode,
  ...overrides,
});

export const startManagedBackend = (
  project: RealBackendProjectEnv,
  overrides: Record<string, string> = {},
): ManagedBackendProcess => {
  if (!existsSync(lifecycleScript)) {
    throw new Error(`Server lifecycle script not found at ${lifecycleScript}`);
  }

  const command = getPythonCommand();
  const args = [lifecycleScript, 'start'];
  const process = spawn(command, args, {
    cwd: repoRoot,
    env: buildBackendEnv(project, overrides),
    stdio: 'inherit',
  });

  return { process, command, args };
};

export const stopManagedBackend = async (
  project: RealBackendProjectEnv,
  overrides: Record<string, string> = {},
): Promise<void> => {
  if (!existsSync(lifecycleScript)) {
    return;
  }

  await new Promise<void>((resolve, reject) => {
    const command = getPythonCommand();
    const args = [lifecycleScript, 'stop'];
    const stopProcess = spawn(command, args, {
      cwd: repoRoot,
      env: buildBackendEnv(project, overrides),
      stdio: 'inherit',
    });

    stopProcess.once('error', reject);
    stopProcess.once('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Failed to stop managed backend for ${project.projectName} (exit ${code ?? 'null'})`));
    });
  });
};

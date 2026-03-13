export type FixturePasswordAlias =
  | 'admin'
  | 'owner'
  | 'super_admin'
  | 'member'
  | 'requester';

type FixturePasswordEnv = {
  admin: 'TLDW_ADMIN_E2E_ADMIN_PASSWORD';
  owner: 'TLDW_ADMIN_E2E_OWNER_PASSWORD';
  super_admin: 'TLDW_ADMIN_E2E_SUPER_ADMIN_PASSWORD';
  member: 'TLDW_ADMIN_E2E_MEMBER_PASSWORD';
  requester: 'TLDW_ADMIN_E2E_REQUESTER_PASSWORD';
};

const FIXTURE_PASSWORD_ENV: FixturePasswordEnv = {
  admin: 'TLDW_ADMIN_E2E_ADMIN_PASSWORD',
  owner: 'TLDW_ADMIN_E2E_OWNER_PASSWORD',
  super_admin: 'TLDW_ADMIN_E2E_SUPER_ADMIN_PASSWORD',
  member: 'TLDW_ADMIN_E2E_MEMBER_PASSWORD',
  requester: 'TLDW_ADMIN_E2E_REQUESTER_PASSWORD',
};

const FIXTURE_PASSWORD_DEFAULTS: Record<FixturePasswordAlias, string> = {
  admin: 'AdminPass123!',
  owner: 'AdminPass123!',
  super_admin: 'AdminPass123!',
  member: 'MemberPass123!',
  requester: 'RequesterPass123!',
};

const ensureFixturePassword = (alias: FixturePasswordAlias): string => {
  const envName = FIXTURE_PASSWORD_ENV[alias];
  const configured = process.env[envName]?.trim();
  if (configured) {
    return configured;
  }

  const fallback = FIXTURE_PASSWORD_DEFAULTS[alias];
  process.env[envName] = fallback;
  return fallback;
};

export const getFixturePassword = (alias: FixturePasswordAlias): string =>
  ensureFixturePassword(alias);

export const getFixturePasswordEnv = (): Record<string, string> => ({
  [FIXTURE_PASSWORD_ENV.admin]: ensureFixturePassword('admin'),
  [FIXTURE_PASSWORD_ENV.owner]: ensureFixturePassword('owner'),
  [FIXTURE_PASSWORD_ENV.super_admin]: ensureFixturePassword('super_admin'),
  [FIXTURE_PASSWORD_ENV.member]: ensureFixturePassword('member'),
  [FIXTURE_PASSWORD_ENV.requester]: ensureFixturePassword('requester'),
});

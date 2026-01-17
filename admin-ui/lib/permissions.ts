import { ROLE_RANK, getRoleRank } from './roles';

export type OrgMembership = {
  org_id: number;
  role: string;
};

export const canEditFromMemberships = (
  adminRoles: OrgMembership[],
  targetRoles: OrgMembership[]
): boolean => {
  if (adminRoles.length === 0 || targetRoles.length === 0) {
    return false;
  }

  const adminByOrg = new Map<number, string>(
    adminRoles.map((membership) => [membership.org_id, membership.role])
  );
  const targetByOrg = new Map<number, string>(
    targetRoles.map((membership) => [membership.org_id, membership.role])
  );

  const sharedOrgs = [...adminByOrg.keys()].filter((orgId) => targetByOrg.has(orgId));
  if (sharedOrgs.length === 0) {
    return false;
  }

  return sharedOrgs.some((orgId) => {
    const adminRole = adminByOrg.get(orgId) || '';
    const targetRole = targetByOrg.get(orgId) || '';
    const adminRank = getRoleRank(adminRole) ?? 0;
    const targetRank = getRoleRank(targetRole) ?? 0;
    return adminRank >= ROLE_RANK.admin && adminRank >= targetRank;
  });
};

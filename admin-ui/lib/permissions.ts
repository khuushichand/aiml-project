export type OrgMembership = {
  org_id: number;
  role: string;
};

const roleRank: Record<string, number> = {
  owner: 4,
  super_admin: 5,
  admin: 3,
  member: 1,
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
    const adminRank = roleRank[adminRole] || 0;
    const targetRank = roleRank[targetRole] || 0;
    return adminRank >= roleRank.admin && adminRank >= targetRank;
  });
};

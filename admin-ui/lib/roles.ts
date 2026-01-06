export const ROLE_RANK: Record<string, number> = {
  super_admin: 3,
  owner: 3,
  admin: 2,
  member: 1,
  user: 0,
  service: 0,
};

export const getRoleRank = (role?: string | null): number | undefined => {
  if (!role) return undefined;
  return ROLE_RANK[role];
};

export const hasRoleAccess = (currentRole: string | null | undefined, requiredRoles: string[]): boolean => {
  if (requiredRoles.length === 0) {
    return true;
  }
  if (!currentRole) {
    return false;
  }
  const currentRank = getRoleRank(currentRole);
  if (currentRank === undefined) {
    return false;
  }
  return requiredRoles.some((requiredRole) => {
    const requiredRank = getRoleRank(requiredRole);
    if (requiredRank === undefined) {
      return false;
    }
    return currentRank >= requiredRank;
  });
};

export const isAdminRole = (role?: string | null): boolean => {
  const rank = getRoleRank(role);
  return rank !== undefined && rank >= ROLE_RANK.admin;
};

export const isSuperAdminRole = (role?: string | null): boolean => {
  const rank = getRoleRank(role);
  return rank !== undefined && rank >= ROLE_RANK.super_admin;
};

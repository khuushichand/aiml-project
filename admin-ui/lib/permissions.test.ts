import { describe, it, expect } from '@jest/globals';
import { canEditFromMemberships, type OrgMembership } from './permissions';

const membership = (org_id: number, role: string): OrgMembership => ({ org_id, role });

describe('canEditFromMemberships', () => {
  it('denies edit when both membership lists are empty', () => {
    expect(canEditFromMemberships([], [])).toBe(false);
  });

  it('denies edit when admin memberships are empty', () => {
    expect(canEditFromMemberships([], [membership(1, 'member')])).toBe(false);
  });

  it('denies edit when target memberships are empty', () => {
    expect(canEditFromMemberships([membership(1, 'admin')], [])).toBe(false);
  });

  it('denies edit when there is no shared org', () => {
    const adminRoles = [membership(1, 'admin')];
    const targetRoles = [membership(2, 'member')];
    expect(canEditFromMemberships(adminRoles, targetRoles)).toBe(false);
  });

  it('allows edit when admin role meets threshold and target rank', () => {
    const adminRoles = [membership(1, 'admin')];
    const targetRoles = [membership(1, 'member')];
    expect(canEditFromMemberships(adminRoles, targetRoles)).toBe(true);
  });

  it('denies edit when admin role is below target role', () => {
    const adminRoles = [membership(1, 'admin')];
    const targetRoles = [membership(1, 'owner')];
    expect(canEditFromMemberships(adminRoles, targetRoles)).toBe(false);
  });
});

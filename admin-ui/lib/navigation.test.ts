import { describe, expect, it } from 'vitest';
import {
  matchesNavigationQuery,
  navigation,
  navigationSections,
  type NavigationItem,
} from './navigation';

describe('navigation information architecture', () => {
  it('keeps sections in the intended order', () => {
    expect(navigationSections.map((section) => section.title)).toEqual([
      'Overview',
      'Identity & Access',
      'AI & Models',
      'Operations',
      'Governance',
      'Advanced',
    ]);
  });

  it('includes key admin destinations in operations and governance groups', () => {
    const operations = navigationSections.find((section) => section.title === 'Operations');
    const governance = navigationSections.find((section) => section.title === 'Governance');

    expect(operations?.items.map((item) => item.href)).toContain('/monitoring');
    expect(operations?.items.map((item) => item.href)).toContain('/incidents');
    expect(governance?.items.map((item) => item.href)).toContain('/security');
    expect(governance?.items.map((item) => item.href)).toContain('/resource-governor');
  });
});

describe('matchesNavigationQuery', () => {
  const usersItem = navigation.find((item) => item.href === '/users') as NavigationItem;
  const providersItem = navigation.find((item) => item.href === '/providers') as NavigationItem;

  it('matches by item name', () => {
    expect(matchesNavigationQuery(usersItem, 'Identity & Access', 'users')).toBe(true);
  });

  it('matches by section name', () => {
    expect(matchesNavigationQuery(usersItem, 'Identity & Access', 'identity')).toBe(true);
  });

  it('matches by keyword metadata', () => {
    expect(matchesNavigationQuery(providersItem, 'AI & Models', 'models')).toBe(true);
  });

  it('returns false when query does not match', () => {
    expect(matchesNavigationQuery(usersItem, 'Identity & Access', 'billing')).toBe(false);
  });
});

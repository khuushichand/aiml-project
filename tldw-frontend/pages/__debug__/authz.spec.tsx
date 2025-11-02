import { isAdmin } from '@/lib/authz';

type Case = { name: string; user: any; expected: boolean };

const cases: Case[] = [
  { name: 'null user -> false', user: null, expected: false },
  { name: 'is_admin true', user: { is_admin: true }, expected: true },
  { name: 'isAdmin true', user: { isAdmin: true }, expected: true },
  { name: 'role admin (string)', user: { role: 'admin' }, expected: true },
  { name: 'role ADMIN (case-insensitive)', user: { role: 'ADMIN' }, expected: true },
  { name: 'roles includes admin (array)', user: { roles: ['user', 'admin'] }, expected: true },
  { name: 'roles single string value', user: { roles: 'admin' }, expected: true },
  { name: 'permissions includes admin', user: { permissions: ['read', 'admin'] }, expected: true },
  { name: 'scopes includes admin', user: { scopes: ['foo', 'admin'] }, expected: true },
  { name: 'non-admin user', user: { role: 'user', roles: ['member'], permissions: ['read'], scopes: [] }, expected: false },
];

export default function AuthzSpecPage() {
  const enabled = String(process.env.NEXT_PUBLIC_ENABLE_DEBUG || '').trim().toLowerCase() === 'true';
  const results = cases.map((c) => ({
    name: c.name,
    expected: c.expected,
    actual: isAdmin(c.user),
  }));
  const pass = results.every((r) => r.actual === r.expected);

  if (!enabled) {
    return (
      <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
        <h1>AuthZ Spec</h1>
        <p>Debug pages are disabled. Set NEXT_PUBLIC_ENABLE_DEBUG=true to view tests.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <h1>AuthZ Spec: isAdmin</h1>
      <div style={{ margin: '8px 0' }}>
        Overall: <strong style={{ color: pass ? 'green' : 'red' }}>{pass ? 'PASS' : 'FAIL'}</strong>
      </div>
      <table style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ddd' }}>Case</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ddd' }}>Expected</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ddd' }}>Actual</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ddd' }}>Result</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => {
            const ok = r.actual === r.expected;
            return (
              <tr key={r.name}>
                <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0' }}>{r.name}</td>
                <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0' }}>{String(r.expected)}</td>
                <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0' }}>{String(r.actual)}</td>
                <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0', color: ok ? 'green' : 'red' }}>{ok ? 'PASS' : 'FAIL'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

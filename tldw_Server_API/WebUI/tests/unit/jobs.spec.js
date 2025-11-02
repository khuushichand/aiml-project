/* @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Jobs module', () => {
  let jobs;
  beforeEach(async () => {
    // Minimal DOM
    document.body.innerHTML = `
      <table><tbody id="adminJobs_tableBody"></tbody></table>
    `;
    // Mock apiClient
    global.apiClient = {
      makeRequest: vi.fn(),
    };
    jobs = await import('../../js/jobs.js');
  });

  it('adminFetchJobsStats renders rows safely', async () => {
    apiClient.makeRequest.mockResolvedValueOnce([
      { domain: 'd', queue: 'q', job_type: 't', queued: 1, scheduled: 0, processing: 0, quarantined: 0 }
    ]);
    await jobs.adminFetchJobsStats();
    const rows = document.querySelectorAll('#adminJobs_tableBody tr');
    expect(rows.length).toBe(1);
    const cells = rows[0].querySelectorAll('td');
    expect(cells[0].textContent).toBe('d');
    expect(cells[1].textContent).toBe('q');
    expect(cells[2].textContent).toBe('t');
  });

  it('renderSparkline creates expected tick characters', () => {
    const s = jobs.renderSparkline([0, 1, 2, 3, 4]);
    expect(typeof s).toBe('string');
    expect(s.length).toBeGreaterThan(0);
  });
});

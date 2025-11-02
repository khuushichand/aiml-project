/* @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Utils from '../../js/utils.js';

describe('Utils', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it('debounce limits calls', async () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = Utils.debounce(fn, 100);
    debounced(); debounced(); debounced();
    expect(fn).toHaveBeenCalledTimes(0);
    vi.advanceTimersByTime(99);
    expect(fn).toHaveBeenCalledTimes(0);
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('escapeHtml prevents XSS chars', () => {
    expect(Utils.escapeHtml('<script>"&')).toBe('&lt;script&gt;&quot;&amp;');
  });

  it('saveToStorage/getFromStorage with expiry', () => {
    Utils.saveToStorage('k', { a: 1 }, 0.001);
    expect(Utils.getFromStorage('k')).toEqual({ a: 1 });
  });

  it('parseJSONSafely returns default on invalid JSON', () => {
    expect(Utils.parseJSONSafely('{bad}', { d: 1 })).toEqual({ d: 1 });
    expect(Utils.parseJSONSafely('[]', { d: 1 })).toEqual([]);
  });

  it('validateFileUpload enforces size/ext/type', () => {
    const file = new File(['abc'], 'a.txt', { type: 'text/plain' });
    expect(Utils.validateFileUpload(file, { maxSize: 2 }).valid).toBe(false);
    expect(Utils.validateFileUpload(file, { allowedExtensions: ['pdf'] }).valid).toBe(false);
    expect(Utils.validateFileUpload(file, { allowedExtensions: ['txt'] }).valid).toBe(true);
  });

  it('retryWithBackoff retries and eventually resolves', async () => {
    vi.useFakeTimers();
    const fn = vi.fn()
      .mockRejectedValueOnce(new Error('nope'))
      .mockRejectedValueOnce(new Error('nope'))
      .mockResolvedValue('ok');

    const promise = Utils.retryWithBackoff(fn, { initialDelay: 1, maxDelay: 2 });
    // advance timers enough to pass both retries
    await vi.advanceTimersByTimeAsync(10);
    await expect(promise).resolves.toBe('ok');
    expect(fn).toHaveBeenCalledTimes(3);
  });
});

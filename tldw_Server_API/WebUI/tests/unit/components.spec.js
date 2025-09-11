/* @vitest-environment jsdom */
import { describe, it, expect, beforeEach } from 'vitest';
import { ToastManager, Modal, JSONViewer } from '../../js/components.js';

describe('Components', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('ToastManager shows toast', () => {
    const tm = new ToastManager();
    const toast = tm.success('Done', 1);
    expect(document.querySelector('#toast-container')).toBeTruthy();
    expect(toast).toBeTruthy();
  });

  it('Modal opens and closes', () => {
    const modal = new Modal({ title: 'T', content: '<div>c</div>' });
    modal.show();
    expect(document.querySelector('.modal')).toBeTruthy();
    modal.close();
    expect(document.querySelector('.modal')).toBeFalsy();
  });

  it('JSONViewer renders and toggles', () => {
    const container = document.createElement('div');
    new JSONViewer(container, { a: [1, 2] }, { expanded: 0 });
    const toggle = container.querySelector('.json-toggle');
    expect(toggle).toBeTruthy();
    toggle.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const content = container.querySelector('.json-content');
    expect(content).toBeTruthy();
  });
});


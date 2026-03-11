/* @vitest-environment jsdom */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { UserBulkActions } from './UserBulkActions';

const noop = () => {};

describe('UserBulkActions', () => {
  it('renders nothing when no users are selected', () => {
    const { container } = render(
      <UserBulkActions
        selectedCount={0}
        bulkRole="user"
        bulkRoleOptions={['user', 'admin']}
        bulkBusy={false}
        bulkAction={null}
        onBulkRoleChange={noop}
        onAssignRole={noop}
        onActivate={noop}
        onDeactivate={noop}
        onRequireMfa={noop}
        onClearMfa={noop}
        onDelete={noop}
        onClearSelection={noop}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('delegates role selection and bulk action clicks', async () => {
    const user = userEvent.setup();
    const onBulkRoleChange = vi.fn();
    const onAssignRole = vi.fn();
    const onActivate = vi.fn();
    const onClearSelection = vi.fn();

    render(
      <UserBulkActions
        selectedCount={2}
        bulkRole="user"
        bulkRoleOptions={['user', 'admin']}
        bulkBusy={false}
        bulkAction={null}
        onBulkRoleChange={onBulkRoleChange}
        onAssignRole={onAssignRole}
        onActivate={onActivate}
        onDeactivate={noop}
        onRequireMfa={noop}
        onClearMfa={noop}
        onDelete={noop}
        onClearSelection={onClearSelection}
      />
    );

    await user.selectOptions(screen.getByLabelText('Bulk role selection'), 'admin');
    expect(onBulkRoleChange).toHaveBeenCalledWith('admin');

    await user.click(screen.getByRole('button', { name: 'Assign Role' }));
    expect(onAssignRole).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Activate' }));
    expect(onActivate).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Clear selection' }));
    expect(onClearSelection).toHaveBeenCalledTimes(1);
  });
});

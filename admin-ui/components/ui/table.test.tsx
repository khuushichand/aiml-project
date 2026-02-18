/* @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './table';

afterEach(() => {
  cleanup();
});

describe('TableHeader', () => {
  it('applies sticky header classes by default', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Value</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );

    const headerCell = screen.getByRole('columnheader', { name: 'Name' });
    const thead = headerCell.closest('thead');
    expect(thead?.classList.contains('sticky')).toBe(true);
    expect(thead?.classList.contains('top-0')).toBe(true);
    expect(thead?.classList.contains('z-10')).toBe(true);
  });

  it('renders an sr-only caption when the caption prop is provided', () => {
    render(
      <Table caption="List of users table with 1 row.">
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Value</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );

    const caption = screen.getByText('List of users table with 1 row.');
    expect(caption.tagName.toLowerCase()).toBe('caption');
    expect(caption.classList.contains('sr-only')).toBe(true);
  });

  it('generates a fallback caption with headers and row count when caption is omitted', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Alpha</TableCell>
            <TableCell>Active</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Beta</TableCell>
            <TableCell>Paused</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );

    expect(screen.getByText('Table columns: Name, Status. 2 rows.')).toBeInTheDocument();
  });

  it('shows horizontal scroll shadows when table overflows', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Value</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );

    const container = screen.getByTestId('table-scroll-container');
    Object.defineProperty(container, 'clientWidth', { configurable: true, value: 100 });
    Object.defineProperty(container, 'scrollWidth', { configurable: true, value: 320 });
    Object.defineProperty(container, 'scrollLeft', { configurable: true, writable: true, value: 0 });

    fireEvent(window, new Event('resize'));
    expect(screen.queryByTestId('table-scroll-shadow-left')).toBeNull();
    expect(screen.queryByTestId('table-scroll-shadow-right')).not.toBeNull();

    Object.defineProperty(container, 'scrollLeft', { configurable: true, writable: true, value: 60 });
    fireEvent.scroll(container);
    expect(screen.queryByTestId('table-scroll-shadow-left')).not.toBeNull();
    expect(screen.queryByTestId('table-scroll-shadow-right')).not.toBeNull();

    Object.defineProperty(container, 'scrollLeft', { configurable: true, writable: true, value: 220 });
    fireEvent.scroll(container);
    expect(screen.queryByTestId('table-scroll-shadow-right')).toBeNull();
  });
});

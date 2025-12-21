import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatComposer } from '../ChatComposer';

describe('ChatComposer', () => {
  it('renders textarea with placeholder', () => {
    render(<ChatComposer placeholder="Type a message..." />);
    expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
  });

  it('displays the text value', () => {
    render(<ChatComposer text="Hello world" />);
    expect(screen.getByRole('textbox')).toHaveValue('Hello world');
  });

  it('calls onChange when typing', async () => {
    const handleChange = vi.fn();
    render(<ChatComposer onChange={handleChange} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'H');
    expect(handleChange).toHaveBeenCalledWith('H');
  });

  it('is disabled when disabled prop is true', () => {
    render(<ChatComposer disabled />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });

  it('renders with custom rows', () => {
    render(<ChatComposer rows={5} />);
    expect(screen.getByRole('textbox')).toHaveAttribute('rows', '5');
  });

  it('renders right actions', () => {
    render(
      <ChatComposer
        rightActions={[
          <button key="send" data-testid="send-btn">
            Send
          </button>,
        ]}
      />
    );
    expect(screen.getByTestId('send-btn')).toBeInTheDocument();
  });

  it('calls onSend with Ctrl+Enter when text is present', () => {
    const handleSend = vi.fn();
    render(<ChatComposer text="Hello" onSend={handleSend} />);
    const textarea = screen.getByRole('textbox');
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    expect(handleSend).toHaveBeenCalledWith('text', 'Hello');
  });

  it('calls onSend with Meta+Enter (Mac) when text is present', () => {
    const handleSend = vi.fn();
    render(<ChatComposer text="Hello" onSend={handleSend} />);
    const textarea = screen.getByRole('textbox');
    fireEvent.keyDown(textarea, { key: 'Enter', metaKey: true });
    expect(handleSend).toHaveBeenCalledWith('text', 'Hello');
  });

  it('does not call onSend when text is empty or whitespace', () => {
    const handleSend = vi.fn();
    render(<ChatComposer text="   " onSend={handleSend} />);
    const textarea = screen.getByRole('textbox');
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    expect(handleSend).not.toHaveBeenCalled();
  });

  it('does not call onSend on Enter without modifier keys', () => {
    const handleSend = vi.fn();
    render(<ChatComposer text="Hello" onSend={handleSend} />);
    const textarea = screen.getByRole('textbox');
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(handleSend).not.toHaveBeenCalled();
  });
});

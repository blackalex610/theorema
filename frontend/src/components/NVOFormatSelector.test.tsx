import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NVOFormatSelector from './NVOFormatSelector';

describe('NVOFormatSelector', () => {
  it('calls onSelect with "short" when the short-format card is clicked', async () => {
    const onSelect = vi.fn();
    render(<NVOFormatSelector selected="full" onSelect={onSelect} />);

    await userEvent.click(screen.getByText('Кратък НВО'));

    expect(onSelect).toHaveBeenCalledWith('short');
  });

  it('calls onSelect with "full" when the full-format card is clicked', async () => {
    const onSelect = vi.fn();
    render(<NVOFormatSelector selected="short" onSelect={onSelect} />);

    await userEvent.click(screen.getByText('Пълен НВО'));

    expect(onSelect).toHaveBeenCalledWith('full');
  });

  it('does not call onSelect when disabled', async () => {
    const onSelect = vi.fn();
    render(<NVOFormatSelector selected="full" onSelect={onSelect} disabled />);

    await userEvent.click(screen.getByText('Кратък НВО'));

    expect(onSelect).not.toHaveBeenCalled();
  });
});

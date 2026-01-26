'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ToggleBadgeGroupProps {
  /** Available options to display as badges */
  options: string[];
  /** Currently selected options */
  selected: string[];
  /** Callback when selection changes */
  onChange: (selected: string[]) => void;
  /** Accessible label for the group */
  label: string;
  /** Optional className for the container */
  className?: string;
  /** Allow multiple selections (default: true) */
  multiSelect?: boolean;
  /** Size variant */
  size?: 'sm' | 'md';
}

/**
 * Keyboard-navigable badge selection group.
 * Supports: arrow keys to navigate, Enter/Space to toggle selection.
 */
const ToggleBadgeGroup = React.forwardRef<HTMLDivElement, ToggleBadgeGroupProps>(
  (
    {
      options,
      selected,
      onChange,
      label,
      className,
      multiSelect = true,
      size = 'md',
    },
    ref
  ) => {
    const [focusedIndex, setFocusedIndex] = React.useState<number>(-1);
    const containerRef = React.useRef<HTMLDivElement>(null);

    const handleKeyDown = (event: React.KeyboardEvent, index: number) => {
      switch (event.key) {
        case 'ArrowRight':
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex((index + 1) % options.length);
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex((index - 1 + options.length) % options.length);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          toggleOption(options[index]);
          break;
        case 'Home':
          event.preventDefault();
          setFocusedIndex(0);
          break;
        case 'End':
          event.preventDefault();
          setFocusedIndex(options.length - 1);
          break;
      }
    };

    const toggleOption = (option: string) => {
      if (multiSelect) {
        const isSelected = selected.includes(option);
        if (isSelected) {
          onChange(selected.filter((s) => s !== option));
        } else {
          onChange([...selected, option]);
        }
      } else {
        onChange([option]);
      }
    };

    // Focus the badge when focusedIndex changes
    React.useEffect(() => {
      if (focusedIndex >= 0 && containerRef.current) {
        const buttons = containerRef.current.querySelectorAll('button');
        buttons[focusedIndex]?.focus();
      }
    }, [focusedIndex]);

    const badgeSize = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

    return (
      <div
        ref={(node) => {
          // Support both refs
          if (typeof ref === 'function') {
            ref(node);
          } else if (ref) {
            ref.current = node;
          }
          (containerRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
        }}
        role="group"
        aria-label={label}
        className={cn('flex flex-wrap gap-2', className)}
      >
        {options.map((option, index) => {
          const isSelected = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              role="checkbox"
              aria-checked={isSelected}
              tabIndex={focusedIndex === index || (focusedIndex === -1 && index === 0) ? 0 : -1}
              onClick={() => toggleOption(option)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              onFocus={() => setFocusedIndex(index)}
              className={cn(
                'inline-flex items-center rounded-full border font-medium transition-colors',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                'cursor-pointer select-none',
                badgeSize,
                isSelected
                  ? 'border-transparent bg-primary text-primary-foreground hover:bg-primary/80'
                  : 'border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              {option}
            </button>
          );
        })}
      </div>
    );
  }
);

ToggleBadgeGroup.displayName = 'ToggleBadgeGroup';

export { ToggleBadgeGroup };

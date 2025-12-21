'use client';

import { useKeyboardShortcuts, getShortcutGroups, formatShortcutKey } from '@/lib/use-keyboard-shortcuts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Keyboard } from 'lucide-react';

export function KeyboardShortcutsProvider({ children }: { children: React.ReactNode }) {
  const { isHelpOpen, setIsHelpOpen, shortcuts, pendingPrefix } = useKeyboardShortcuts();
  const groups = getShortcutGroups(shortcuts);

  return (
    <>
      {children}

      {/* Pending prefix indicator */}
      {pendingPrefix && (
        <div className="fixed bottom-4 right-4 bg-primary text-primary-foreground px-3 py-2 rounded-lg shadow-lg z-50 flex items-center gap-2">
          <Keyboard className="h-4 w-4" />
          <span className="font-mono font-bold">{pendingPrefix.toUpperCase()}</span>
          <span className="text-sm opacity-80">waiting for next key...</span>
        </div>
      )}

      {/* Keyboard shortcuts help dialog */}
      <Dialog open={isHelpOpen} onOpenChange={setIsHelpOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Keyboard className="h-5 w-5" />
              Keyboard Shortcuts
            </DialogTitle>
            <DialogDescription>
              Use these shortcuts to navigate quickly
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 mt-4">
            {Object.entries(groups).map(([category, categoryShortcuts]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-muted-foreground mb-3">
                  {category}
                </h3>
                <div className="space-y-2">
                  {categoryShortcuts.map((shortcut) => (
                    <div
                      key={shortcut.key}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm">{shortcut.description}</span>
                      <ShortcutBadge shortcut={formatShortcutKey(shortcut)} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-4 border-t text-xs text-muted-foreground">
            <p>
              <strong>Tip:</strong> Press <ShortcutBadge shortcut="G" /> followed by a letter to navigate.
              For example, <ShortcutBadge shortcut="G" /> then <ShortcutBadge shortcut="U" /> goes to Users.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ShortcutBadge({ shortcut }: { shortcut: string }) {
  // Split by "then" for multi-key shortcuts
  const parts = shortcut.split(' then ');

  return (
    <span className="flex items-center gap-1">
      {parts.map((part, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-muted-foreground text-xs mx-1">then</span>}
          {part.split(' + ').map((key, j) => (
            <kbd
              key={j}
              className="px-2 py-0.5 bg-muted border rounded text-xs font-mono font-semibold"
            >
              {key}
            </kbd>
          ))}
        </span>
      ))}
    </span>
  );
}

// Button to show keyboard shortcuts from UI
export function KeyboardShortcutsButton() {
  const { setIsHelpOpen } = useKeyboardShortcuts();

  return (
    <button
      onClick={() => setIsHelpOpen(true)}
      className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      title="Keyboard shortcuts (Shift+?)"
    >
      <Keyboard className="h-4 w-4" />
      <span className="hidden lg:inline">Shortcuts</span>
      <kbd className="hidden lg:inline px-1.5 py-0.5 bg-muted border rounded text-xs font-mono">
        ?
      </kbd>
    </button>
  );
}

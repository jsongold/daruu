/**
 * Custom hook for handling keyboard shortcuts.
 * Provides undo/redo and escape key handling.
 */

import { useEffect, useCallback, useRef } from 'react';

export interface KeyboardShortcutHandlers {
  /** Called on Ctrl/Cmd+Z */
  onUndo?: () => void;
  /** Called on Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y */
  onRedo?: () => void;
  /** Called on Escape key */
  onEscape?: () => void;
  /** Called on Ctrl/Cmd+S */
  onSave?: () => void;
}

export interface UseKeyboardShortcutsOptions {
  /** Whether shortcuts are enabled */
  enabled?: boolean;
  /** Prevent default browser behavior for handled keys */
  preventDefault?: boolean;
  /** Element to attach listeners to (defaults to document) */
  targetRef?: React.RefObject<HTMLElement>;
}

/**
 * Hook for handling keyboard shortcuts.
 *
 * @example
 * ```tsx
 * useKeyboardShortcuts({
 *   onUndo: () => edits.undo(),
 *   onRedo: () => edits.redo(),
 *   onEscape: () => setEditingFieldId(null),
 * });
 * ```
 */
export function useKeyboardShortcuts(
  handlers: KeyboardShortcutHandlers,
  options: UseKeyboardShortcutsOptions = {}
): void {
  const {
    enabled = true,
    preventDefault = true,
  } = options;

  // Store handlers in ref to avoid recreating the effect
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Check if user is typing in an input field
    const target = event.target as HTMLElement;
    const isInputField =
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable;

    // Get modifier key based on OS
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const modifierKey = isMac ? event.metaKey : event.ctrlKey;

    // Handle shortcuts
    if (modifierKey) {
      // Ctrl/Cmd+Z - Undo
      if (event.key === 'z' && !event.shiftKey) {
        // Allow undo in input fields but also call our handler
        if (handlersRef.current.onUndo) {
          if (preventDefault && !isInputField) {
            event.preventDefault();
          }
          handlersRef.current.onUndo();
        }
        return;
      }

      // Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y - Redo
      if ((event.key === 'z' && event.shiftKey) || event.key === 'y') {
        if (handlersRef.current.onRedo) {
          if (preventDefault && !isInputField) {
            event.preventDefault();
          }
          handlersRef.current.onRedo();
        }
        return;
      }

      // Ctrl/Cmd+S - Save
      if (event.key === 's') {
        if (handlersRef.current.onSave) {
          if (preventDefault) {
            event.preventDefault();
          }
          handlersRef.current.onSave();
        }
        return;
      }
    }

    // Escape - Close/Cancel
    if (event.key === 'Escape') {
      if (handlersRef.current.onEscape) {
        handlersRef.current.onEscape();
      }
      return;
    }
  }, [preventDefault]);

  useEffect(() => {
    if (!enabled) return;

    const target = options.targetRef?.current ?? document;
    target.addEventListener('keydown', handleKeyDown as EventListener);

    return () => {
      target.removeEventListener('keydown', handleKeyDown as EventListener);
    };
  }, [enabled, handleKeyDown, options.targetRef]);
}

/**
 * Hook for detecting if a specific key combination is pressed.
 */
export function useIsKeyPressed(key: string): boolean {
  const pressedRef = useRef(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === key) {
        pressedRef.current = true;
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === key) {
        pressedRef.current = false;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('keyup', handleKeyUp);
    };
  }, [key]);

  return pressedRef.current;
}

/**
 * Get the display string for a keyboard shortcut.
 */
export function getShortcutDisplay(
  key: string,
  modifiers: { ctrl?: boolean; shift?: boolean; alt?: boolean } = {}
): string {
  const isMac = typeof navigator !== 'undefined' &&
    navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  const parts: string[] = [];

  if (modifiers.ctrl) {
    parts.push(isMac ? '⌘' : 'Ctrl');
  }
  if (modifiers.alt) {
    parts.push(isMac ? '⌥' : 'Alt');
  }
  if (modifiers.shift) {
    parts.push(isMac ? '⇧' : 'Shift');
  }

  // Format key
  let displayKey = key;
  if (key === 'Escape') displayKey = 'Esc';
  if (key === 'Enter') displayKey = '↵';
  if (key === 'Backspace') displayKey = '⌫';
  if (key === 'Delete') displayKey = '⌦';
  if (key === 'ArrowUp') displayKey = '↑';
  if (key === 'ArrowDown') displayKey = '↓';
  if (key === 'ArrowLeft') displayKey = '←';
  if (key === 'ArrowRight') displayKey = '→';

  parts.push(displayKey.toUpperCase());

  return parts.join(isMac ? '' : '+');
}

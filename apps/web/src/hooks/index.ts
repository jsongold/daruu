/**
 * Custom hooks exports
 */

export { useJob, useJobPolling } from './useJob';
export type { UseJobOptions, UseJobReturn } from './useJob';

export { useDocumentUpload, formatFileSize } from './useDocumentUpload';
export type { UseDocumentUploadOptions, UseDocumentUploadReturn } from './useDocumentUpload';

export { useDebounce, useDebouncedCallback, useDebouncedSave } from './useDebounce';

export { useConversation } from './useConversation';
export type { UseConversationOptions, UseConversationReturn } from './useConversation';

export { useTemplates } from './useTemplates';
export type { UseTemplatesOptions, UseTemplatesReturn } from './useTemplates';

export { useEdits } from './useEdits';
export type { UseEditsOptions, UseEditsReturn } from './useEdits';

export { useKeyboardShortcuts, useIsKeyPressed, getShortcutDisplay } from './useKeyboardShortcuts';
export type { KeyboardShortcutHandlers, UseKeyboardShortcutsOptions } from './useKeyboardShortcuts';

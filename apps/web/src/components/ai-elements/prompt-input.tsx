/**
 * AI Elements - PromptInput component
 * Simplified version based on Vercel AI Elements
 * https://github.com/vercel/ai-elements
 */

import { cn } from "@/lib/utils";
import { SendIcon, PaperclipIcon, Loader2Icon } from "lucide-react";
import type { HTMLAttributes, FormEvent, ChangeEvent, KeyboardEvent } from "react";
import { forwardRef, useRef, useCallback } from "react";

export interface PromptInputProps extends Omit<HTMLAttributes<HTMLFormElement>, 'onChange' | 'onSubmit'> {
  value?: string;
  onChange?: (value: string) => void;
  onSubmit?: (value: string, files?: File[]) => void;
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
  allowAttachments?: boolean;
  maxRows?: number;
}

export const PromptInput = forwardRef<HTMLFormElement, PromptInputProps>(
  (
    {
      className,
      value = "",
      onChange,
      onSubmit,
      placeholder = "Type a message...",
      disabled = false,
      loading = false,
      allowAttachments = false,
      maxRows = 5,
      ...props
    },
    ref
  ) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleSubmit = useCallback(
      (e: FormEvent) => {
        e.preventDefault();
        if (!value.trim() || disabled || loading) return;
        onSubmit?.(value);
      },
      [value, disabled, loading, onSubmit]
    );

    const handleKeyDown = useCallback(
      (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          if (!value.trim() || disabled || loading) return;
          onSubmit?.(value);
        }
      },
      [value, disabled, loading, onSubmit]
    );

    const handleChange = useCallback(
      (e: ChangeEvent<HTMLTextAreaElement>) => {
        onChange?.(e.target.value);
        // Auto-resize textarea
        const textarea = e.target;
        textarea.style.height = "auto";
        const lineHeight = 24;
        const maxHeight = lineHeight * maxRows;
        textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
      },
      [onChange, maxRows]
    );

    const handleFileClick = useCallback(() => {
      fileInputRef.current?.click();
    }, []);

    const handleFileChange = useCallback(
      (e: ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length > 0) {
          onSubmit?.(value, files);
        }
        // Reset input
        e.target.value = "";
      },
      [value, onSubmit]
    );

    return (
      <form
        ref={ref}
        className={cn(
          "flex items-end gap-2 border-t border-border bg-background p-4",
          className
        )}
        onSubmit={handleSubmit}
        {...props}
      >
        {allowAttachments && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
            />
            <button
              type="button"
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                "text-muted-foreground hover:bg-muted hover:text-foreground",
                "transition-colors",
                disabled && "pointer-events-none opacity-50"
              )}
              onClick={handleFileClick}
              disabled={disabled}
            >
              <PaperclipIcon className="h-5 w-5" />
            </button>
          </>
        )}

        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || loading}
            rows={1}
            className={cn(
              "w-full resize-none rounded-lg border border-input bg-background px-4 py-2.5",
              "text-sm placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "min-h-[44px] max-h-[200px]"
            )}
          />
        </div>

        <button
          type="submit"
          disabled={!value.trim() || disabled || loading}
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            "bg-primary text-primary-foreground",
            "hover:bg-primary/90 transition-colors",
            "disabled:pointer-events-none disabled:opacity-50"
          )}
        >
          {loading ? (
            <Loader2Icon className="h-5 w-5 animate-spin" />
          ) : (
            <SendIcon className="h-5 w-5" />
          )}
        </button>
      </form>
    );
  }
);

PromptInput.displayName = "PromptInput";

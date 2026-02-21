/**
 * AI Elements - Message component
 * Simplified version based on Vercel AI Elements
 * https://github.com/vercel/ai-elements
 */

import { cn } from "@/lib/utils";
import type { HTMLAttributes, ReactNode } from "react";

export type MessageRole = "user" | "assistant" | "system" | "agent";

export interface MessageProps extends HTMLAttributes<HTMLDivElement> {
  from: MessageRole;
}

export const Message = ({ className, from, ...props }: MessageProps) => (
  <div
    className={cn(
      "group flex w-full max-w-[95%] flex-col gap-2",
      from === "user" ? "is-user ml-auto items-end" : "is-assistant items-start",
      className
    )}
    data-role={from}
    {...props}
  />
);

export interface MessageContentProps extends HTMLAttributes<HTMLDivElement> {}

export const MessageContent = ({
  children,
  className,
  ...props
}: MessageContentProps) => (
  <div
    className={cn(
      "flex w-fit min-w-0 max-w-full flex-col gap-2 overflow-hidden text-sm",
      "group-[.is-user]:rounded-2xl group-[.is-user]:bg-primary group-[.is-user]:px-4 group-[.is-user]:py-3 group-[.is-user]:text-primary-foreground",
      "group-[.is-assistant]:text-foreground",
      className
    )}
    {...props}
  >
    {children}
  </div>
);

export interface MessageResponseProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export const MessageResponse = ({
  children,
  className,
  ...props
}: MessageResponseProps) => (
  <div
    className={cn(
      "prose prose-sm max-w-none dark:prose-invert",
      "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
      className
    )}
    {...props}
  >
    {typeof children === "string" ? (
      <p className="whitespace-pre-wrap">{children}</p>
    ) : (
      children
    )}
  </div>
);

export interface MessageActionsProps extends HTMLAttributes<HTMLDivElement> {}

export const MessageActions = ({
  className,
  children,
  ...props
}: MessageActionsProps) => (
  <div
    className={cn(
      "flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100",
      className
    )}
    {...props}
  >
    {children}
  </div>
);

export interface MessageActionProps extends HTMLAttributes<HTMLButtonElement> {
  tooltip?: string;
  label?: string;
}

export const MessageAction = ({
  tooltip,
  children,
  label,
  className,
  ...props
}: MessageActionProps) => (
  <button
    className={cn(
      "inline-flex h-8 w-8 items-center justify-center rounded-md",
      "text-muted-foreground hover:bg-muted hover:text-foreground",
      "transition-colors",
      className
    )}
    type="button"
    title={tooltip || label}
    {...props}
  >
    {children}
    {label && <span className="sr-only">{label}</span>}
  </button>
);

export interface MessageToolbarProps extends HTMLAttributes<HTMLDivElement> {}

export const MessageToolbar = ({
  className,
  children,
  ...props
}: MessageToolbarProps) => (
  <div
    className={cn(
      "flex w-full items-center justify-between gap-4",
      className
    )}
    {...props}
  >
    {children}
  </div>
);

export interface MessageAvatarProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  fallback?: ReactNode;
}

export const MessageAvatar = ({
  className,
  src,
  fallback = "?",
  ...props
}: MessageAvatarProps) => (
  <div
    className={cn(
      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
      "bg-muted text-muted-foreground text-xs font-medium",
      "overflow-hidden",
      className
    )}
    {...props}
  >
    {src ? (
      <img src={src} alt="" className="h-full w-full object-cover" />
    ) : (
      fallback
    )}
  </div>
);

export interface MessageTimestampProps extends HTMLAttributes<HTMLSpanElement> {
  date?: Date | string;
}

export const MessageTimestamp = ({
  className,
  date,
  children,
  ...props
}: MessageTimestampProps) => {
  const formattedDate = date
    ? new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : children;

  return (
    <span
      className={cn("text-xs text-muted-foreground", className)}
      {...props}
    >
      {formattedDate}
    </span>
  );
};

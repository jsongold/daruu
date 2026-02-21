/**
 * AI Elements - Conversation component
 * Simplified version based on Vercel AI Elements
 * https://github.com/vercel/ai-elements
 */

import { cn } from "@/lib/utils";
import { ArrowDownIcon } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";
import { createContext, useContext, useRef, useEffect, useState, useCallback } from "react";

// Context for scroll management
interface ConversationContextType {
  isAtBottom: boolean;
  scrollToBottom: () => void;
}

const ConversationContext = createContext<ConversationContextType | null>(null);

export const useConversationContext = () => {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error("Conversation components must be used within Conversation");
  }
  return context;
};

export interface ConversationProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export const Conversation = ({ className, children, ...props }: ConversationProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, []);

  const handleScroll = useCallback(() => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      setIsAtBottom(scrollHeight - scrollTop - clientHeight < 50);
    }
  }, []);

  // Auto-scroll when new content is added if already at bottom
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new MutationObserver(() => {
      if (isAtBottom) {
        scrollToBottom();
      }
    });

    observer.observe(container, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [isAtBottom, scrollToBottom]);

  return (
    <ConversationContext.Provider value={{ isAtBottom, scrollToBottom }}>
      <div
        ref={containerRef}
        className={cn("relative flex-1 overflow-y-auto", className)}
        onScroll={handleScroll}
        role="log"
        {...props}
      >
        {children}
      </div>
    </ConversationContext.Provider>
  );
};

export interface ConversationContentProps extends HTMLAttributes<HTMLDivElement> {}

export const ConversationContent = ({
  className,
  ...props
}: ConversationContentProps) => (
  <div className={cn("flex flex-col gap-6 p-4", className)} {...props} />
);

export interface ConversationEmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  icon?: ReactNode;
}

export const ConversationEmptyState = ({
  className,
  title = "No messages yet",
  description = "Start a conversation to see messages here",
  icon,
  children,
  ...props
}: ConversationEmptyStateProps) => (
  <div
    className={cn(
      "flex size-full flex-col items-center justify-center gap-3 p-8 text-center",
      className
    )}
    {...props}
  >
    {children ?? (
      <>
        {icon && <div className="text-muted-foreground">{icon}</div>}
        <div className="space-y-1">
          <h3 className="font-medium text-sm">{title}</h3>
          {description && (
            <p className="text-muted-foreground text-sm">{description}</p>
          )}
        </div>
      </>
    )}
  </div>
);

export interface ConversationScrollButtonProps extends HTMLAttributes<HTMLButtonElement> {}

export const ConversationScrollButton = ({
  className,
  ...props
}: ConversationScrollButtonProps) => {
  const { isAtBottom, scrollToBottom } = useConversationContext();

  if (isAtBottom) return null;

  return (
    <button
      className={cn(
        "absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full p-2",
        "bg-background border border-border shadow-md",
        "hover:bg-muted transition-colors",
        className
      )}
      onClick={scrollToBottom}
      type="button"
      {...props}
    >
      <ArrowDownIcon className="h-4 w-4" />
    </button>
  );
};

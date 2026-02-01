/**
 * Custom hook for template state management.
 * Handles template matching, selection, and caching.
 */

import { useState, useCallback, useRef } from 'react';
import type { Template, TemplateMatch } from '../api/templateClient';
import {
  listTemplates,
  matchTemplates,
  getTemplate,
} from '../api/templateClient';
import { ApiError } from '../api/client';

export interface UseTemplatesOptions {
  /** Whether to auto-load templates on mount */
  autoLoadList?: boolean;
}

export interface UseTemplatesReturn {
  // Template list
  templates: Template[];
  isLoadingTemplates: boolean;
  refreshTemplates: () => Promise<void>;

  // Template matching
  matches: TemplateMatch[];
  isMatching: boolean;
  matchForPage: (pageImage: Blob) => Promise<TemplateMatch[]>;
  clearMatches: () => void;

  // Selected template
  selectedTemplate: Template | null;
  selectedTemplateId: string | null;
  isLoadingSelected: boolean;
  selectTemplate: (id: string) => Promise<void>;
  skipTemplateMatching: () => void;
  clearSelection: () => void;

  // State
  hasSkippedMatching: boolean;
  error: string | null;
  clearError: () => void;
}

export function useTemplates(
  options: UseTemplatesOptions = {}
): UseTemplatesReturn {
  const { autoLoadList = false } = options;

  // Template list state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

  // Matching state
  const [matches, setMatches] = useState<TemplateMatch[]>([]);
  const [isMatching, setIsMatching] = useState(false);

  // Selected template state
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [isLoadingSelected, setIsLoadingSelected] = useState(false);

  // Skip state
  const [hasSkippedMatching, setHasSkippedMatching] = useState(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Cache for matched templates
  const templateCacheRef = useRef<Map<string, Template>>(new Map());

  // Track if initial load has been done
  const hasLoadedRef = useRef(false);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Load template list
  const refreshTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    setError(null);

    try {
      const templateList = await listTemplates();
      setTemplates(templateList);

      // Update cache
      templateList.forEach((template) => {
        templateCacheRef.current.set(template.id, template);
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load templates';
      setError(message);
    } finally {
      setIsLoadingTemplates(false);
    }
  }, []);

  // Match templates for a page image
  const matchForPage = useCallback(async (pageImage: Blob): Promise<TemplateMatch[]> => {
    setIsMatching(true);
    setError(null);
    setHasSkippedMatching(false);

    try {
      const matchResults = await matchTemplates(pageImage);
      setMatches(matchResults);
      return matchResults;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to match templates';
      setError(message);
      setMatches([]);
      return [];
    } finally {
      setIsMatching(false);
    }
  }, []);

  // Clear matches
  const clearMatches = useCallback(() => {
    setMatches([]);
    setHasSkippedMatching(false);
  }, []);

  // Select a template
  const selectTemplate = useCallback(async (id: string) => {
    setSelectedTemplateId(id);
    setIsLoadingSelected(true);
    setError(null);
    setHasSkippedMatching(false);

    try {
      // Check cache first
      let template = templateCacheRef.current.get(id);

      if (!template) {
        template = await getTemplate(id);
        templateCacheRef.current.set(id, template);
      }

      setSelectedTemplate(template);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load template';
      setError(message);
      setSelectedTemplate(null);
      setSelectedTemplateId(null);
    } finally {
      setIsLoadingSelected(false);
    }
  }, []);

  // Skip template matching (fresh analysis)
  const skipTemplateMatching = useCallback(() => {
    setHasSkippedMatching(true);
    setSelectedTemplate(null);
    setSelectedTemplateId(null);
    setMatches([]);
  }, []);

  // Clear selection
  const clearSelection = useCallback(() => {
    setSelectedTemplate(null);
    setSelectedTemplateId(null);
    setHasSkippedMatching(false);
  }, []);

  // Auto-load templates if enabled
  if (autoLoadList && !hasLoadedRef.current) {
    hasLoadedRef.current = true;
    refreshTemplates();
  }

  return {
    // Template list
    templates,
    isLoadingTemplates,
    refreshTemplates,

    // Template matching
    matches,
    isMatching,
    matchForPage,
    clearMatches,

    // Selected template
    selectedTemplate,
    selectedTemplateId,
    isLoadingSelected,
    selectTemplate,
    skipTemplateMatching,
    clearSelection,

    // State
    hasSkippedMatching,
    error,
    clearError,
  };
}

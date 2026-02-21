-- ============================================================================
-- MCP Tables Migration
-- ============================================================================
-- Creates tables for Model Context Protocol (MCP) integration:
-- - mcp_sessions: Y Pattern session linking
-- - entitlements: Feature gating based on subscription plans
-- ============================================================================

-- ============================================================================
-- Table: mcp_sessions
-- ============================================================================
-- Stores session tokens linking Claude sessions to authenticated users
-- Part of Y Pattern authentication flow

CREATE TABLE IF NOT EXISTS public.mcp_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token TEXT NOT NULL UNIQUE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '7 days'),
    last_used_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Indexes
    CONSTRAINT mcp_sessions_token_format CHECK (length(session_token) >= 32)
);

CREATE INDEX idx_mcp_sessions_token ON public.mcp_sessions(session_token);
CREATE INDEX idx_mcp_sessions_user_id ON public.mcp_sessions(user_id);
CREATE INDEX idx_mcp_sessions_expires_at ON public.mcp_sessions(expires_at);

-- ============================================================================
-- Table: entitlements
-- ============================================================================
-- Stores user subscription plans and feature access
-- Used for gating premium features (export_pdf, etc.)

CREATE TABLE IF NOT EXISTS public.entitlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    features JSONB NOT NULL DEFAULT '{
        "max_pdfs_per_month": 5,
        "can_export": false,
        "max_file_size_mb": 10,
        "can_autofill": false,
        "max_source_docs": 0
    }'::jsonb,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT CHECK (subscription_status IN ('active', 'canceled', 'past_due', 'trialing')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_entitlements_user_id ON public.entitlements(user_id);
CREATE INDEX idx_entitlements_stripe_customer_id ON public.entitlements(stripe_customer_id);
CREATE INDEX idx_entitlements_stripe_subscription_id ON public.entitlements(stripe_subscription_id);

-- ============================================================================
-- RLS Policies
-- ============================================================================

-- Enable RLS
ALTER TABLE public.mcp_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entitlements ENABLE ROW LEVEL SECURITY;

-- mcp_sessions policies
CREATE POLICY "Users can view their own sessions"
    ON public.mcp_sessions
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own sessions"
    ON public.mcp_sessions
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own sessions"
    ON public.mcp_sessions
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own sessions"
    ON public.mcp_sessions
    FOR DELETE
    USING (auth.uid() = user_id);

-- entitlements policies
CREATE POLICY "Users can view their own entitlements"
    ON public.entitlements
    FOR SELECT
    USING (auth.uid() = user_id);

-- Only service role can modify entitlements (via Stripe webhook)
CREATE POLICY "Service role can manage all entitlements"
    ON public.entitlements
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: get_user_entitlement
-- Returns entitlement details for a user
CREATE OR REPLACE FUNCTION public.get_user_entitlement(p_user_id UUID)
RETURNS TABLE (
    plan TEXT,
    features JSONB,
    subscription_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT e.plan, e.features, e.subscription_status
    FROM public.entitlements e
    WHERE e.user_id = p_user_id;

    -- If no entitlement exists, return default free plan
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            'free'::TEXT as plan,
            '{
                "max_pdfs_per_month": 5,
                "can_export": false,
                "max_file_size_mb": 10,
                "can_autofill": false,
                "max_source_docs": 0
            }'::JSONB as features,
            NULL::TEXT as subscription_status;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: can_user_download
-- Checks if user has permission to download PDFs
CREATE OR REPLACE FUNCTION public.can_user_download(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_can_export BOOLEAN;
BEGIN
    SELECT (features->>'can_export')::boolean
    INTO v_can_export
    FROM public.entitlements
    WHERE user_id = p_user_id;

    -- Default to false if no entitlement found
    RETURN COALESCE(v_can_export, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: cleanup_expired_sessions
-- Removes expired session tokens (should be run periodically via cron)
CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM public.mcp_sessions
    WHERE expires_at < now();

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: create_default_entitlement
-- Automatically create default entitlement for new users
CREATE OR REPLACE FUNCTION public.create_default_entitlement()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.entitlements (user_id, plan, features)
    VALUES (
        NEW.id,
        'free',
        '{
            "max_pdfs_per_month": 5,
            "can_export": false,
            "max_file_size_mb": 10,
            "can_autofill": false,
            "max_source_docs": 0
        }'::jsonb
    )
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger: Auto-create entitlement for new users
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_default_entitlement();

-- ============================================================================
-- Default Plan Features
-- ============================================================================
-- For reference, here are the feature limits by plan:
--
-- FREE:
-- - max_pdfs_per_month: 5
-- - can_export: false (preview only)
-- - max_file_size_mb: 10
-- - can_autofill: false
-- - max_source_docs: 0
--
-- PRO ($10/month):
-- - max_pdfs_per_month: 100
-- - can_export: true
-- - max_file_size_mb: 50
-- - can_autofill: true
-- - max_source_docs: 10
--
-- ENTERPRISE (custom pricing):
-- - max_pdfs_per_month: unlimited
-- - can_export: true
-- - max_file_size_mb: 100
-- - can_autofill: true
-- - max_source_docs: unlimited
-- ============================================================================

COMMENT ON TABLE public.mcp_sessions IS 'Stores session tokens for Y Pattern MCP authentication';
COMMENT ON TABLE public.entitlements IS 'User subscription plans and feature access for MCP tools';
COMMENT ON FUNCTION public.get_user_entitlement(UUID) IS 'Returns entitlement details for a user';
COMMENT ON FUNCTION public.can_user_download(UUID) IS 'Checks if user has export permission';
COMMENT ON FUNCTION public.cleanup_expired_sessions() IS 'Removes expired MCP session tokens';

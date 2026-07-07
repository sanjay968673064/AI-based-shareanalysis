CREATE TABLE IF NOT EXISTS recommendation_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  confidence_score NUMERIC(6, 2) NOT NULL,
  risk_score NUMERIC(6, 2) NOT NULL,
  price_at_recommendation NUMERIC(18, 4) NOT NULL,
  target_allocation NUMERIC(6, 2) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendation_history_tenant_user_idx
  ON recommendation_history(tenant_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS recommendation_history_symbol_idx
  ON recommendation_history(symbol, created_at DESC);

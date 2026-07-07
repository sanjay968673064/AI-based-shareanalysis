CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT 'starter',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app_users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  external_auth_id TEXT NOT NULL UNIQUE,
  email TEXT,
  full_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE broker_connections (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  broker TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'disconnected',
  access_token_ciphertext TEXT,
  refresh_token_ciphertext TEXT,
  scopes TEXT[] NOT NULL DEFAULT ARRAY['read:portfolio', 'read:orders', 'read:positions', 'read:quotes'],
  last_synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT broker_connections_read_only CHECK (NOT ('trade:execute' = ANY(scopes)))
);

CREATE TABLE holdings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  broker_connection_id UUID REFERENCES broker_connections(id) ON DELETE SET NULL,
  symbol TEXT NOT NULL,
  exchange TEXT NOT NULL DEFAULT 'NSE',
  company_name TEXT NOT NULL,
  sector TEXT,
  asset_class TEXT NOT NULL DEFAULT 'equity',
  quantity NUMERIC(18, 4) NOT NULL,
  average_price NUMERIC(18, 4) NOT NULL,
  last_price NUMERIC(18, 4) NOT NULL,
  day_pnl NUMERIC(18, 4) NOT NULL DEFAULT 0,
  total_pnl NUMERIC(18, 4) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX holdings_tenant_user_idx ON holdings(tenant_id, user_id);
CREATE INDEX holdings_symbol_idx ON holdings(symbol);

CREATE TABLE portfolio_reports (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  report_type TEXT NOT NULL,
  health_score INTEGER NOT NULL CHECK (health_score BETWEEN 0 AND 100),
  summary TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  symbol TEXT,
  threshold NUMERIC(18, 4),
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
  user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tenants (id, name, plan)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Tenant', 'pro')
ON CONFLICT DO NOTHING;

INSERT INTO app_users (id, tenant_id, external_auth_id, email, full_name)
VALUES (
  '00000000-0000-0000-0000-000000000101',
  '00000000-0000-0000-0000-000000000001',
  'demo-user',
  'demo@example.com',
  'Demo Investor'
)
ON CONFLICT DO NOTHING;

INSERT INTO broker_connections (tenant_id, user_id, broker, status, scopes)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000101',
  'zerodha',
  'sandbox',
  ARRAY['read:portfolio', 'read:orders', 'read:positions', 'read:quotes']
);

INSERT INTO holdings (
  tenant_id, user_id, symbol, company_name, sector, quantity, average_price, last_price, day_pnl, total_pnl
) VALUES
  ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'INFY', 'Infosys Ltd', 'Information Technology', 24, 1410.25, 1516.75, -248.50, 2556.00),
  ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'HDFCBANK', 'HDFC Bank Ltd', 'Financial Services', 18, 1562.10, 1698.30, 312.20, 2451.60),
  ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'TATAMOTORS', 'Tata Motors Ltd', 'Consumer Cyclical', 40, 685.80, 804.15, 420.00, 4734.00),
  ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'RELIANCE', 'Reliance Industries Ltd', 'Energy', 12, 2445.00, 2862.40, 188.30, 5008.80);

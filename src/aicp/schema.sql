-- AI reliability control plane. Own database. Not the workflow-engine schema.

CREATE TABLE IF NOT EXISTS aicp_prompt_versions (
  id            uuid PRIMARY KEY,
  feature       text NOT NULL,
  version       int  NOT NULL,
  body          text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (feature, version)
);

CREATE TABLE IF NOT EXISTS aicp_features (
  name                 text PRIMARY KEY,
  active_version_id    uuid REFERENCES aicp_prompt_versions (id),
  model                text NOT NULL,
  fallback_model       text,
  max_tokens           int NOT NULL DEFAULT 256,
  timeout_ms           int NOT NULL DEFAULT 5000,
  killed               boolean NOT NULL DEFAULT false,
  fail_closed          boolean NOT NULL DEFAULT true,
  budget_requests      int NOT NULL DEFAULT 100,
  budget_usd           numeric(12, 6) NOT NULL DEFAULT 10,
  window_seconds       int NOT NULL DEFAULT 3600,
  store_payloads       boolean NOT NULL DEFAULT false,
  updated_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aicp_budgets (
  tenant        text NOT NULL,
  feature       text NOT NULL,
  window_start  timestamptz NOT NULL,
  request_count int NOT NULL DEFAULT 0,
  spent_usd     numeric(14, 6) NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant, feature, window_start)
);

CREATE TABLE IF NOT EXISTS aicp_traces (
  id                 uuid PRIMARY KEY,
  tenant             text NOT NULL,
  feature            text NOT NULL,
  prompt_version_id  uuid,
  prompt_version     int,
  model              text NOT NULL,
  input_hash         text NOT NULL,
  input_preview      text NOT NULL,
  output_preview     text,
  status             text NOT NULL,
  error_class        text,
  latency_ms         double precision NOT NULL,
  overhead_ms        double precision NOT NULL,
  provider_ms        double precision NOT NULL,
  tokens_in          int NOT NULL DEFAULT 0,
  tokens_out         int NOT NULL DEFAULT 0,
  cost_usd           numeric(14, 6) NOT NULL DEFAULT 0,
  retried            boolean NOT NULL DEFAULT false,
  used_fallback      boolean NOT NULL DEFAULT false,
  unmetered          boolean NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aicp_eval_cases (
  id          uuid PRIMARY KEY,
  feature     text NOT NULL,
  input       jsonb NOT NULL,
  checker     text NOT NULL,
  expected    jsonb NOT NULL,
  note        text
);

CREATE TABLE IF NOT EXISTS aicp_eval_runs (
  id            uuid PRIMARY KEY,
  feature       text NOT NULL,
  version_id    uuid NOT NULL,
  version       int NOT NULL,
  passed        int NOT NULL,
  total         int NOT NULL,
  pass_rate     double precision NOT NULL,
  blocked       boolean NOT NULL,
  details       jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aicp_promote_events (
  id            uuid PRIMARY KEY,
  feature       text NOT NULL,
  from_version  int,
  to_version    int NOT NULL,
  eval_run_id   uuid,
  accepted      boolean NOT NULL,
  reason        text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS aicp_traces_feature_time
  ON aicp_traces (feature, created_at DESC);
CREATE INDEX IF NOT EXISTS aicp_traces_tenant
  ON aicp_traces (tenant, created_at DESC);
CREATE INDEX IF NOT EXISTS aicp_traces_id_created
  ON aicp_traces (created_at DESC);

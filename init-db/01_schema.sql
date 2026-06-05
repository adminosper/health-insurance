-- =============================================================================
-- 01_schema.sql
-- Creates all database tables, enums, and constraints for the
-- Health Insurance Claims Processing System.
-- Executed automatically by PostgreSQL on container initialization.
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUM TYPES
-- Single source of truth for all valid categorical values.
-- =============================================================================

CREATE TYPE service_category AS ENUM (
    'ROOM_RENT', 'ICU_CHARGES', 'CONSULTATION', 'OT_CHARGES', 'PHARMACY',
    'DIAGNOSTICS', 'DENTAL', 'AYUSH', 'CONSUMABLES', 'COSMETIC',
    'COSMETIC_SURGERY', 'SURGERY', 'OTHER'
);

CREATE TYPE claim_type AS ENUM (
    'REIMBURSEMENT', 'CASHLESS'
);

CREATE TYPE claim_status AS ENUM (
    'SUBMITTED', 'VALIDATED', 'QUERY_RAISED', 'UNDER_REVIEW', 'ADJUDICATED',
    'PENDING_APPROVAL', 'APPROVED', 'PARTIALLY_APPROVED', 'DENIED', 'PAID'
);

CREATE TYPE manual_approval_status AS ENUM (
    'PENDING', 'APPROVED', 'OVERRIDDEN', 'REJECTED'
);

CREATE TYPE line_item_status AS ENUM (
    'APPROVED', 'DENIED', 'PARTIALLY_APPROVED', 'EXCLUDED'
);

CREATE TYPE execution_phase AS ENUM (
    'EXCLUSION', 'CAPPING', 'COVERAGE', 'COST_SHARING'
);

CREATE TYPE action_type AS ENUM (
    'EXCLUDE', 'LIMIT', 'COPAY', 'DEDUCTIBLE'
);

CREATE TYPE gender AS ENUM (
    'MALE', 'FEMALE', 'OTHER'
);

-- =============================================================================
-- CORE ENTITIES
-- =============================================================================

-- Plans: The insurance product blueprint
CREATE TABLE plans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    allowed_sum_insured_options JSONB NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Policies: A purchased contract tied to a plan
CREATE TABLE policies (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id                 UUID NOT NULL REFERENCES plans(id),
    chosen_sum_insured      DECIMAL(15, 2) NOT NULL,
    tenure_start            DATE NOT NULL,
    tenure_end              DATE NOT NULL,
    policyholder_name       VARCHAR(255) NOT NULL,
    policyholder_contact    JSONB,
    policyholder_kyc        JSONB,
    bank_account_details    JSONB,
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Members: Individuals covered under a policy
CREATE TABLE members (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id       UUID NOT NULL REFERENCES policies(id),
    full_name       VARCHAR(255) NOT NULL,
    date_of_birth   DATE NOT NULL,
    gender          gender NOT NULL,
    relationship    VARCHAR(50) NOT NULL,
    ped_list        JSONB NOT NULL DEFAULT '[]'
);

-- Accumulators: Dynamic financial state per policy
CREATE TABLE accumulators (
    policy_id               UUID PRIMARY KEY REFERENCES policies(id),
    available_sum_insured   DECIMAL(15, 2) NOT NULL,
    accumulated_ncb         DECIMAL(15, 2) NOT NULL DEFAULT 0,
    active_deductible_paid  DECIMAL(15, 2) NOT NULL DEFAULT 0,
    category_usage          JSONB NOT NULL DEFAULT '{}'
);

-- =============================================================================
-- RULE ENGINE CONFIGURATIONS
-- =============================================================================

-- Rules: Individual adjudication rules tied to a plan
CREATE TABLE rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id         UUID NOT NULL REFERENCES plans(id),
    name            VARCHAR(255) NOT NULL,
    execution_phase execution_phase NOT NULL,
    priority        INTEGER NOT NULL,
    condition       JSONB NOT NULL,
    action_type     action_type NOT NULL,
    action_config   JSONB NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Index for fast rule lookup during adjudication
CREATE INDEX idx_rules_plan_phase_priority ON rules (plan_id, execution_phase, priority);

-- =============================================================================
-- CLAIM TRANSACTIONS
-- =============================================================================

-- Claims: A submitted reimbursement/cashless request
CREATE TABLE claims (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id               UUID NOT NULL REFERENCES policies(id),
    member_id               UUID NOT NULL REFERENCES members(id),
    diagnosis_codes         JSONB NOT NULL,
    claim_type              claim_type NOT NULL,
    is_accident             BOOLEAN NOT NULL DEFAULT FALSE,
    admission_date          DATE NOT NULL,
    discharge_date          DATE NOT NULL,
    status                  claim_status NOT NULL DEFAULT 'SUBMITTED',
    manual_approval_status  manual_approval_status NOT NULL DEFAULT 'PENDING',
    total_billed            DECIMAL(15, 2) NOT NULL DEFAULT 0,
    total_insurer_payable   DECIMAL(15, 2) NOT NULL DEFAULT 0,
    total_member_payable    DECIMAL(15, 2) NOT NULL DEFAULT 0,
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Line Items: Individual billing entries within a claim
CREATE TABLE line_items (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_id          UUID NOT NULL REFERENCES claims(id),
    service_category  service_category NOT NULL,
    billed_amount     DECIMAL(15, 2) NOT NULL,
    allowed_amount    DECIMAL(15, 2) NOT NULL DEFAULT 0,
    insurer_payable   DECIMAL(15, 2) NOT NULL DEFAULT 0,
    status            line_item_status NOT NULL DEFAULT 'APPROVED',
    audit_trail       JSONB NOT NULL DEFAULT '[]'
);

-- Index for fast line item lookup by claim
CREATE INDEX idx_line_items_claim_id ON line_items (claim_id);

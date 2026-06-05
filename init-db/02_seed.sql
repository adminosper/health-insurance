-- =============================================================================
-- 02_seed.sql
-- Seeds realistic test data for reviewer testing.
-- Executed automatically by PostgreSQL after 01_schema.sql.
-- =============================================================================

-- =============================================================================
-- PLANS
-- =============================================================================

INSERT INTO plans (id, name, description, allowed_sum_insured_options) VALUES
(
    'a1b2c3d4-0001-4000-8000-000000000001',
    'General Health Plan',
    'Comprehensive health plan covering hospitalization, dental, AYUSH, and more for individuals and families.',
    '[500000, 1000000, 2500000]'
),
(
    'a1b2c3d4-0002-4000-8000-000000000002',
    'Heart Disease Critical Care Plan',
    'Specialized plan focused on cardiac conditions with higher surgery sublimits and no cardiac-specific waiting period.',
    '[1000000, 2000000]'
);

-- =============================================================================
-- RULES: General Health Plan
-- =============================================================================

-- EXCLUSION Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0001-4000-8000-000000000001',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Initial Waiting Period 30 Days',
    'EXCLUSION', 1,
    '{"all": [{"field": "member.days_active", "operator": "LT", "value": 30}, {"field": "claim.is_accident", "operator": "EQ", "value": false}]}',
    'EXCLUDE',
    '{"reason_code": "INITIAL_WAITING", "explanation": "Claim within 30-day initial waiting period"}'
),
(
    'b1b2c3d4-0001-4000-8000-000000000002',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Cosmetic Surgery Exclusion',
    'EXCLUSION', 2,
    '{"field": "line_item.service_category", "operator": "IN", "value": ["COSMETIC", "COSMETIC_SURGERY"]}',
    'EXCLUDE',
    '{"reason_code": "PERMANENT_EXCLUSION", "explanation": "Cosmetic procedures are permanently excluded"}'
);

-- CAPPING Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0001-4000-8000-000000000003',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Room Rent Cap - 5L SI',
    'CAPPING', 1,
    '{"all": [{"field": "line_item.service_category", "operator": "EQ", "value": "ROOM_RENT"}, {"field": "policy.chosen_sum_insured", "operator": "EQ", "value": 500000}]}',
    'LIMIT',
    '{"max_amount": 5000, "period": "PER_DAY", "reason_code": "ROOM_RENT_CAP", "explanation": "Room rent capped at Rs.5,000/day for 5L SI"}'
),
(
    'b1b2c3d4-0001-4000-8000-000000000004',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Room Rent Cap - 10L+ SI',
    'CAPPING', 2,
    '{"all": [{"field": "line_item.service_category", "operator": "EQ", "value": "ROOM_RENT"}, {"field": "policy.chosen_sum_insured", "operator": "GTE", "value": 1000000}]}',
    'LIMIT',
    '{"max_amount": 10000, "period": "PER_DAY", "reason_code": "ROOM_RENT_CAP", "explanation": "Room rent capped at Rs.10,000/day for 10L+ SI"}'
),
(
    'b1b2c3d4-0001-4000-8000-000000000005',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Dental Sublimit',
    'CAPPING', 3,
    '{"field": "line_item.service_category", "operator": "EQ", "value": "DENTAL"}',
    'LIMIT',
    '{"max_amount": 50000, "period": "PER_POLICY_YEAR", "accumulator_key": "DENTAL", "reason_code": "DENTAL_SUBLIMIT", "explanation": "Dental treatment capped at Rs.50,000 per policy year"}'
),
(
    'b1b2c3d4-0001-4000-8000-000000000006',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'AYUSH Limit',
    'CAPPING', 4,
    '{"field": "line_item.service_category", "operator": "EQ", "value": "AYUSH"}',
    'LIMIT',
    '{"max_amount": 50000, "period": "PER_POLICY_YEAR", "accumulator_key": "AYUSH", "reason_code": "AYUSH_SUBLIMIT", "explanation": "AYUSH treatment capped at Rs.50,000 per policy year"}'
);

-- COST_SHARING Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0001-4000-8000-000000000007',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'Standard Copay 10%',
    'COST_SHARING', 1,
    '{"field": "line_item.service_category", "operator": "NEQ", "value": null}',
    'COPAY',
    '{"percentage": 10, "reason_code": "MEMBER_COPAY", "explanation": "10% copay applied on allowed amount"}'
);

-- =============================================================================
-- RULES: Heart Disease Critical Care Plan
-- =============================================================================

-- EXCLUSION Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0002-4000-8000-000000000001',
    'a1b2c3d4-0002-4000-8000-000000000002',
    'Initial Waiting Period 30 Days',
    'EXCLUSION', 1,
    '{"all": [{"field": "member.days_active", "operator": "LT", "value": 30}, {"field": "claim.is_accident", "operator": "EQ", "value": false}]}',
    'EXCLUDE',
    '{"reason_code": "INITIAL_WAITING", "explanation": "Claim within 30-day initial waiting period"}'
);

-- CAPPING Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0002-4000-8000-000000000002',
    'a1b2c3d4-0002-4000-8000-000000000002',
    'Room Rent Cap',
    'CAPPING', 1,
    '{"field": "line_item.service_category", "operator": "EQ", "value": "ROOM_RENT"}',
    'LIMIT',
    '{"max_amount": 8000, "period": "PER_DAY", "reason_code": "ROOM_RENT_CAP", "explanation": "Room rent capped at Rs.8,000/day"}'
),
(
    'b1b2c3d4-0002-4000-8000-000000000003',
    'a1b2c3d4-0002-4000-8000-000000000002',
    'Cardiac Surgery Sublimit',
    'CAPPING', 2,
    '{"all": [{"field": "line_item.service_category", "operator": "EQ", "value": "SURGERY"}, {"field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["I21", "I25", "I42", "I50"]}]}',
    'LIMIT',
    '{"max_amount": 500000, "period": "PER_POLICY_YEAR", "accumulator_key": "CARDIAC_SURGERY", "reason_code": "CARDIAC_SUBLIMIT", "explanation": "Cardiac surgery capped at Rs.5,00,000 per policy year"}'
);

-- COST_SHARING Phase
INSERT INTO rules (id, plan_id, name, execution_phase, priority, condition, action_type, action_config) VALUES
(
    'b1b2c3d4-0002-4000-8000-000000000004',
    'a1b2c3d4-0002-4000-8000-000000000002',
    'Non-Cardiac Copay 20%',
    'COST_SHARING', 1,
    '{"not": {"field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["I21", "I25", "I42", "I50"]}}',
    'COPAY',
    '{"percentage": 20, "reason_code": "NON_CARDIAC_COPAY", "explanation": "20% copay for non-cardiac treatments"}'
);

-- =============================================================================
-- POLICIES
-- 2 per plan, one per SI tier to enable testing different rule conditions
-- =============================================================================

-- General Health Plan: Policy with 5L SI
INSERT INTO policies (id, plan_id, chosen_sum_insured, tenure_start, tenure_end, policyholder_name, policyholder_contact, policyholder_kyc, bank_account_details) VALUES
(
    'c1b2c3d4-0001-4000-8000-000000000001',
    'a1b2c3d4-0001-4000-8000-000000000001',
    500000.00,
    '2025-01-01', '2026-01-01',
    'Rajesh Kumar',
    '{"mobile": "+919876543210", "email": "rajesh.kumar@example.com"}',
    '{"pan": "ABCDE1234F", "aadhaar": "1234-5678-9012"}',
    '{"account_holder": "Rajesh Kumar", "bank_name": "ICICI Bank", "account_number": "1234567890", "ifsc_code": "ICIC0001234"}'
),
-- General Health Plan: Policy with 10L SI
(
    'c1b2c3d4-0001-4000-8000-000000000002',
    'a1b2c3d4-0001-4000-8000-000000000001',
    1000000.00,
    '2025-06-01', '2026-06-01',
    'Priya Sharma',
    '{"mobile": "+919876543211", "email": "priya.sharma@example.com"}',
    '{"pan": "FGHIJ5678K", "aadhaar": "2345-6789-0123"}',
    '{"account_holder": "Priya Sharma", "bank_name": "HDFC Bank", "account_number": "0987654321", "ifsc_code": "HDFC0005678"}'
),
-- Heart Disease Plan: Policy with 10L SI
(
    'c1b2c3d4-0002-4000-8000-000000000001',
    'a1b2c3d4-0002-4000-8000-000000000002',
    1000000.00,
    '2025-03-01', '2026-03-01',
    'Amit Patel',
    '{"mobile": "+919876543212", "email": "amit.patel@example.com"}',
    '{"pan": "KLMNO9012L", "aadhaar": "3456-7890-1234"}',
    '{"account_holder": "Amit Patel", "bank_name": "SBI", "account_number": "1122334455", "ifsc_code": "SBIN0009876"}'
),
-- Heart Disease Plan: Policy with 20L SI
(
    'c1b2c3d4-0002-4000-8000-000000000002',
    'a1b2c3d4-0002-4000-8000-000000000002',
    2000000.00,
    '2025-04-15', '2026-04-15',
    'Sunita Reddy',
    '{"mobile": "+919876543213", "email": "sunita.reddy@example.com"}',
    '{"pan": "PQRST3456M", "aadhaar": "4567-8901-2345"}',
    '{"account_holder": "Sunita Reddy", "bank_name": "Axis Bank", "account_number": "5566778899", "ifsc_code": "UTIB0004567"}'
);

-- =============================================================================
-- MEMBERS
-- Varying ages, genders, relationships, and PED lists for testing edge cases
-- =============================================================================

INSERT INTO members (id, policy_id, full_name, date_of_birth, gender, relationship, ped_list) VALUES
-- Rajesh's policy (5L SI): Self + Spouse
(
    'd1b2c3d4-0001-4000-8000-000000000001',
    'c1b2c3d4-0001-4000-8000-000000000001',
    'Rajesh Kumar', '1985-03-15', 'MALE', 'SELF', '[]'
),
(
    'd1b2c3d4-0001-4000-8000-000000000002',
    'c1b2c3d4-0001-4000-8000-000000000001',
    'Anita Kumar', '1988-07-22', 'FEMALE', 'SPOUSE', '["E11.9"]'
),
-- Priya's policy (10L SI): Self only
(
    'd1b2c3d4-0002-4000-8000-000000000001',
    'c1b2c3d4-0001-4000-8000-000000000002',
    'Priya Sharma', '1975-11-30', 'FEMALE', 'SELF', '["I10", "E78.0"]'
),
-- Amit's policy (Heart, 10L SI): Self + Parent (senior citizen)
(
    'd1b2c3d4-0003-4000-8000-000000000001',
    'c1b2c3d4-0002-4000-8000-000000000001',
    'Amit Patel', '1990-01-10', 'MALE', 'SELF', '[]'
),
(
    'd1b2c3d4-0003-4000-8000-000000000002',
    'c1b2c3d4-0002-4000-8000-000000000001',
    'Ramesh Patel', '1958-05-20', 'MALE', 'PARENT', '["I25", "I10"]'
),
-- Sunita's policy (Heart, 20L SI): Self only
(
    'd1b2c3d4-0004-4000-8000-000000000001',
    'c1b2c3d4-0002-4000-8000-000000000002',
    'Sunita Reddy', '1982-09-08', 'FEMALE', 'SELF', '["I42"]'
);

-- =============================================================================
-- ACCUMULATORS
-- Initial balances = chosen_sum_insured; zero usage at policy start
-- =============================================================================

INSERT INTO accumulators (policy_id, available_sum_insured, accumulated_ncb, active_deductible_paid, category_usage) VALUES
(
    'c1b2c3d4-0001-4000-8000-000000000001',
    500000.00, 0, 0,
    '{"DENTAL": 0, "AYUSH": 0}'
),
(
    'c1b2c3d4-0001-4000-8000-000000000002',
    1000000.00, 0, 0,
    '{"DENTAL": 0, "AYUSH": 0}'
),
(
    'c1b2c3d4-0002-4000-8000-000000000001',
    1000000.00, 0, 0,
    '{"CARDIAC_SURGERY": 0}'
),
(
    'c1b2c3d4-0002-4000-8000-000000000002',
    2000000.00, 0, 0,
    '{"CARDIAC_SURGERY": 0}'
);

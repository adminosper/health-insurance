# Domain Model & Architecture

This document describes the core entities, their relationships, the claim state machine, and the exact data structure we used to model complex medical coverage rules.

## Core Entities & Relationships

The system is built on a standard hierarchical insurance model, mapping the product (Plan) down to the specific medical event (Claim).

```mermaid
erDiagram
    PLAN ||--o{ POLICY : "defines"
    PLAN ||--o{ RULE : "contains"
    POLICY ||--|{ MEMBER : "covers"
    POLICY ||--|| ACCUMULATOR : "has financial state"
    POLICY ||--o{ CLAIM : "generates"
    MEMBER ||--o{ CLAIM : "submits"
    CLAIM ||--|{ LINE_ITEM : "contains"
    CLAIM ||--o| DISPUTE : "can have"
    MEMBER ||--o{ DISPUTE : "raises"

    PLAN {
        UUID id PK
        VARCHAR name
        TEXT description
        JSONB allowed_sum_insured_options
        BOOLEAN is_active
        TIMESTAMP created_at
    }
    POLICY {
        UUID id PK
        UUID plan_id FK
        DECIMAL chosen_sum_insured
        DATE tenure_start
        DATE tenure_end
        VARCHAR policyholder_name
        JSONB policyholder_contact
        JSONB policyholder_kyc
        JSONB bank_account_details
        TIMESTAMP created_at
    }
    MEMBER {
        UUID id PK
        UUID policy_id FK
        VARCHAR full_name
        DATE date_of_birth
        ENUM gender
        VARCHAR relationship
        JSONB ped_list
    }
    ACCUMULATOR {
        UUID policy_id PK, FK
        DECIMAL available_sum_insured
        DECIMAL accumulated_ncb
        DECIMAL active_deductible_paid
        JSONB category_usage
    }
    RULE {
        UUID id PK
        UUID plan_id FK
        VARCHAR name
        ENUM execution_phase
        INTEGER priority
        JSONB condition
        ENUM action_type
        JSONB action_config
        BOOLEAN is_active
    }
    CLAIM {
        UUID id PK
        UUID policy_id FK
        UUID member_id FK
        TEXT diagnosis_codes
        ENUM claim_type
        BOOLEAN is_accident
        DATE admission_date
        DATE discharge_date
        ENUM status
        DECIMAL total_billed
        DECIMAL total_insurer_payable
        DECIMAL total_member_payable
        JSONB documents_attached
        TIMESTAMP created_at
    }
    LINE_ITEM {
        UUID id PK
        UUID claim_id FK
        ENUM service_category
        DECIMAL billed_amount
        DECIMAL allowed_amount
        DECIMAL insurer_payable
        JSONB metadata
        ENUM status
        JSONB audit_trail
    }
    DISPUTE {
        UUID id PK
        UUID claim_id FK
        UUID member_id FK
        TEXT reason
        ENUM status
        TIMESTAMP created_at
    }
```

1. **Plan**: The master blueprint of the insurance product (e.g., "General Health Plan"). It defines the available sum insured tiers.
2. **Policy**: A specific contract purchased by a customer, tied to a Plan. It holds the active `chosen_sum_insured`, the tenure period, and policyholder KYC details.
3. **Member**: Individuals covered under a Policy. The system handles "family floaters" by allowing multiple Members to share a single Policy.
4. **Accumulator**: The dynamic, stateful financial ledger for a Policy. It tracks the `available_sum_insured`, active deductibles paid, and specific `category_usage` (e.g., how much has been spent on Room Rent this year). **There is strictly a 1:1 relationship between an Accumulator and a Policy.**
5. **Claim**: A single reimbursement or cashless request submitted by a Member.
6. **Line Item**: The granular billing entries within a Claim (e.g., Room Rent, Surgery, Pharmacy).
7. **Dispute**: A member-initiated contestation of a finalized adjudication outcome.
8. **Rule**: A pure logic configuration tied to a Plan, specifying exact adjudication behaviors.

## The Claim State Machine

Claims move through a strict, linear state machine designed to separate asynchronous automated processing from human administrative review.

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED : Member submits claim
    SUBMITTED --> PENDING_APPROVAL : Adjudication Engine finishes
    
    state Admin_Review {
        PENDING_APPROVAL --> APPROVED : Admin Approves
        PENDING_APPROVAL --> PARTIALLY_APPROVED : Admin Partially Approves
        PENDING_APPROVAL --> DENIED : Admin Rejects
    }
    
    APPROVED --> PAID : Finance processing
    PARTIALLY_APPROVED --> PAID : Finance processing
    
    APPROVED --> SUBMITTED : Admin Revert (Rollback)
    PARTIALLY_APPROVED --> SUBMITTED : Admin Revert (Rollback)
    DENIED --> SUBMITTED : Admin Revert (Rollback)

    PAID --> [*]
    DENIED --> [*]
```

1. **`SUBMITTED`**: Initial state upon API ingestion. Line items are created.
2. **`PENDING_APPROVAL`**: The Adjudication Engine has finished evaluating rules, generating an EOB, and calculating financials, but no physical money has been deducted yet. *(Note: The database schema includes a `VALIDATED` state. While deferred in V1, this acts as a seamless integration point for future synchronous document verification before hitting the heavy adjudication pipeline.)*
3. **`APPROVED` / `PARTIALLY_APPROVED` / `DENIED`**: An admin manually reviews the EOB and makes a binding decision. If approved, the Accumulator is hard-debited.
4. **`PAID`**: (Terminal) Finance has processed the NEFT payout.

### Revert Flow
If an admin realizes a mistake or a member raises a `Dispute`, the `POST /revert` endpoint reverses the state machine from an adjudicated state back to `SUBMITTED`, untangles the physical accumulator math, and drops it back into the engine to safely reach `PENDING_APPROVAL` again against the latest limits.

## How Coverage Rules are Modeled

We modeled coverage rules not as hardcoded Python logic, but as highly dynamic JSON payloads stored in the `rules` database table. This allows the system to add new rules without changing the underlying code.

Each rule has four critical properties:
1. **Execution Phase**: When the rule runs (`EXCLUSION` -> `CAPPING` -> `COVERAGE` -> `COST_SHARING`).
2. **Priority**: The exact order of execution within a phase.
3. **Condition**: A JSON AST (Abstract Syntax Tree) representing the boolean logic of when the rule should fire.
4. **Action**: The specific financial mutation (`EXCLUDE`, `LIMIT`, `COPAY`, `DEDUCTIBLE`) and its configuration.

### Example: Rule Payload
This is an example of how we represent a "10% Copay on Diagnostics" rule:

```json
{
  "name": "Flat 10% Copay on Diagnostics",
  "execution_phase": "COST_SHARING",
  "priority": 10,
  "condition": {
    "field": "service_category",
    "operator": "eq",
    "value": "DIAGNOSTICS"
  },
  "action_type": "COPAY",
  "action_config": {
    "copay_percentage": 10.0
  }
}
```

### The Adjudication Context Builder
The Rule Engine is entirely stateless. To evaluate the rules, the `Context Builder` flattens the Claim, the Policy, the Member's metadata, and the current state of the Accumulator into a single `Dict[str, Any]` (the Context). 

The Rule Engine then simply takes this Context, passes it through the Rule's `condition` AST, and if it resolves to `True`, it applies the math specified in the `action_config` to the Line Item. Each rule application generates an Audit Trail entry on the Line Item explaining exactly why a deduction or coverage happened.

# Architecture Decision Records (ADRs)

This document tracks the key design decisions, requirements, and assumptions for each finalized sub-process in the Claims Processing System.

---

## 1. Sub-Process: Seed Data Flow

### Context
To process claims and demonstrate the system's capabilities, we need realistic configuration data (insurance products/plans) and transactional base data (policies, members, accumulator states). The problem statement explicitly excludes policy purchase and enrollment flows from the scope.

### Decision
We will use static JSON files (or a dedicated seeding script) to load the necessary domain entities into the system's database/in-memory store on startup.

### Requirements
*   **Plans & Rules:** Seed at least two distinct Plans (e.g., Basic and Premium) configured with various rules (exclusions, capping, copays) using the generic Rule Engine DSL.
*   **Policies:** Seed active policy contracts linked to the plans.
*   **Members:** Seed member profiles, including edge cases (e.g., members with specific Pre-Existing Diseases (PEDs), senior citizens).
*   **Accumulators:** Initialize starting balances for sum insured, deductibles, and category limits for these policies.

### Assumptions
*   Since enrollment is out of scope, the seed data represents a completely valid, post-purchase state.
*   We assume data structures defined in the seed files match the expected domain entity schemas perfectly (no complex data ingestion validation required for seed data).

---

## 2. Sub-Process: Rule Engine & Claim Assessment Flow

### Context
Adjudicating a claim requires evaluating complex, plan-specific conditions (e.g., "Dental capped at ₹1L in Tier-1 cities", "30-day initial waiting period") against the current claim, its line items, the member's profile, and the policy's state. Hardcoding these rules creates a fragile system.

### Decision
We will implement a generic, domain-agnostic **Rule Engine** decoupled from specific insurance math **Effect Handlers**.

1.  **Context Construction:** The application layer flattens relevant domain entities (Claim, Line Item, Policy, Member, Accumulators) into a single JSON-like `context` object.
2.  **Condition DSL:** Rules define criteria using a generic, composable condition tree (using operators like `EQ`, `IN`, `GT`, and logical `all`/`any`).
3.  **Strict Pipeline Stages:** Rules are executed in a hardcoded, sequential order to ensure mathematical correctness: `EXCLUSION` $\rightarrow$ `CAPPING` $\rightarrow$ `COVERAGE` $\rightarrow$ `COST_SHARING`.
4.  **Priority execution:** Within a stage, rules are executed based on a defined `priority` integer.
5.  **Effect Execution:** When a rule's condition evaluates to `TRUE`, the engine triggers the designated `effect_type` handler (e.g., `ExcludeHandler`, `LimitHandler`, `CopayHandler`) which applies the financial change and generates the explanation reason.

### Requirements
*   Rules must be stored purely as configuration data (e.g., JSON associated with a Plan).
*   Adding a new rule for an existing effect type must require **zero code changes**.
*   The engine must accumulate an audit trail of applied rules to generate the Explanation of Benefits (EOB).

### Assumptions
*   The flat `context` object contains all necessary data fields required by the rule configurations.
*   The fixed 4-stage pipeline is sufficient to handle the complexity of the scoped Indian health insurance rules.
*   Complex cross-references (e.g., checking if `claim.diagnosis_code` exists within `member.ped_codes`) can be handled either by a specific DSL operator (`IN_ARRAY`) or resolved during context construction.

### Example: Defining and Evaluating a Rule

By separating the **Condition** (using a generic DSL) from the **Effect** (using typed handlers), new business rules can be created purely through configuration without touching the codebase.

**1. Defining a Rule (JSON Configuration)**
For example, to implement: *"Dental is covered up to ₹1 Lakh in Tier 1 cities"*, we define a rule where the condition checks the line item category and the policy city tier, and the effect applies a limit.

```json
{
  "name": "Dental limit - Tier 1",
  "stage": "CAPPING",
  "priority": 1,
  "condition": {
    "all": [
      { "field": "line_item.service_category", "operator": "EQ", "value": "DENTAL" },
      { "field": "policy.city_tier", "operator": "IN", "value": ["TIER_1"] }
    ]
  },
  "effect_type": "LIMIT",
  "effect_params": { "max_amount": 100000, "period": "PER_POLICY_YEAR", "accumulator_key": "DENTAL" }
}
```

**2. Evaluator Layer Execution**
1.  **Context Building:** The system flattens the claim request into a context map (e.g., `{"line_item.service_category": "DENTAL", "policy.city_tier": "TIER_1", ...}`).
2.  **Generic Evaluation:** The engine parses the `condition` DSL against the context. The engine knows *nothing* about health insurance at this step—it just evaluates `EQ` and `IN` operators.
3.  **Effect Trigger:** Because the condition returns `true`, the engine looks up the `LIMIT` handler (defined by `effect_type`) and passes it the `effect_params`. The handler executes the insurance math, reduces the payable amount, and logs the EOB explanation.

This makes adding a new rule for "Tier 2 cities" as simple as adding another JSON block, without requiring a software release.

---

## 3. Sub-Process: Claim Submission & Pipeline Flow

### Context
Both cashless and reimbursement claims require the same adjudication engine, but differ in entry points (hospital portal vs customer app), intermediate steps (pre-auth vs document verification), and settlement targets (hospital vs policyholder). We need a pipeline architecture that manages claim state transitions for each approval flow while maximizing code reuse.

### Decision

#### V1 Scope: Reimbursement Flow Only
For V1, we implement the **Reimbursement Pipeline** end-to-end. Cashless flow (pre-authorization, network validation, hospital settlement) is deferred to V2. The architecture will support adding the Cashless Pipeline without refactoring.

#### Pipeline Architecture
A `ClaimPipeline` is an ordered list of composable **Steps**. Each step receives the current Claim + context, performs its work, and transitions the claim to the next state — or halts the pipeline with a failure/hold state.

```
Step {
  execute(claim, context) → StepResult { status: CONTINUE | HALT, next_state }
}
```

#### V1 Reimbursement Pipeline (Implemented)

```
PolicyValidation → DocumentVerification → Adjudication → AccumulatorUpdate → EOBGeneration → ManualApproval → PolicyholderPayout
```

| Step | Responsibility | Output State |
|---|---|---|
| `PolicyValidation` | Is policy active? Is member enrolled? Is filing within deadline? | `VALIDATED` (or `REJECTED` if invalid) |
| `DocumentVerification` | Checks mandatory documents (claim form, discharge summary, receipts, cancelled cheque). Missing docs halt pipeline. | `UNDER_REVIEW` (or `QUERY_RAISED` if docs missing) |
| `Adjudication` | Runs the Rule Engine (Exclusion → Capping → Coverage → Cost-Sharing) on each line item. Builds per-line-item audit trail. | `ADJUDICATED` |
| `AccumulatorUpdate` | Tentatively reserves the approved amount from the policy's sum insured and category buckets. | `ADJUDICATED` (accumulators updated) |
| `EOBGeneration` | Builds the structured Explanation of Benefits with per-line-item breakdown and audit trail. | `ADJUDICATED` (EOB attached) |
| `ManualApproval` | Pipeline **halts here**. An approver reviews the full audit trail and updates the `manual_approval_status`. | `APPROVED` / `PARTIALLY_APPROVED` / `DENIED` |
| `PolicyholderPayout` | Marks the claim for NEFT payout to the policyholder's bank account. | `PAID` |

#### Manual Approval Step (Detail)
The `ManualApproval` step is critical. It ensures no claim is auto-paid without human oversight. When the pipeline reaches this step:

1.  The claim status moves to `PENDING_APPROVAL`.
2.  The `manual_approval_status` field is set to `PENDING`.
3.  The approver is presented with the **full audit trail**.
4.  The approver submits their decision via the API, which updates the `manual_approval_status` and finalizes the overall claim `status`.
5.  Only after manual approval does the pipeline resume to the `PolicyholderPayout` step.

#### Audit Trail Structure (Per Line Item)
Each line item accumulates an ordered list of `AdjustmentRecord` objects as it passes through the adjudication pipeline:

```json
{
  "line_item_id": "li_001",
  "service_category": "ROOM_RENT",
  "billed_amount": 12000.00,
  "audit_trail": [
    {
      "step": 1,
      "rule_name": "Room Rent Cap - Tier 1",
      "stage": "CAPPING",
      "effect_type": "PROPORTIONATE_LIMIT",
      "amount_before": 12000.00,
      "amount_adjusted": -2000.00,
      "amount_after": 10000.00,
      "reason_code": "ROOM_RENT_EXCEEDED",
      "explanation": "Room rent capped at ₹10,000/day. Billed ₹12,000/day."
    },
    {
      "step": 2,
      "rule_name": "Standard Copay 10%",
      "stage": "COST_SHARING",
      "effect_type": "COPAY",
      "amount_before": 10000.00,
      "amount_adjusted": -1000.00,
      "amount_after": 9000.00,
      "reason_code": "MEMBER_COPAY",
      "explanation": "10% copay applied on allowed amount of ₹10,000."
    }
  ],
  "final_allowed_amount": 9000.00,
  "insurer_payable": 9000.00,
  "member_payable": 3000.00,
  "recommended_status": "APPROVED",
  "approver_action": null,
  "approver_override_reason": null
}
```

#### V2 Cashless Pipeline (Future — Documented for Architecture)

```
PolicyValidation → NetworkValidation → PreAuthApproval
    ... [treatment pause] ...
FinalBillReconciliation → Adjudication → AccumulatorUpdate → EOBGeneration → ManualApproval → HospitalSettlement
```

Key differences from Reimbursement:
*   `NetworkValidation`: Validates hospital is in the plan's network list.
*   `PreAuthApproval`: Issues a temporary coverage cap letter based on estimated costs. Claim enters a **pause state** (`PRE_AUTH_APPROVED`) until the hospital submits the final discharge bill.
*   `FinalBillReconciliation`: Compares actual discharge bill against the pre-auth estimate.
*   `HospitalSettlement`: Payout is directed to the hospital, not the policyholder.
*   The pipeline has a **two-phase execution** — Phase 1 runs up to `PreAuthApproval`, then the pipeline resumes from `FinalBillReconciliation` when the final bill arrives.

#### State Machine — V1 Reimbursement

```
SUBMITTED
  → VALIDATED (policy checks pass)
  → QUERY_RAISED (missing documents — pipeline halts, awaits resubmission)
  → UNDER_REVIEW (documents verified, adjudication begins)
  → ADJUDICATED (rules have fired, amounts calculated)
  → PENDING_APPROVAL (awaiting manual approver action)
  → APPROVED / PARTIALLY_APPROVED / DENIED (approver confirms or overrides)
  → PAID (NEFT payout processed)
  → DISPUTED (member appeals — separate flow)
```

### Requirements
*   Each pipeline step must be a self-contained, testable unit.
*   State transitions must be guarded — a claim can only move to states allowed by the current pipeline step. No free-form status updates via API.
*   The full audit trail must be persisted before the `ManualApproval` step so the approver has complete visibility.
*   Approver overrides must be logged with a mandatory reason and appended to the audit trail (not replacing the original adjudication output).

### Assumptions
*   V1 implements only the Reimbursement Pipeline. The Claim entity schema includes nullable cashless-specific fields (`pre_auth_id`, `claim_type`) to support V2 without migration.
*   The `ManualApproval` step is synchronous in V1 — we expose an API endpoint for the approver to submit their decision. No async notification/queue system.
*   The `QUERY_RAISED` state allows document resubmission, after which the pipeline resumes from `DocumentVerification`.
*   Accumulator reservations made before `ManualApproval` are tentative. If the approver denies or overrides, the reservation is rolled back/adjusted.

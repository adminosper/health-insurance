# Architecture & Design Decisions

This document details what was built, what was deferred, and the core assumptions made for each major sub-process in the Claims Processing System.

---

## 1. Sub-Process: Seed Plans and Policy Data

### Why Required
To test or demonstrate any working claim processing functionality, we must have active policy contracts, enrolled members, product plans, and initial coverage limits (accumulators) already present in the system. Because member enrollment and policy purchase are out-of-scope, this foundation must be seeded beforehand.

### What Built
* **Automated Seed Scripts**: We created `init-db/01_schema.sql` and `init-db/02_seed.sql` which run automatically when the PostgreSQL database container starts.
* **Testing Ready**: The scripts populate two distinct products (General Health Plan and Heart Disease Critical Care Plan), 11 complex JSONB rules, 4 policy tiers, 6 members, and initial accumulator states so that the system is fully testable out-of-the-box.

### What We Didn't (Deferred)
* **Policy Management UI**: We did not build screens or endpoints for creating policies, adding members, or editing plan types.
* **Production-Grade Secure PHI/KYC Storage**: To keep the database setup simple for this local assignment, member identity and KYC data (like names, ages, and medical history) are stored in plaintext in the database. 

  In a production system, this sensitive Personally Identifiable Information (PII) and Protected Health Information (PHI) will be secured by:
  1. **Field-Level Encryption (FLE)** within the database to ensure sensitive columns (such as member names, email/phone details, and medical codes) are encrypted using strong encryption keys.
  2. **Isolated Identity Tokenization / Vault**: Storing high-risk identity profiles in a dedicated secure data vault (such as HashiCorp Vault or AWS Secrets Manager) and referencing them in the transactional database via non-sensitive tokens/reference IDs.

### Assumptions
* **Health Insurance Domain Limit**: We assume we are building strictly for the health insurance domain for now. Modeling other insurance domains (e.g., motor, property, life) would require completely different accumulator types, rules, and claim models.

---

## 2. Sub-Process: Claim Submission and Status Retrieval (Customer/Member Perspective)

### Why Required
Members need to submit claims electronically and track their adjudication status in real-time. Because claim processing and medical rule adjudication are heavy operations, the submission workflow must be decoupled from the actual processing engine to ensure high API responsiveness and resilience.

### What Built
* **Member Claims APIs**: Implemented `POST /api/v1/claims` for submitting claims and `GET /api/v1/claims/{claim_id}` for members to fetch their claim status and details.
* **Member/Policy Validation**: The submission endpoint verifies synchronously that the submitting member is actually part of the provided policy before creating the claim.
* **Field-Level Encryption (FLE) for Diagnosis Codes**: Since diagnosis codes represent sensitive Protected Health Information (PHI), they are encrypted at the application layer using symmetric encryption (Fernet) before being saved to the database. The secret key is loaded from the environment variables, ensuring that diagnosis codes are encrypted at rest in the database.
* **Decoupled Architecture**: Validated claims are persisted to the database with a status of `SUBMITTED`, laying the groundwork for asynchronous processing.

### What We Didn't (Deferred)
* **Duplicate Claim Submission**: Validations will also contain checks for duplicate claim submission in V2. This is currently not implemented as part of V1.
* **Immediate Policy/Limit Adjudication**: We do not run immediate checks to validate rules, policy limits, or remaining balances (accumulators) during submission. For v1, all these adjudications and policy limits/rules validations are deferred to run at the same time during the decoupled claim processing phase.
* **Role-Based Access Control (RBAC)**: Fine-grained user vs. admin access policies (e.g., ensuring only administrators can view decrypted diagnosis codes) are deferred to a later iteration.

### Assumptions
* **Mocked Document Attachments**: The system does not process actual files or documents. Instead, documents are passed as a list of document type strings (validated against a finite set of allowed document enums, e.g., `"bills"`, `"receipts"`). In a production flow, we assume documents would need actual binary storage (e.g., S3), parsing/OCR, and manual validation audits to verify physical documents.

---

## 3. Sub-Process: Claim Processing

### Why Required
Once a claim is submitted, it must undergo complex medical rules adjudication, coverage validation, and financial calculations to determine the final insurer and member payable amounts. This process is complex and heavily data-driven, requiring a strict separation of concerns between state management (orchestration) and stateless logic evaluation (rules).

For a high-level technical deep dive, please review the engine documentation first: [documentations/engines_architecture.md](file:///Users/shagunarora/Desktop/realfast-claim-processing-system/documentations/engines_architecture.md).

### What Built
* **Two-Engine Architecture**: We divided the processing into two distinct engines to maintain clean boundaries:
  1. **Rule Engine**: A pure, stateless evaluator. It parses a custom JSON Domain Specific Language (DSL) to evaluate conditions (e.g., diagnosis matches, waiting periods) and executes financial mutations (EXCLUDE, LIMIT, COPAY, DEDUCTIBLE) on individual line items.
  2. **Adjudication Engine (Pipeline)**: The stateful orchestrator. It fetches necessary database records, builds the flattened execution context, runs the sequential processing phases (`EXCLUSION` -> `CAPPING` -> `COVERAGE` -> `COST_SHARING`), manages in-memory accumulators across line items, and handles database persistence.
* **Line Item Metadata Normalization**: Designed a metadata structure (`quantity` and `unit`) on line items. The Context Builder converts this into a standard `per_unit_amount` so that the Rule Engine doesn't have to understand different units of measure.
* **Concurrent Claim Idempotency**: Handled cases where a claim is processed while another claim for the same policy is already `PENDING_APPROVAL`. The system computes the *effective* sum insured by pre-deducting amounts reserved by other pending claims, ensuring limits are never double-spent. Because of this dynamic effective balance, **we never physically update the `accumulators` database row during adjudication**. Physical hard-debits only occur when the claim is finalized to `PAID`.
* **Deferred Accumulator Math**: To avoid leaking funds, in-memory accumulator usage is tracked in a deferred manner during the pipeline execution. The absolute final, post-copay `insurer_payable` amount is what gets recorded against the accumulator at the very end of the line item's processing.
* **Unit-Agnostic Capping**: The rule engine's LIMIT action dynamically scales caps based on the line item metadata (`quantity` and `unit`). By configuring a rule with `"limit_type": "PER_UNIT"` and an explicit `"limit_unit"`, the engine natively supports multi-unit treatments (like physiotherapy sessions or room rent days) without hardcoded period checks.
* **Stateful Manual Review**: Implemented the final phase where a `PENDING_APPROVAL` claim undergoes manual admin review (Approve/Reject). This isolates the stateless adjudication from the stateful physical debits made to the Postgres `accumulators` table upon Approval.
* **Atomic Re-Adjudication Revert**: Added a `POST /revert` rollback mechanism that elegantly reverses physical accumulator math and dynamically drops the claim back into the processing pipeline to instantly incorporate any limit changes, eliminating complex synchronization bugs during reviewer reversals.
* **Member Disputes**: Implemented a workflow allowing policyholders to raise disputes on manually reviewed claims. The dispute lifecycle includes `RAISED`, `UNDER_PROCESSING`, and `RESOLVED` statuses. 

### What We Didn't (Deferred) / V1 Limitations
* **Admin Dispute Notification & Queueing**: We implemented the API endpoints to raise and update disputes, but deferred building the internal admin notification queue. In a future iteration, an admin would be notified of a `RAISED` dispute, transition it to `UNDER_PROCESSING`, investigate, and if the member is correct, use the existing Revert endpoint to re-adjudicate before marking the dispute as `RESOLVED`.
* **Member Dispute Cancellation**: We are deferring the ability for a user to close or withdraw their own dispute to V2. In V1, once a dispute is raised, it must be resolved by an admin.
* **Rule-Specific Manual Approvals**: We are deferring the logic to tag specific rules as "requiring manual check" to V2. For V1, we assume all rules configured in the system can be fully and autonomously processed by the Rule Engine without requiring an explicit manual override queue just for a triggered rule.
* **Manual Rejections & Re-adjudication**: Because we use a Dynamic Effective Balance for accumulators, if a human manually overrides a `PENDING_APPROVAL` claim to `REJECTED`, the locked funds are instantly freed. In V1, any subsequent claims that were unfairly denied due to those previously locked funds must be manually re-triggered by an administrator. In V2, this will be an automated async job.
* **Cross-Line-Item Proportional Adjustments**: Our Rule Engine evaluates one line item at a time. It cannot handle complex rules like "If Room Rent exceeds limit, proportionally reduce all other associated line items by the same ratio." This would require a separate multi-item post-processing phase.
* **Complex Multi-Claim Deductibles**: Family floater deductibles (where individuals and the family unit have intersecting thresholds) are simplified in V1 to a single policy-level tracker.
* **Asynchronous Queueing System**: Although built decoupled, the actual processing is currently triggered via a synchronous admin endpoint for testing purposes. In production, a message broker (e.g., Kafka or RabbitMQ) would listen for `SUBMITTED` claims and process them via background workers.

### Assumptions
* **Execution Phase Ordering**: We assume a strict, hardcoded order of operations: `EXCLUSION` rules run first (to drop invalid items entirely), followed by `CAPPING` (per-item or category limits), then `COVERAGE` (overall policy sum insured limits), and finally `COST_SHARING` (copays and deductibles on the remaining covered amount).
* **PED and Medical Codes Enum**: We assume all Pre-Existing Disease (PED) and medical diagnosis codes are consistent strings across rules and claims. While an ENUM or a standard taxonomy (like ICD-10) should be created for data integrity, we deferred this since the primary focus was building the claim processing orchestration.

### Pipeline State Machine & Audit Trail (V1 Reimbursement)
The backend manages state transitions safely and automatically builds a full audit trail before `PENDING_APPROVAL`:
```
SUBMITTED
  → VALIDATED (policy checks pass)
  → PENDING_APPROVAL (awaiting manual approver action)
  → APPROVED / PARTIALLY_APPROVED / DENIED (approver confirms or overrides)
  → PAID (NEFT payout processed)
```
Each line item generates a detailed `audit_trail` tracking every mathematical mutation:
```json
{
  "step": 1,
  "rule_name": "Room Rent Cap",
  "stage": "CAPPING",
  "effect_type": "LIMIT",
  "amount_before": 12000.00,
  "amount_adjusted": -2000.00,
  "amount_after": 10000.00,
  "reason_code": "ROOM_RENT_EXCEEDED",
  "explanation": "Capped Room Rent"
}
```

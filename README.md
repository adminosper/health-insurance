# Health Insurance Claim Processing System

Welcome to the **RealFast Claim Processing Adjudication Engine**. This repository contains the backend engine responsible for intaking health insurance claims, validating them, and executing complex adjudication rules (Exclusions, Capping, Copays, and Deductibles) using a unified Context Builder and stateless Rule Engine.

## Context & Documentation
Before diving into the code, we highly recommend reading the following architectural and design documents to understand the system's "why" and "how":

* **Product Requirements**: [documentations/PRD.md](./documentations/PRD.md)
* **Detailed Claim Processing Decisions**: [submission_docs/decisions.md](./submission_docs/decisions.md)
* **Engines Architecture (The Core)**: [documentations/engines_architecture.md](./documentations/engines_architecture.md)

## Prerequisites
To run and test this system locally, you only need:
* **Docker** & **Docker Compose** installed and running on your machine.
* A REST client like **Postman**, **cURL**, or simply the built-in **Swagger UI** (accessed via browser).

## Setup Flow

1. **Clone the repository and navigate into the folder.**
2. **Create a `.env` file** in the root directory to provide the encryption key used for securing HPII details (Health Protected Identifiable Information). You can use this pre-generated dummy key for testing:
   ```bash
   echo 'ENCRYPTION_KEY="TnpHcl9MNEp0Wkp3cEtLZDRfU3pBcU9pQ1JXY2hwQzM="' > .env
   ```
3. **Spin up the Docker containers**:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```
   *Note: This spins up a PostgreSQL database and a FastAPI backend (`http://localhost:8000`). The database is automatically seeded with Plans, Policies, Rules, Members, and Accumulators via the `init-db/02_seed.sql` script.*

3. **Verify the API is running**:
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser. You should see the interactive Swagger API documentation.

## Test Flow

This guide walks you through submitting a claim and manually triggering the asynchronous Adjudication Engine.

### Step 1: Submit a Claim
Let's submit a reimbursement claim for a member. We will use a pre-seeded policy for Rajesh Kumar (Policy ID: `c1b2c3d4-0001-4000-8000-000000000001`).

**Endpoint:** `POST http://localhost:8000/api/v1/claims`

**Request Body (JSON):**
```json
{
  "policy_id": "c1b2c3d4-0001-4000-8000-000000000001",
  "member_id": "d1b2c3d4-0001-4000-8000-000000000001",
  "claim_type": "REIMBURSEMENT",
  "is_accident": false,
  "admission_date": "2025-02-01",
  "discharge_date": "2025-02-05",
  "diagnosis_codes": ["I10"],
  "documents_attached": [
    "BILLS"
  ],
  "line_items": [
    {
      "service_category": "ROOM_RENT",
      "billed_amount": 30000.00,
      "metadata": {
        "quantity": 5,
        "unit": "DAY"
      }
    },
    {
      "service_category": "PHARMACY",
      "billed_amount": 5000.00,
      "metadata": {
        "quantity": 1,
        "unit": "UNIT"
      }
    }
  ]
}
```

**Desired Output:**
You should receive a `201 Created` response. Notice that the claim `status` is currently **`SUBMITTED`**, and `total_insurer_payable` is 0. 
*Copy the `id` (the Claim ID) from the response for the next step.*

### Step 2: Trigger the Adjudication Pipeline
In production, a message broker triggers the pipeline. For testing, we expose an admin endpoint to manually force the Adjudication Engine to process the claim.

**Endpoint:** `POST http://localhost:8000/api/v1/admin/claims/{claim_id}/process` *(Replace `{claim_id}` with the ID from Step 1)*

**Desired Output:**
You should receive a `200 OK` response. 
Notice the outcome! The `status` has transitioned to **`PENDING_APPROVAL`**.
The Engine executed the rules:
1. *Room Rent Capping*: Rajesh's plan has a 5L Sum Insured, capping room rent at Rs. 5000/day. The billed amount was Rs. 30,000 for 5 days (6000/day). The pipeline capped the `insurer_payable` to 25,000 for that line item.
2. *Copay*: A flat 10% copay was applied across the board on the allowed amounts.
3. The total `insurer_payable` and `member_payable` fields in the response are now mathematically accurate based on the parsed JSON rules.

### Step 3: Fetch Explanation of Benefits (EOB)
Now that the Adjudication Engine has mathematically processed the claim, a reviewer (or the member) can fetch the fully generated EOB. This endpoint compiles the per-line-item audit trails detailing exactly what financial rules fired and why.

**Endpoint:** `GET http://localhost:8000/api/v1/claims/{claim_id}/eob`

**Desired Output:**
You will receive a detailed JSON response showing the `total_billed`, `total_insurer_payable`, and a `line_items` array. Inside each line item, you'll see a pristine `audit_trail` array that tracks every rule that impacted the financials (e.g., Room Rent Capping, Copays) with explicit `amount_adjusted` values and `reason_codes`!

### Step 4: Admin Manual Review
Once a claim has been adjudicated and is sitting in the `PENDING_APPROVAL` state, an administrator can manually review it and make a final decision to either APPROVE or REJECT the claim.

**Endpoint:** `POST http://localhost:8000/api/v1/admin/claims/{claim_id}/review`

**Request Body (JSON):**
```json
{
  "action": "APPROVE",
  "notes": "Looks good, all rules applied correctly."
}
```

**Desired Output:**
You will receive a `200 OK` response with the claim status updated to **`APPROVED`** (or `PARTIALLY_APPROVED`).
Crucially, *this is the exact moment* the physical database accumulators are hard-debited. The `available_sum_insured` drops, and `category_usage` is incremented.
*(Note: If you pass `"action": "REJECT"`, the claim is marked `DENIED` and the pending limits are instantly un-locked for the next claim!)*

### Step 5: Revert a Manual Decision (Rollback)
If an admin made a mistake or a member raises a dispute, the system supports a robust atomic rollback mechanism. 

**Endpoint:** `POST http://localhost:8000/api/v1/admin/claims/{claim_id}/revert`

**Desired Output:**
You will receive a `200 OK` response with the claim status updated back to **`PENDING_APPROVAL`**.
Under the hood, the Engine securely untangles and reverses the physical accumulator math, transitions the claim to `SUBMITTED`, and then instantly runs `process_claim` again to dynamically re-adjudicate the claim against the latest policy limits!

### Step 6: Member Disputes Workflow
If a member disagrees with the final adjudication decision (e.g. the cap is too low, or a rule was incorrectly applied), they can raise a formal dispute.

**Endpoint:** `POST http://localhost:8000/api/v1/claims/{claim_id}/disputes`

**Request Body (JSON):**
```json
{
  "member_id": "d1b2c3d4-0001-4000-8000-000000000001",
  "reason": "The room rent capping was incorrectly applied as I have a corporate waiver."
}
```

**Desired Output:**
You will receive a `201 Created` response with the dispute `status` as **`RAISED`**. 
*Note: A dispute can ONLY be raised on claims that have already been manually reviewed (`APPROVED`, `PARTIALLY_APPROVED`, or `DENIED`).*

**Admin Dispute Lifecycle (Not fully built in V1):**
In a complete production environment, the following workflow occurs:
1. **Notification**: The Admin queue is notified of the `RAISED` dispute.
2. **Investigation**: An admin picks up the dispute, and updates the status to **`UNDER_PROCESSING`** via `POST /api/v1/admin/disputes/{dispute_id}/status`.
3. **Revert & Fix**: If the admin decides the member is right, they will use the Revert endpoint (`POST /admin/claims/{claim_id}/revert`) to untangle the math, manually adjust the claim or policy configuration, and re-adjudicate.
4. **Resolution**: The admin updates the dispute status to **`RESOLVED`**.

### Step 7: Verify the Database (Optional)
If you want to see how this translates to raw database state:

1. Log into the Docker database container:
   ```bash
   docker exec -it realfast-claim-processing-system-db-1 psql -U postgres -d health_insurance
   ```
2. Query the line items for your claim:
   ```sql
   SELECT service_category, billed_amount, allowed_amount, insurer_payable, status, audit_trail 
   FROM line_items 
   WHERE claim_id = 'YOUR_CLAIM_ID_HERE';
   ```
You will see exactly how the `audit_trail` JSONB array captures every rule that fired.

---

## Running the Automated Test Suite
To verify the complex domain logic without making API calls, you can run our comprehensive pytest suite.

1. Ensure your Python environment is set up (or run this inside the API docker container):
   ```bash
   # Run from the root directory
   PYTHONPATH=. pytest tests/ -v
   ```
2. **Desired Output:** All 38 tests (Domain and Unit tests) should pass, proving the isolation between the Stateless Rule Evaluator and the Stateful Adjudication Orchestrator, as well as testing manual review limits math.

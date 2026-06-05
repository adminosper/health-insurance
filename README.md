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

### Step 3: Verify the Database (Optional but recommended!)
If you want to see the beautifully generated Audit Trails for each line item (which an Admin Reviewer would see):

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
You will see exactly how the `audit_trail` JSON array captures every rule that fired (`LIMIT`, `COPAY`, etc.), the exact reason codes, and the precise financial impact step-by-step.

---

## Running the Automated Test Suite
To verify the complex domain logic without making API calls, you can run our comprehensive pytest suite.

1. Ensure your Python environment is set up (or run this inside the API docker container):
   ```bash
   # Run from the root directory
   PYTHONPATH=. pytest tests/ -v
   ```
2. **Desired Output:** All 27 tests (Domain and Unit tests) should pass, proving the isolation between the Stateless Rule Evaluator and the Stateful Adjudication Orchestrator.

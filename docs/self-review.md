# Self-Review

This document provides an honest assessment of the system's current state, highlighting architectural strengths and acknowledging technical limitations.

## What's Good

1. **Extensible and Scalable Architecture:** The strict decoupling of the stateless Rule Engine from the stateful Adjudication Engine makes the system highly scalable. It provides the flexibility to easily upgrade or swap out the rule evaluation logic in the future without touching the orchestration flow. Currently, the system elegantly handles simple to moderate rules, such as:
   * **Unit-based Capping:** Capping room rent at ₹5,000 *per day*.
   * **Categorical Exclusions:** Denying all line items under the "Cosmetic" category.
   * **Cost Sharing:** Applying a flat 10% copayment across all approved coverage amounts.

2. **Clean Code Structure:** The codebase is thoughtfully organized using strict layer separation (`src/routes`, `src/services`, `src/repositories`, `src/models`). Every module has a single, clearly defined responsibility, making the repository highly readable and easy to navigate.

3. **Concurrency and Idempotency Tracking:** The system actively guards against concurrency issues by computing dynamic effective balances to prevent double-spending of policy limits. The deferred math processing ensures that accumulators are completely isolated until explicit manual review finalizes the debits.

## What's Rough

1. **Rule Engine Complexity Limits:** The current iteration of the Rule Engine evaluates line items in strict isolation. It requires architectural modifications to natively support complex, cross-item rules. Examples include proportional adjustments (reducing doctor consultation fees if room rent exceeds limits) or complex family floaters (handling shared deductibles where an individual has a sub-limit).

2. **Reviewer Assignment and Locking:** Currently, we do not store the identity of the administrator performing the manual review, nor do we employ optimistic locking on the claim record. If two reviewers attempt to approve or revert the exact same claim simultaneously, a race condition could occur. 

## What I Would Change With More Time

1. **Test Coverage Depth:** While we have solid coverage isolating the core domain logic and basic scenarios, the permutations of medical claims are vast. I would write a much more comprehensive suite of scenario-based integration tests to cover edge cases like retroactive policy cancellations, overlapping hospital stays, or out-of-network provider penalties.

2. **Asynchronous Processing:** Right now, we manually trigger the heavy adjudication process synchronously via an API endpoint for testing purposes. In a real production system, I would offload this to an asynchronous background worker queue (like Celery or Kafka) to prevent blocking the web server and to support retry mechanisms.

3. **Database Migrations:** We are currently using raw SQL scripts (`01_schema.sql`) to initialize the database. I would move to a structured migration tool like **Alembic** to safely and incrementally evolve the schema in production.

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

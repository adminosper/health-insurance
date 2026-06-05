# Self-Review

## Areas for Improvement
* **Adjudication Engine Domain Tests**: Our domain tests currently rely on mocking the `claims_repo` and manually constructing data objects. In the future, these tests should ideally be refactored into true integration tests that run against a live test database to verify complete end-to-end processing logic from API boundary to DB persistence. And also test cases should also be improved.

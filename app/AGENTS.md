# AGENTS.md
# Recurring Development Rules for This Project

This file captures the coding standards, structural conventions, and workflow
expectations that are consistently applied across all work in this repository.
Treat every rule here as a hard requirement, not a preference.

---

## 1. Code Structure & Modularity

- **One responsibility per file.** Each module solves exactly one problem.
  Entry-point files only wire things together. Logic files only contain
  domain behaviour. Data-access files only communicate with external stores.
  Never mix concerns within a single file.
- **Extract reusable logic immediately.** If the same branching pattern or
  data-shaping logic appears more than once, extract it into a named helper
  before the second usage lands. Inline duplication is not acceptable as a
  shortcut.

---

## 2. File Placement & Folder Discipline

- **Respect the existing layer structure.** New files must land in the correct
  layer folder:

  | Layer | Suggested Location |
  |---|---|
  | Entry points / handlers | `src/routes/` |
  | Business / domain logic | `src/services/` |
  | Data transformation | `src/presenters/` or `src/serializers/` |
  | Data access / queries | `src/repositories/` or `db/` |
  | Auth / security helpers | `src/auth/` |
  | Shared pure utilities | `src/utils/` or `src/shared/` |
  | Data models / schemas | `src/models/` |
  | Config / settings | `src/config.py` |

- **Never create files at the wrong level.** A data-access function must not
  live inside an entry-point file. A presenter must not directly execute a
  database call.
- **Registration of components is centralised.** Routers, handlers, or plugin
  registrations belong in a single registry or bootstrap module. New
  components must be added there, not scattered across startup code.

---

## 3. Reuse vs. Duplication

- **Search before adding.** Before writing a new helper, check whether an
  equivalent already exists in `utils/`, `shared/`, or the same module. Prefer
  extending an existing well-named function over creating a near-duplicate.
- **Constants are module-level declarations.** Raw strings, query templates,
  or magic values belong at the top of the file as named constants. Do not
  inline them inside function bodies.
- **Configuration comes from one place only.** All environment-variable reads
  are centralised in a dedicated settings/config class or module. No other
  module may read environment variables directly.

---

## 4. Naming Conventions

- **Be explicit, not clever.** Names should describe what a thing *is* or
  *does*, not how it is implemented. Avoid single-letter variables outside
  short loop counters.
- **Consistency over personal style.** Follow the naming pattern already in
  use in the surrounding code (camelCase, snake_case, PascalCase — whichever
  the codebase establishes). Do not introduce a second convention in the same
  layer.
- **Functions are verbs, data structures are nouns.** `fetch_user_report()`
  not `user_report()`; `UserReport` not `FetchUserReport`.

---

## 5. Import Placement & Formatting

- **Language-level future compatibility first.** If the language or toolchain
  supports a forward-compatibility pragma or import (e.g.,
  `from __future__ import annotations` in Python), it goes at the very top of
  every file.
- **Standard import order (enforced by the project linter):**
  1. Language-level compatibility imports
  2. Standard library / built-ins
  3. Third-party dependencies
  4. Local / project imports
  - Each group is separated by a blank line.
- **No wildcard imports.** `from module import *` is never permitted.
- **Import only what you use.** Unused imports must be cleaned up before
  finalising any change.
- **Absolute imports only.** Use full package paths. Relative imports are
  acceptable only inside package init files for controlled re-exports.

---

## 6. Error Handling

- **Be explicit about failure modes.** Every function that can fail must either
  return a typed error value or raise a clearly named exception — never swallow
  errors silently.
- **Errors are logged at the boundary.** Log the full context (operation,
  inputs, trace) at the layer that first catches the error. Do not re-log the
  same error further up the call stack.
- **User-facing messages are decoupled from internal details.** Exception
  messages and internal stack traces must never be forwarded verbatim to
  external callers.

---

## 7. Testing Expectations

- **New logic ships with tests.** Any new service function, utility, or data
  transformation must have at least one unit test covering the happy path and
  one covering a representative failure case.
- **Tests are co-located or mirror the source tree.** Test files follow the
  same folder hierarchy as the source they cover (e.g., `tests/services/`
  mirrors `src/services/`).
- **No logic in test setup.** Fixtures and helpers exist to prepare state, not
  to assert behaviour. Keep assertions in test bodies.

---

## 8. Documentation & Comments

- **Comments explain *why*, not *what*.** Code should be readable enough that
  inline comments only appear when the reasoning behind a decision is not
  obvious from the code itself.
- **Public interfaces have docstrings.** Every exported function, class, or
  module that is consumed outside its own file must have a concise docstring
  describing its contract.
- **Keep docs close to code.** If behaviour changes, the relevant docstring or
  inline comment must be updated in the same commit.

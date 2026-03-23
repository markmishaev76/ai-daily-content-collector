# AI Harness Scorecard: ai-daily-content-collector

**Grade: F** (7.9/100) | No meaningful harness. AI output is essentially unaudited.

- **Repository**: `/home/runner/work/ai-daily-content-collector/ai-daily-content-collector`
- **Languages**: python
- **Assessed**: 2026-03-23 06:55 UTC
- **Checks**: 3/31 passed

## Summary

| Category | Weight | Score | Checks |
|----------|--------|-------|--------|
| Architectural Documentation | 20% | 0% [----------] | 0/5 |
| Mechanical Constraints | 25% | 14% [#---------] | 1/7 |
| Testing & Stability | 25% | 6% [#---------] | 1/8 |
| Review & Drift Prevention | 15% | 20% [##--------] | 1/6 |
| AI-Specific Safeguards | 15% | 0% [----------] | 0/5 |

## Architectural Documentation (0%)

### [FAIL] Architecture Documentation (0/5)

_matklad ARCHITECTURE.md guide_

**Evidence**: No architecture documentation found

**Remediation**: Create ARCHITECTURE.md at repo root following matklad's pattern: short, stable, focused on module boundaries and constraints.

### [FAIL] Agent Instructions (0/5)

_OpenAI Harness Engineering (2026)_

**Evidence**: No AI agent instruction files found

**Remediation**: Create CLAUDE.md or AGENTS.md with project context, code style, and constraints so AI agents produce consistent output.

### [FAIL] Architecture Decision Records (0/3)

_DORA 2025 Report - AI-accessible documentation_

**Evidence**: No Architecture Decision Records found

**Remediation**: Create docs/adr/ directory with numbered markdown decision records. Use adr-tools or a simple template.

### [FAIL] Module Boundary Documentation (0/4)

_matklad ARCHITECTURE.md - constraints as absences_

**Evidence**: No module boundary constraints documented

**Remediation**: Document which modules must NOT depend on each other in ARCHITECTURE.md. Example: 'The fields crate never depends on any other workspace crate.'

### [FAIL] API Documentation (0/3)

_DORA 2025 - AI-accessible documentation_

**Evidence**: No API documentation generation or spec files found

**Remediation**: Add doc generation to CI (cargo doc, typedoc, sphinx) or maintain OpenAPI/Swagger specs.


## Mechanical Constraints (14%)

### [PASS] CI Pipeline (3/3)

_DORA 2025 Report_

**Evidence**: CI detected: github

### [FAIL] Linter Enforcement (0/4)

_OpenAI Harness Engineering - mechanical constraints_

**Evidence**: No linter found in CI

**Remediation**: Add a linter to CI that blocks merges on violations (e.g. cargo clippy -- -D warnings, eslint --max-warnings 0).

### [FAIL] Formatter Enforcement (0/3)

_OpenAI Harness Engineering - mechanical constraints_

**Evidence**: No formatter check found in CI

**Remediation**: Add a formatter check to CI (e.g. cargo fmt --all -- --check, prettier --check).

### [FAIL] Type Safety (0/3)

_SlopCodeBench - preventing subtle type errors_

**Evidence**: No type safety enforcement found

**Remediation**: Use a statically typed language, enable TypeScript strict mode, or add mypy/pyright to CI for Python.

### [FAIL] Dependency Auditing (0/4)

_Blog: security infrastructure reliability_

**Evidence**: No dependency auditing found

**Remediation**: Add cargo deny/audit, npm audit, pip-audit, or Snyk to CI as a blocking check.

### [FAIL] Conventional Commits (0/2)

_DORA 2025 - working in small batches_

**Evidence**: No conventional commit enforcement found

**Remediation**: Add commitlint or equivalent to CI to enforce consistent commit message format.

### [FAIL] Unsafe Code Policy (0/3)

_Blog: 80% problem in AI-generated code_

**Evidence**: No explicit policy against unsafe code patterns

**Remediation**: Add unsafe_code = forbid (Rust), security linting (semgrep/bandit), or ESLint rules against dangerous patterns.


## Testing & Stability (6%)

### [PASS] Test Suite (2/3)

_Kent Beck - tests define what correct means_

**Evidence**: Tests found but not confirmed in CI

**Remediation**: Add test execution to your CI pipeline.

### [FAIL] Feature Matrix Testing (0/3)

_DORA 2025 - stability through comprehensive testing_

**Evidence**: Only one test configuration found

**Remediation**: Add CI jobs for different feature flags, environments, or dependency versions (e.g. --all-features, --no-default-features, MSRV check).

### [FAIL] Code Coverage (0/4)

_DORA 2025 - stability feedback loops_

**Evidence**: No code coverage measurement found

**Remediation**: Add cargo llvm-cov, pytest-cov, istanbul/c8, or equivalent to CI. Even informational coverage provides a feedback loop.

### [FAIL] Mutation Testing (0/4)

_SlopCodeBench - code that 'appears correct but is unreliable'_

**Evidence**: No mutation testing found

**Remediation**: Add cargo-mutants (Rust), Stryker (JS/TS), mutmut (Python), or PIT (Java). Mutation testing catches tests that pass without verifying behavior.

### [FAIL] Property-Based Testing (0/3)

_Blog: catching edge cases in AI-generated code_

**Evidence**: No property-based testing found

**Remediation**: Add proptest (Rust), hypothesis (Python), fast-check (JS/TS), or jqwik (Java) for testing invariants with random structured inputs.

### [FAIL] Fuzz Testing (0/3)

_Blog: 80% problem - catching what AI misses_

**Evidence**: No fuzz testing found

**Remediation**: Add fuzz targets for parsing-heavy and input-handling code paths.

### [FAIL] Contract / Compatibility Tests (0/3)

_OpenAI Harness Engineering - mechanical constraints_

**Evidence**: No contract or compatibility tests found

**Remediation**: Add contract tests that verify external interface stability (golden fixtures, snapshot tests, wire-format checks).

### [FAIL] Tests Block Merge (0/2)

_DORA 2025 - stability metrics_

**Evidence**: No test jobs found in CI

**Remediation**: Add test execution to CI as a blocking job.


## Review & Drift Prevention (20%)

### [FAIL] Code Review Required (0/4)

_OpenAI Harness Engineering - author/reviewer separation_

**Evidence**: Cannot verify branch protection without API access. Run with --github-token or --gitlab-token for full assessment.

**Remediation**: Enable required reviews in branch protection settings and add CODEOWNERS.

### [PASS] Scheduled CI Jobs (3/3)

_OpenAI Harness Engineering - garbage collection agents_

**Evidence**: Scheduled CI pipeline found

### [FAIL] Stale Documentation Detection (0/2)

_OpenAI Harness Engineering - quality drift_

**Evidence**: No stale documentation detection found

**Remediation**: Add TODO/FIXME scanning, link checking (lychee), or prose linting (vale) to CI.

### [FAIL] PR/MR Template (0/2)

_DORA 2025 - working in small batches_

**Evidence**: No PR/MR template found

**Remediation**: Add .github/PULL_REQUEST_TEMPLATE.md or .gitlab/merge_request_templates/Default.md with sections for description, testing, and impact.

### [FAIL] Automated Code Review (0/2)

_OpenAI Harness Engineering - separate authoring and reviewing agents_

**Evidence**: No automated review tools found

**Remediation**: Configure CodeRabbit, SonarCloud, Dependabot/Renovate, or equivalent for automated review on every PR/MR.

### [FAIL] Documentation Sync Check (0/2)

_OpenAI Harness Engineering - curated knowledge base_

**Evidence**: No documentation sync checks found in CI

**Remediation**: Add CI jobs that verify related docs stay in sync (e.g. diff AGENTS.md CLAUDE.md, golden fixture checks).


## AI-Specific Safeguards (0%)

### [FAIL] AI Usage Norms (0/4)

_DORA 2025 - clear organizational stance on AI use_

**Evidence**: No AI usage norms documented

**Remediation**: Document AI usage policies: review expectations for AI-generated code, when manual implementation is required, testing-before-implementation norms.

### [FAIL] Small Batch Enforcement (0/3)

_DORA 2025 - working in small batches_

**Evidence**: No small batch enforcement found

**Remediation**: Add PR size checks (Danger, pr-size-labeler) or document size guidelines in CONTRIBUTING.md. Large AI-generated PRs are harder to review.

### [FAIL] Design-Before-Code Culture (0/3)

_Blog: cognitive offloading guardrails_

**Evidence**: No design-before-code process found

**Remediation**: Create docs/rfcs/ or docs/designs/ directory. Document a process where significant changes start with a design doc or plan before implementation.

### [FAIL] Error Handling Policy (0/3)

_Blog: AI agents deleting tests, using expect()_

**Evidence**: No error handling policy found

**Remediation**: Add clippy lints (unwrap_used, expect_used) for Rust, ESLint rules for JS/TS, or document error handling patterns in agent instructions.

### [FAIL] Security-Critical Path Marking (0/2)

_Blog: 80% problem in security infrastructure_

**Evidence**: No security-critical path marking found

**Remediation**: Add CODEOWNERS for sensitive directories, SECURITY.md for vuln reporting, or SAST scanning in CI.


## References

- Blog: 80% problem - catching what AI misses
- Blog: 80% problem in AI-generated code
- Blog: 80% problem in security infrastructure
- Blog: AI agents deleting tests, using expect()
- Blog: catching edge cases in AI-generated code
- Blog: cognitive offloading guardrails
- Blog: security infrastructure reliability
- DORA 2025 - AI-accessible documentation
- DORA 2025 - clear organizational stance on AI use
- DORA 2025 - stability feedback loops
- DORA 2025 - stability metrics
- DORA 2025 - stability through comprehensive testing
- DORA 2025 - working in small batches
- DORA 2025 Report
- DORA 2025 Report - AI-accessible documentation
- Kent Beck - tests define what correct means
- OpenAI Harness Engineering (2026)
- OpenAI Harness Engineering - author/reviewer separation
- OpenAI Harness Engineering - curated knowledge base
- OpenAI Harness Engineering - garbage collection agents
- OpenAI Harness Engineering - mechanical constraints
- OpenAI Harness Engineering - quality drift
- OpenAI Harness Engineering - separate authoring and reviewing agents
- SlopCodeBench - code that 'appears correct but is unreliable'
- SlopCodeBench - preventing subtle type errors
- matklad ARCHITECTURE.md - constraints as absences
- matklad ARCHITECTURE.md guide

---
*Generated by [ai-harness-scorecard](https://github.com/markmishaev/ai-harness-scorecard)*
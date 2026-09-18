---
name: automation-intent
description: Create traceable automation-intent.yaml from test cases, PRDs, prototypes, and ui-knowledge without asset matching, locator generation, or Playwright generation.
metadata:
  short-description: Build traceable UI automation intent YAML
---

# Automation Intent

Use this Skill when the user wants a business test case translated into the formal
`automation-intent.yaml v1.0` intermediate representation.

The Skill consumes Test Case, PRD, Prototype, and existing `ui-knowledge/` assets and
produces `automation-intent.yaml`. Its output describes business intent, semantic UI
context, semantic steps, required capabilities, assertions, evidence, and runtime
unknowns. It is an input to a future Asset Matcher.

## Hard boundary

Do not perform any of the following:

- choose or match an automation asset;
- emit `reuse-plan`, `matched_asset`, `selected_asset`, `reuse_readiness`,
  `effective_reuse_readiness`, or `dependency_closure`;
- generate CSS, XPath, `nth`, `locator(...)`, or any final Locator;
- generate Playwright code;
- explore the browser or turn runtime observations into invented static facts;
- change a business assertion to fit an existing helper or asset.

Read [references/automation-intent-schema.md](references/automation-intent-schema.md)
as the normative field and enum contract before generating or updating an Intent.
Use [templates/automation-intent.example.yaml](templates/automation-intent.example.yaml)
when a complete example is needed, and
[templates/automation-intent.minimal.yaml](templates/automation-intent.minimal.yaml)
for a draft scaffold.

## Inputs and output

Inputs may be supplied inline, as files, or as links already available in the task:

- Test Case: expected business flow and business assertions;
- PRD: business rules and expected outcomes;
- Prototype: intended page/region terminology and visual flow;
- `ui-knowledge/ui-match-index.yaml`: first lookup for page/component/rule semantics;
- `ui-knowledge/runtime-required.yaml`: runtime unknowns and resolution references;
- `ui-knowledge/pages`, `components`, `interaction-rules`, `permissions`: detailed evidence;
- `ui-knowledge` runtime references and human-confirmed facts when explicitly supplied.

By default write `automation-intent.yaml` in the current task workspace, unless the
user specifies another path. If the file already exists, update the matching stable
`intent.id` or `intent.case.id` in place and preserve runtime/human enrichment.

## Required workflow

1. Read the normative reference and inspect the supplied source material. If `ui-knowledge`
   exists, search `ui-match-index.yaml` before opening detailed profile files.
2. Establish the business contract from PRD and Test Case. For business expectations,
   PRD has priority over Test Case. A conflict is recorded as a blocking issue; never
   choose the “most reasonable” interpretation.
3. Resolve semantic page, region, and component references from Prototype plus UI Profile
   evidence. Preserve every Knowledge ID. A UI Profile fact marked `CODE_CONFIRMED` or
   `CODE_INFERRED` is not automatically business `CONFIRMED`.
4. Create the exact top-level shape under `intent`: `id`, `lifecycle`, `case`,
   `eligibility`, `goal`, `test_data`, `preconditions`, `ui_context`, `steps`,
   `required_capabilities`, `assertions`, `knowledge`, `runtime_unknowns`,
   `automation_constraints`, and `validation`.
5. Express each action as a semantic Step. Use business names, anchors, expected types,
   variable references, transitions, capability references, runtime-unknown references,
   and source references. Never put a final Locator in a Step.
6. Add one Required Capability for each reusable ability the future Asset Matcher will
   need. Capabilities describe what is needed in stable semantic `snake_case`; they do
   not name helpers, bug IDs, historical files, or concrete asset IDs. Every required
   Step must reference at least one capability, and every capability must reference a
   Step.
7. Add core Assertions only for business expectations supported by a source reference or
   the business goal. Do not add `SUCCESS_FEEDBACK` merely because source code contains a
   toast. Use `runtime_unknowns` for unresolved close, search, loading, permission, or
   post-action behavior.
8. Separate knowledge into `confirmed`, `inferred`, and `ui_profile_refs`. Inferred
   facts must include `confidence`, `basis`, and
   `must_not_be_treated_as_confirmed: true`. Use only the allowed Source Types from the
   reference; model guesses belong in `knowledge.inferred`, not in `source`.
9. Record unresolved facts as Runtime Unknowns with a question, category, blocking
   decision, priority, affected Steps/Capabilities, UI runtime reference, and a
   preferred resolution. `blocking: true` means the affected Step must not execute
   before resolution; it does not prevent generating the Intent or matching assets.
10. Set `validation.ready_for_asset_matching: true` only when the business goal, at least
    one valid Step, Step-to-Capability coverage, capability references, and at least one
    core business Assertion are complete and there is no requirements-level blocking
    ambiguity. Runtime Unknowns alone do not make it false.
11. Run the lightweight validator when available:
    `python3 scripts/validate_automation_intent.py automation-intent.yaml`.
    Fix structural violations, forbidden Locator syntax, source-type violations, missing
    references, and Secret values before reporting completion.
12. Return the Intent Summary described below.

## Source and conflict rules

Allowed source types are exactly:

`TEST_CASE`, `PRD`, `PROTOTYPE`, `UI_PROFILE`, `UI_PROFILE_RUNTIME_REQUIRED`, `HUMAN`,
`RUNTIME_OBSERVATION`.

Use this precedence for conflicting evidence:

1. Business expectation/rule: PRD, then Test Case; conflict is blocking.
2. Page/region semantics: Prototype plus UI Profile evidence.
3. Implementation-visible facts: UI Profile.
4. Real-page facts: Runtime Observation.
5. Human Confirmed may supplement a business fact but cannot silently override a PRD conflict.

Do not use `MODEL_GUESS` as a source. Record model reasoning as an inferred fact with a
transparent basis. Do not use an `INFRASTRUCTURE` component as a UI Target by default.
Do not treat a variant rule whose activation is `RUNTIME_REQUIRED` as unconditional.

## Data and security rules

Test-data variables use references such as `${customer_name}` and `${target_employee}`.
For `SECRET` variables, write no literal value into the Intent: use `value: null` or an
approved variable reference and keep only a non-secret source description/reference.

## Idempotent updates

When updating an existing Intent:

- match by stable `intent.id` or `case.id`;
- preserve `HUMAN_CONFIRMED`, `RUNTIME_VERIFIED`, and `runtime_enrichment` facts;
- do not silently downgrade verified facts with a new static scan;
- record source conflicts in `validation.conflicts` and/or
  `validation.blocking_issues`;
- do not append duplicate `source_refs` or duplicate Knowledge facts;
- keep the existing stable IDs for Steps, Capabilities, Assertions, and Runtime Unknowns
  when their meaning is unchanged.

## Intent Summary

After generating or updating the file, report:

- `case.id` / `case.name`;
- `eligibility`;
- `step_count`;
- `required_capability_count`;
- `assertion_count`;
- counts of confirmed, inferred, and runtime-unknown facts;
- resolved / partially-resolved / unresolved UI context counts;
- blocking Runtime Unknown count;
- `ready_for_asset_matching`;
- blocking issues and warnings.

The summary is a report only. It must not contain an asset selection or Locator.

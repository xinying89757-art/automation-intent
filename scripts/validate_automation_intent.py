#!/usr/bin/env python3
"""Lightweight structural validator for automation-intent.yaml v1.0."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guidance
    raise SystemExit("PyYAML is required: python3 -m pip install pyyaml") from exc


SOURCE_TYPES = {
    "TEST_CASE",
    "PRD",
    "PROTOTYPE",
    "UI_PROFILE",
    "UI_PROFILE_RUNTIME_REQUIRED",
    "HUMAN",
    "RUNTIME_OBSERVATION",
}
STAGES = {"PRE_RUNTIME", "RUNTIME_ENRICHED", "FINALIZED"}
STATUSES = {"DRAFT", "REVIEWED", "READY_FOR_MATCHING", "BLOCKED", "FINALIZED"}
ELIGIBILITY = {"ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE"}
RESOLUTION = {"RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED"}
KNOWLEDGE_LEVELS = {
    "CONFIRMED",
    "INFERRED",
    "RUNTIME_UNKNOWN",
    "HUMAN_CONFIRMED",
    "RUNTIME_VERIFIED",
}
CAPABILITY_CATEGORIES = {
    "AUTH",
    "NAVIGATION",
    "STATE_SETUP",
    "TEST_DATA",
    "UI_TARGET",
    "UI_INTERACTION",
    "BUSINESS_ACTION",
    "BUSINESS_FLOW",
    "WAIT",
    "ASSERTION",
    "UPLOAD",
    "DOWNLOAD",
    "ENVIRONMENT",
}
ASSERTION_TYPES = {
    "FIELD_VALUE",
    "TEXT",
    "VISIBILITY",
    "PAGE_STATE",
    "DIALOG_STATE",
    "ROW_STATE",
    "URL",
    "COUNT",
    "ENABLED_STATE",
    "SELECTED_STATE",
    "SUCCESS_FEEDBACK",
    "BUSINESS_RESULT",
}
UNKNOWN_CATEGORIES = {
    "PAGE_RESOLUTION",
    "TARGET_RESOLUTION",
    "INTERACTION_BEHAVIOR",
    "DATA_BEHAVIOR",
    "PERMISSION_BEHAVIOR",
    "LOADING_BEHAVIOR",
    "POST_ACTION_BEHAVIOR",
    "IFRAME_BEHAVIOR",
    "OVERLAY_BEHAVIOR",
    "RESPONSIVE_BEHAVIOR",
    "UNKNOWN",
}
PREFERRED_RESOLUTIONS = {
    "UI_EXPLORATION",
    "HUMAN_HINT",
    "HUMAN_DEMO",
    "REQUIREMENT_CONFIRMATION",
    "TEST_DATA_PREPARATION",
}
FORBIDDEN_INTENT_KEYS = {
    "matched_asset",
    "selected_asset",
    "reuse_readiness",
    "effective_reuse_readiness",
    "dependency_closure",
    "reuse-plan",
}
LOCATOR_PATTERN = re.compile(
    r"(?i)(?:\bcss\b|\bxpath\b|\bnth\b|locator\s*\(|dom[_ -]?depth)"
)
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class Validator:
    def __init__(self, document: object):
        self.document = document
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def check(self) -> None:
        if not isinstance(self.document, dict):
            self.error("document must be a mapping")
            return
        if self.document.get("schema_version") != "1.0":
            self.error('schema_version must be "1.0"')
        intent = self.document.get("intent")
        if not isinstance(intent, dict):
            self.error("intent must be a mapping")
            return

        required = {
            "id",
            "lifecycle",
            "case",
            "eligibility",
            "goal",
            "test_data",
            "preconditions",
            "ui_context",
            "steps",
            "required_capabilities",
            "assertions",
            "knowledge",
            "runtime_unknowns",
            "automation_constraints",
            "validation",
        }
        missing = sorted(required - set(intent))
        if missing:
            self.error(f"intent missing required keys: {', '.join(missing)}")
        unexpected = sorted(FORBIDDEN_INTENT_KEYS & set(intent))
        if unexpected:
            self.error(f"Asset Matcher fields are forbidden in intent: {', '.join(unexpected)}")

        self.check_lifecycle(intent.get("lifecycle"))
        self.check_case_eligibility_goal(intent)
        self.check_test_data(intent.get("test_data"))
        self.check_preconditions(intent.get("preconditions"))
        self.check_ui_context(intent.get("ui_context"))
        self.check_steps_capabilities(intent)
        self.check_assertions(intent.get("assertions"))
        self.check_knowledge(intent.get("knowledge"))
        self.check_unknowns(intent.get("runtime_unknowns"))
        self.check_sources(intent)
        self.check_step_locators(intent.get("steps"))
        self.check_readiness(intent)

    def check_lifecycle(self, lifecycle: object) -> None:
        if not isinstance(lifecycle, dict):
            self.error("intent.lifecycle must be a mapping")
            return
        if lifecycle.get("stage") not in STAGES:
            self.error("intent.lifecycle.stage is invalid")
        if lifecycle.get("status") not in STATUSES:
            self.error("intent.lifecycle.status is invalid")

    def check_case_eligibility_goal(self, intent: dict) -> None:
        case = intent.get("case")
        if not isinstance(case, dict):
            self.error("intent.case must be a mapping")
        else:
            for key in ("id", "name", "module", "source_refs"):
                if key not in case:
                    self.error(f"intent.case missing {key}")
        eligibility = intent.get("eligibility")
        if not isinstance(eligibility, dict) or eligibility.get("status") not in ELIGIBILITY:
            self.error("intent.eligibility.status is invalid")
        goal = intent.get("goal")
        if not isinstance(goal, dict) or any(
            not isinstance(goal.get(part), dict) for part in ("actor", "action", "object")
        ) or not goal.get("expected_business_result"):
            self.error("goal must contain actor, action, object, and expected_business_result")

    def check_test_data(self, test_data: object) -> None:
        if not isinstance(test_data, dict):
            self.error("intent.test_data must be a mapping")
            return
        variables = test_data.get("variables", [])
        if not isinstance(variables, list):
            self.error("test_data.variables must be a list")
            return
        for variable in variables:
            if not isinstance(variable, dict):
                self.error("each test-data variable must be a mapping")
                continue
            for key in ("id", "semantic_name", "type", "required", "value", "source", "sensitivity"):
                if key not in variable:
                    self.error(f"test-data variable missing {key}")
            if variable.get("sensitivity") not in {"NORMAL", "SENSITIVE", "SECRET"}:
                self.error(f"invalid sensitivity for variable {variable.get('id')}")
            if variable.get("sensitivity") == "SECRET":
                value = variable.get("value")
                if value is not None and not (isinstance(value, str) and value.startswith("${")):
                    self.error(f"SECRET variable {variable.get('id')} contains a literal value")

    def check_preconditions(self, preconditions: object) -> None:
        if not isinstance(preconditions, list):
            self.error("intent.preconditions must be a list")
            return
        for item in preconditions:
            if not isinstance(item, dict):
                self.error("each precondition must be a mapping")
                continue
            for key in ("id", "statement", "knowledge_level", "source_refs"):
                if key not in item:
                    self.error(f"precondition missing {key}")
            if item.get("knowledge_level") not in KNOWLEDGE_LEVELS:
                self.error(f"invalid precondition knowledge_level: {item.get('id')}")

    def check_ui_context(self, context: object) -> None:
        if not isinstance(context, dict):
            self.error("intent.ui_context must be a mapping")
            return
        for key in ("entry", "target_page", "target_region", "related_components"):
            if key not in context:
                self.error(f"ui_context missing {key}")
        for key in ("target_page", "target_region"):
            value = context.get(key)
            if not isinstance(value, dict) or value.get("resolution_status") not in RESOLUTION:
                self.error(f"ui_context.{key}.resolution_status is invalid")

    def check_steps_capabilities(self, intent: dict) -> None:
        steps = intent.get("steps")
        capabilities = intent.get("required_capabilities")
        if not isinstance(steps, list) or not isinstance(capabilities, list):
            self.error("steps and required_capabilities must be lists")
            return
        step_ids = {item.get("id") for item in steps if isinstance(item, dict)}
        cap_ids = {item.get("id") for item in capabilities if isinstance(item, dict)}
        for step in steps:
            if not isinstance(step, dict):
                self.error("each Step must be a mapping")
                continue
            for key in ("id", "intent", "context", "target", "action", "required_capability_refs", "source_refs"):
                if key not in step:
                    self.error(f"Step {step.get('id')} missing {key}")
            refs = step.get("required_capability_refs", [])
            if not refs:
                self.error(f"Step {step.get('id')} has no Required Capability reference")
            for ref in refs:
                if ref not in cap_ids:
                    self.error(f"Step {step.get('id')} references unknown Capability {ref}")
            for ref in step.get("runtime_unknown_refs", []) or []:
                # checked against unknown IDs after the unknown list is available
                if not isinstance(ref, str):
                    self.error(f"Step {step.get('id')} has invalid runtime unknown reference")
        for cap in capabilities:
            if not isinstance(cap, dict):
                self.error("each Required Capability must be a mapping")
                continue
            for key in ("id", "capability", "semantic_name", "category", "required", "step_refs", "preferred_asset_types", "ui_knowledge_refs"):
                if key not in cap:
                    self.error(f"Capability {cap.get('id')} missing {key}")
            if cap.get("category") not in CAPABILITY_CATEGORIES:
                self.error(f"invalid Capability category: {cap.get('id')}")
            if not isinstance(cap.get("capability"), str) or not SNAKE_CASE.match(cap.get("capability", "")):
                self.error(f"Capability must be semantic snake_case: {cap.get('id')}")
            for ref in cap.get("step_refs", []) or []:
                if ref not in step_ids:
                    self.error(f"Capability {cap.get('id')} references unknown Step {ref}")

    def check_assertions(self, assertions: object) -> None:
        if not isinstance(assertions, list):
            self.error("intent.assertions must be a list")
            return
        for assertion in assertions:
            if not isinstance(assertion, dict):
                self.error("each Assertion must be a mapping")
                continue
            for key in ("id", "type", "target", "expected", "required", "source_refs"):
                if key not in assertion:
                    self.error(f"Assertion {assertion.get('id')} missing {key}")
            if assertion.get("type") not in ASSERTION_TYPES:
                self.error(f"invalid Assertion type: {assertion.get('id')}")

    def check_knowledge(self, knowledge: object) -> None:
        if not isinstance(knowledge, dict):
            self.error("intent.knowledge must be a mapping")
            return
        for key in ("confirmed", "inferred", "ui_profile_refs"):
            if key not in knowledge:
                self.error(f"knowledge missing {key}")
        for fact in knowledge.get("inferred", []) or []:
            if not isinstance(fact, dict):
                self.error("each inferred fact must be a mapping")
                continue
            for key in ("id", "fact", "confidence", "basis", "must_not_be_treated_as_confirmed"):
                if key not in fact:
                    self.error(f"inferred fact {fact.get('id')} missing {key}")
            if fact.get("must_not_be_treated_as_confirmed") is not True:
                self.error(f"inferred fact {fact.get('id')} must explicitly remain unconfirmed")

    def check_unknowns(self, unknowns: object) -> None:
        if not isinstance(unknowns, list):
            self.error("intent.runtime_unknowns must be a list")
            return
        ids = {item.get("id") for item in unknowns if isinstance(item, dict)}
        for unknown in unknowns:
            if not isinstance(unknown, dict):
                self.error("each Runtime Unknown must be a mapping")
                continue
            for key in ("id", "question", "category", "blocking", "priority", "applies_to", "source", "ui_runtime_ref", "preferred_resolution", "status"):
                if key not in unknown:
                    self.error(f"Runtime Unknown {unknown.get('id')} missing {key}")
            if unknown.get("category") not in UNKNOWN_CATEGORIES:
                self.error(f"invalid Runtime Unknown category: {unknown.get('id')}")
            if unknown.get("preferred_resolution") not in PREFERRED_RESOLUTIONS:
                self.error(f"invalid Runtime Unknown resolution: {unknown.get('id')}")
            if unknown.get("status") not in {"OPEN", "RESOLVED"}:
                self.error(f"invalid Runtime Unknown status: {unknown.get('id')}")
        steps = self.document.get("intent", {}).get("steps", [])
        for step in steps:
            for ref in step.get("runtime_unknown_refs", []) or []:
                if ref not in ids:
                    self.error(f"Step {step.get('id')} references unknown Runtime Unknown {ref}")

    def check_sources(self, node: object, path: str = "intent") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"source", "source_refs", "basis"}:
                    self.check_source_value(value, f"{path}.{key}")
                else:
                    self.check_sources(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self.check_sources(value, f"{path}[{index}]")

    def check_source_value(self, value: object, path: str) -> None:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, dict) or "type" not in item:
                continue
            if item.get("type") not in SOURCE_TYPES:
                self.error(f"invalid source type at {path}: {item.get('type')}")

    def check_step_locators(self, steps: object) -> None:
        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}[{index}]")
            elif isinstance(node, str) and LOCATOR_PATTERN.search(node):
                self.error(f"forbidden Locator syntax in Step at {path}")

        walk(steps, "intent.steps")

    def check_readiness(self, intent: dict) -> None:
        validation = intent.get("validation")
        if not isinstance(validation, dict):
            self.error("intent.validation must be a mapping")
            return
        if validation.get("ready_for_asset_matching") is not True:
            return
        if not intent.get("steps"):
            self.error("ready_for_asset_matching=true requires at least one Step")
        if not intent.get("required_capabilities"):
            self.error("ready_for_asset_matching=true requires Required Capabilities")
        if not intent.get("assertions"):
            self.error("ready_for_asset_matching=true requires a core Assertion")
        if validation.get("blocking_issues"):
            self.error("ready_for_asset_matching=true cannot have blocking_issues")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        document = yaml.safe_load(args.path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.path}", file=sys.stderr)
        return 2
    except yaml.YAMLError as exc:
        print(f"ERROR: invalid YAML: {exc}", file=sys.stderr)
        return 2
    validator = Validator(document)
    validator.check()
    if validator.errors:
        for error in validator.errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.path} is a valid automation-intent.yaml v1.0 document")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

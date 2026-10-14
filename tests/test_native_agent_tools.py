"""Offline schema and distribution regressions; no network or platform execution.

Behavioral failure/fallback decisions are evaluated in evals/evals.json, rather
than pretending a test-only classifier proves that prose follows its policy.
"""
import copy
import json
from pathlib import Path
import re
import unittest

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/flowagent"
REFERENCE = Path("helpers/flowagent/native-agent-tools.md")
EXAMPLE = Path("helpers/flowagent/native-agent-example.json")
CONSUMERS = ("flowagent", "flowagent-to-spec", "builder-agent", "solution-arch-agent", "qa-agent")


def read(path):
    return json.loads(path.read_text())


def resolved(value):
    """Stand-ins for schema checks only; never represent these as live IDs."""
    text = json.dumps(value)
    for index, name in enumerate(("profile-id", "model-id", "child-agent-id", "parent-agent-id"), 1):
        text = text.replace(f"<{name}>", f"00000000-0000-4000-8000-{index:012d}")
    return json.loads(text)


class NativeAgentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = read(ROOT / EXAMPLE)
        cls.schemas = read(FIXTURES / "schemas.json")
        cls.tool = read(FIXTURES / "agent-tool.json")["tool"]

    def validate(self, schema, value):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(resolved(value))

    def test_example_bodies_match_captured_request_schemas(self):
        for key, schema in (("childCreate", "agentCreate"), ("parentCreate", "agentCreate"),
                            ("parentAddTools", "agentUpdate"), ("parentSessionStart", "sessionStart")):
            with self.subTest(body=key):
                self.validate(self.schemas[schema], self.example[key])

    def test_native_binding_resolves_to_active_agent_tool(self):
        self.assertEqual(self.tool["type"], "agent")
        self.assertTrue(self.tool["active"])
        self.assertEqual(self.tool["parentType"], "agentProject")
        binding = {"referenceId": self.tool["referenceId"]}
        self.assertEqual(self.example["parentCreate"]["tools"], [binding])
        self.assertEqual(self.example["parentAddTools"]["addTools"], [binding])
        self.assertEqual(self.example["childCreate"]["tools"], [])

    def test_child_schema_is_exposed_directly_and_inputs_match(self):
        exposed = {k: v for k, v in self.tool["inputSchema"].items() if k != "$schema"}
        self.assertEqual(self.example["childCreate"]["inputSchema"], exposed)
        self.validate(self.tool["inputSchema"], self.example["childToolInput"])
        self.validate(self.example["parentCreate"]["inputSchema"], self.example["parentSessionStart"]["inputs"])
        for key in ("childCreate", "parentCreate"):
            body = self.example[key]
            variables = set(re.findall(r"{{\s*(\w+)\s*}}", body["instructions"]))
            self.assertEqual(variables, set(body["inputSchema"]["properties"]))

    def test_rejects_session_wrapper_wrong_type_missing_and_extra_child_fields(self):
        invalid = ({"inputs": self.example["childToolInput"]}, {"context": {}}, {},
                   {"context": "observation", "approval": True})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.validate(self.tool["inputSchema"], value)

    def test_rejects_invented_binding_fields_and_invalid_provider_ids(self):
        invalid = copy.deepcopy(self.example["parentCreate"])
        invalid["tools"][0]["agentId"] = "<child-agent-id>"
        with self.assertRaises(ValidationError):
            self.validate(self.schemas["agentCreate"], invalid)
        invalid = copy.deepcopy(self.example["parentCreate"])
        invalid["provider"]["profile"] = "a-display-name-is-not-a-uuid"
        with self.assertRaises(ValidationError):
            self.validate(self.schemas["agentCreate"], invalid)

    def test_update_delta_does_not_copy_create_only_tool_metadata(self):
        invalid = copy.deepcopy(self.example["parentAddTools"])
        invalid["addTools"][0]["lastKnownName"] = "Observation Summarizer"
        with self.assertRaises(ValidationError):
            self.validate(self.schemas["agentUpdate"], invalid)

    def test_halt_fixture_preserves_correlation_and_separate_outcomes(self):
        fixture = read(FIXTURES / "completed-halt.json")
        call = fixture["parentEvent"]["data"]
        child = fixture["childSession"]
        self.assertEqual(call["output"]["sessionId"], child["sessionId"])
        self.assertEqual(call["output"]["sessionStatus"], child["status"])
        self.assertEqual(call["output"]["lastMessage"], fixture["childConclusion"])
        self.assertEqual(call["status"], "succeeded")
        self.assertEqual(child["status"], "COMPLETE")
        self.assertTrue(fixture["childConclusion"].startswith("STOPPED"))
        self.validate(self.schemas["sessionStatus"], child["status"])
        self.validate(self.tool["inputSchema"], call["input"])

    def test_raw_outcome_event_correlates_and_resolves_to_the_same_child_result(self):
        fixture = read(FIXTURES / "completed-halt.json")
        row, raw = fixture["parentEvent"], fixture["rawOutcome"]
        self.assertEqual(row["sessionId"], raw["sessionId"])
        self.assertEqual(row["data"]["outcomeEventId"], raw["eventId"])
        self.assertEqual(row["data"]["toolCallId"], raw["data"]["toolCallId"])
        self.assertEqual(raw["type"], "tool-execution-succeeded")
        self.assertEqual(raw["data"]["toolOutput"]["kind"], "resolved")
        self.assertEqual(raw["data"]["toolOutput"]["payload"], row["data"]["output"])


class NativeAgentDistributionTests(unittest.TestCase):
    def test_every_consumer_has_identical_shared_reference_in_its_package(self):
        for skill in CONSUMERS:
            with self.subTest(skill=skill):
                folder = ROOT / "skills" / skill
                relative = Path("assets") / REFERENCE
                self.assertIn(str(relative), (folder / "SKILL.md").read_text())
                self.assertEqual((folder / relative).read_bytes(), (ROOT / REFERENCE).read_bytes())
        for skill in CONSUMERS:
            self.assertEqual((ROOT / "skills" / skill / "assets" / EXAMPLE).read_bytes(),
                             (ROOT / EXAMPLE).read_bytes())

    def test_all_harness_manifests_resolve_to_the_shared_skills(self):
        for manifest in ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json"):
            data = read(ROOT / manifest)
            self.assertEqual(data["name"], "itential-builder")
            self.assertEqual(data.get("skills", "./skills/"), "./skills/")
        for marketplace in (".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json"):
            plugin = read(ROOT / marketplace)["plugins"][0]
            self.assertEqual((ROOT / plugin["source"]).resolve(), ROOT)
        source = read(ROOT / ".agents/plugins/marketplace.json")["plugins"][0]["source"]
        self.assertEqual(source["source"], "local")
        self.assertEqual((ROOT / source["path"]).resolve(), ROOT)

    def test_no_blanket_denial_in_any_distributed_skill(self):
        # Supplemental prose guard; schema/packaging checks and behavioral evals
        # above are the primary regression coverage.
        denial = re.compile(r"(?:agent.to.agent delegation|sub.agents / delegation) is not (?:a supported field|supported)", re.I)
        for path in (ROOT / "skills").rglob("*.md"):
            self.assertIsNone(denial.search(path.read_text()), str(path))


if __name__ == "__main__":
    unittest.main()

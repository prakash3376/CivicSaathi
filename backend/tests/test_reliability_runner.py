"""The release gate must not lie: a step that ran nothing, could not run, or failed is never a pass."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reliability.py"


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reliability_gate", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def result(gate: ModuleType, status: str, priority: str = "P1") -> object:
    return gate.Result("x", "g", "t", priority, status)


class TestTheVerdict:
    def test_every_critical_step_passing_is_release_ready(self, gate: ModuleType) -> None:
        results = [result(gate, "PASS", "P0"), result(gate, "PASS", "P1")]

        assert gate.verdict(results) == "RELEASE-READY"

    def test_a_failed_critical_step_is_never_release_ready(self, gate: ModuleType) -> None:
        for priority in ("P0", "P1"):
            results = [result(gate, "PASS"), result(gate, "FAIL", priority)]

            assert gate.verdict(results) == "NOT RELEASE-READY"

    def test_a_failed_minor_step_does_not_block_but_a_critical_gap_does(
        self, gate: ModuleType
    ) -> None:
        assert gate.verdict([result(gate, "PASS"), result(gate, "FAIL", "P3")]) == "RELEASE-READY"
        for status in ("BLOCKED", "NOT TESTED"):
            assert gate.verdict([result(gate, "PASS"), result(gate, status, "P0")]) == "INCOMPLETE"

    def test_a_degraded_critical_step_passes_but_is_not_hidden(self, gate: ModuleType) -> None:
        assert gate.verdict([result(gate, "DEGRADED", "P1")]) == "RELEASE-READY"

    def test_a_feature_that_does_not_exist_is_listed_but_does_not_count(
        self, gate: ModuleType
    ) -> None:
        results = [result(gate, "PASS", "P0"), result(gate, "NOT TESTED", "N/A")]

        assert gate.verdict(results) == "RELEASE-READY"
        assert results[1].status == "NOT TESTED"  # and never shown as a pass


class TestWhatCountsAsAPass:
    def test_a_test_run_that_ran_no_tests_is_a_failure(self, gate: ModuleType) -> None:
        assert gate.pytest_result(0, "no tests ran in 0.01s")[0] == "FAIL"
        assert gate.pytest_result(0, "0 passed in 0.01s")[0] == "FAIL"

    def test_passing_tests_pass_and_a_failing_exit_fails(self, gate: ModuleType) -> None:
        assert gate.pytest_result(0, "120 passed in 80s") == ("PASS", "120 passed in 80s")
        assert gate.pytest_result(1, "1 failed, 5 passed in 3s")[0] == "FAIL"

    def test_warnings_make_a_passing_check_degraded(self, gate: ModuleType) -> None:
        line = "69 programmes, 49 budget records; 3 warnings. Nothing was changed."

        assert gate.warnings_count(0, line)[0] == "DEGRADED"
        assert gate.warnings_count(0, "0 errors, 0 warnings.")[0] == "PASS"
        assert gate.warnings_count(1, "1 errors, 0 warnings.")[0] == "FAIL"

    def test_a_missing_tool_is_blocked_not_passed(self, gate: ModuleType) -> None:
        step = gate.Step("t", "g", "title", "P1", ["x"], blocked=lambda: "npm is not installed")

        outcome = gate.execute(step)

        assert (outcome.status, outcome.detail) == ("BLOCKED", "npm is not installed")

    def test_a_step_not_run_in_this_mode_says_why(self, gate: ModuleType) -> None:
        outcome = gate.execute(gate.Step("t", "g", "title", "P2", skip="run with --live"))

        assert (outcome.status, outcome.detail) == ("NOT TESTED", "run with --live")

    def test_a_command_that_cannot_start_is_blocked(self, gate: ModuleType) -> None:
        step = gate.Step("t", "g", "title", "P1", ["definitely-not-a-real-command-xyz"])

        assert gate.execute(step).status == "BLOCKED"

    def test_a_key_shaped_string_in_the_source_fails_the_secret_scan(
        self, gate: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "leak.py").write_text('KEY = "AIza' + "x" * 35 + '"')
        monkeypatch.setattr(gate, "BACKEND", tmp_path)
        monkeypatch.setattr(gate, "FRONTEND", tmp_path / "fe")
        monkeypatch.setattr(gate, "ROOT", tmp_path)

        status, detail = gate.scan_for_secrets()

        assert status == "FAIL"
        assert "leak.py" in detail
        assert "AIza" not in detail  # the finding names the file, never the key


class TestThePlan:
    def test_the_features_that_do_not_exist_are_marked_not_applicable_in_the_real_plan(
        self, gate: ModuleType
    ) -> None:
        import argparse

        args = argparse.Namespace(
            browser=False, live=False, only=None, chrome=None, node_modules=None
        )

        steps = {step.id: step for step in gate.plan(args)}

        for name in ("uploads", "accounts", "sql"):
            assert steps[name].priority == "N/A"
            assert steps[name].skip  # each says why it is not run

    def test_every_critical_step_in_the_real_plan_actually_runs_something_or_says_why(
        self, gate: ModuleType
    ) -> None:
        import argparse

        args = argparse.Namespace(
            browser=False, live=False, only=None, chrome=None, node_modules=None
        )

        for step in gate.plan(args):
            if step.priority in {"P0", "P1"} and not step.skip:
                assert step.command is not None or step.id in {"secrets", "journey", "resilience"}

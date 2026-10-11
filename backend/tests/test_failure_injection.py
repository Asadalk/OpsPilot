"""Phase 34: every failure-injection case has a deterministic, stored outcome."""
import os

from app.demo.failures import CASES, run_cases


def test_every_failure_case_behaves_as_expected():
    url = os.environ["DATABASE_URL"].rsplit("/", 1)[0] + "/opspilot_failures_test_bench"
    results = run_cases(["all"], url)
    assert [row["case"] for row in results] == [case.name for case in CASES]
    failed = [row for row in results if not row["passed"]]
    assert not failed, failed

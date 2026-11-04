from toolbr.gate import grader_checks


def test_oracle_100_and_naive_at_most_10_percent():
    checks = grader_checks(["loop"])
    assert all(c.ok for c in checks), [(c.name, c.detail) for c in checks]

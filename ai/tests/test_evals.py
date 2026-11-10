"""The eval dataset is part of the CI gate: pytest runs the offline runner."""

from evals.runner import main


def test_offline_eval_dataset_passes() -> None:
    assert main([]) == 0

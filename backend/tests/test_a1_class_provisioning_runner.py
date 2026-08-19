import importlib.util
from pathlib import Path


def _runner_module():
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_a1_class_provisioning_e2e.py"
    )
    spec = importlib.util.spec_from_file_location(
        "a1_class_provisioning_runner", script
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_error_message_reads_the_canonical_api_envelope():
    runner = _runner_module()
    assert hasattr(runner, "error_message")
    assert (
        runner.error_message(
            {
                "error": {
                    "type": "http_error",
                    "message": "Class already exists.",
                    "detail": None,
                }
            }
        )
        == "Class already exists."
    )

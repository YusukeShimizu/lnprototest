from typing import Any, cast

import pytest
import pyln.spec.bolt1

from lnprototest import Runner, RunnerConn


def test_runnerconn_init_exchange(runner: Runner, namespaceoverride: Any) -> None:
    """Procedural spike: verify a connection handle can drive a minimal init flow."""
    namespaceoverride(pyln.spec.bolt1.namespace)

    if runner._is_dummy():
        pytest.skip("RunnerConn procedural spike requires a real runner")

    runner.start()
    try:
        conn = cast(RunnerConn, runner.connect(cast(Any, None), connprivkey="03"))
        init_msg = conn.recv_msg()
        assert (
            init_msg.messagetype.name == "init"
        ), f"received not an init msg but: {init_msg.to_str()}"
        conn.send_msg(
            "init",
            globalfeatures=runner.runner_features(globals=True),
            features=runner.runner_features(),
        )
    finally:
        runner.stop()

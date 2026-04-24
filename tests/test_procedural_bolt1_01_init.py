import pyln.spec.bolt1

from lnprototest import Runner


def test_procedural_echo_init(runner: Runner, namespaceoverride) -> None:
    namespaceoverride(pyln.spec.bolt1.namespace)

    runner.start()
    try:
        conn = runner.connect(connprivkey="03")
        init = conn.recv_msg()
        assert init.messagetype.name == "init"
        conn.send_msg(
            "init",
            globalfeatures=runner.runner_features(globals=True),
            features=runner.runner_features(),
        )
    finally:
        runner.stop()


def test_procedural_echo_init_reconnect(runner: Runner, namespaceoverride) -> None:
    namespaceoverride(pyln.spec.bolt1.namespace)

    runner.start()
    try:
        conn = runner.connect(connprivkey="03")
        init = conn.recv_msg()
        assert init.messagetype.name == "init"
        conn.send_msg(
            "init",
            globalfeatures=runner.runner_features(globals=True),
            features=runner.runner_features(),
        )

        conn.disconnect()
        conn = runner.connect(connprivkey="02")
        init = conn.recv_msg()
        assert init.messagetype.name == "init"
        conn.send_msg(
            "init",
            globalfeatures=init.fields["globalfeatures"],
            features=init.fields["features"],
        )
    finally:
        runner.stop()

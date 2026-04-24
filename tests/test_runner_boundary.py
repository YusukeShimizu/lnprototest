from typing import Any, List, Optional

import io
from pyln.proto.message import Message

from lnprototest.boundary import (
    CapabilityLevel,
    CapabilitySet,
    ChainBackend,
    NodeAdapter,
    PeerSession,
)
from lnprototest.namespace import namespace
from lnprototest.runner import Runner


def encode_msg(msg_name: str, **kwargs: Any) -> bytes:
    msg = Message(namespace().get_msgtype(msg_name), **kwargs)
    binmsg = io.BytesIO()
    msg.write(binmsg)
    return binmsg.getvalue()


class FakeConfig:
    def getoption(self, name: str) -> Any:
        if name == "verbose":
            return False
        if name == "runner_args":
            return []
        raise KeyError(name)


class FakeSession(PeerSession):
    def __init__(self, connprivkey: str):
        super().__init__(connprivkey)
        self.sent: List[bytes] = []
        self.closed = False
        self.queue: List[bytes] = [encode_msg("init", globalfeatures="", features="")]

    def send_raw(self, payload: bytes) -> None:
        self.sent.append(payload)

    def recv_raw(self, timeout: Optional[int] = None) -> bytes:
        return self.queue.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeChainBackend(ChainBackend):
    def __init__(self):
        self.height = 7
        self.started = False
        self.expected: List[str] = []
        self.unexpected: List[str] = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def restart(self) -> None:
        self.height = 7
        self.started = True

    def block_height(self) -> int:
        return self.height

    def trim_blocks(self, newheight: int) -> None:
        self.height = newheight

    def mine_blocks(self, event: Any, txs: List[str], n: int) -> None:
        self.height += n

    def expect_tx(self, event: Any, txid: str) -> None:
        self.expected.append(txid)

    def expect_no_tx(self, event: Any, txid: str) -> None:
        self.unexpected.append(txid)


class FakeNodeAdapter(NodeAdapter):
    def __init__(self):
        self.running = False
        self.flags: List[str] = []
        self.sessions: List[FakeSession] = []
        self.capability_set = CapabilitySet()
        self.capability_set.set_protocol(
            "option_anchor_outputs", CapabilityLevel.SUPPORTED
        )
        self.capability_set.set_extension("supports_open_accept_channel_type", True)

    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.running = True

    def stop(self, print_logs: bool = False) -> None:
        self.running = False

    def restart(self) -> None:
        self.running = True

    def open_session(self, connprivkey: str) -> PeerSession:
        session = FakeSession(connprivkey)
        self.sessions.append(session)
        return session

    def capabilities(self) -> CapabilitySet:
        return self.capability_set

    def legacy_get_keyset(self):
        raise NotImplementedError

    def legacy_get_node_privkey(self) -> str:
        return "01"

    def legacy_get_node_bitcoinkey(self) -> str:
        return "10"

    def legacy_add_startup_flag(self, flag: str) -> None:
        self.flags.append(flag)

    def legacy_invoice(self, event: Any, amount: int, preimage: str) -> None:
        return

    def legacy_accept_add_fund(self, event: Any) -> None:
        return

    def legacy_fundchannel(
        self,
        event: Any,
        conn: PeerSession,
        amount: int,
        feerate: int = 253,
        expect_fail: bool = False,
    ) -> None:
        return

    def legacy_init_rbf(
        self,
        event: Any,
        conn: PeerSession,
        channel_id: str,
        amount: int,
        utxo_txid: str,
        utxo_outnum: int,
        feerate: int,
    ) -> None:
        return

    def legacy_addhtlc(
        self, event: Any, conn: PeerSession, amount: int, preimage: str
    ) -> None:
        return

    def legacy_close_channel(self, channel_id: str) -> None:
        return


class FakeRunner(Runner):
    def __init__(self):
        super().__init__(FakeConfig())
        self.chain = FakeChainBackend()
        self.node = FakeNodeAdapter()


def test_capability_set_preserves_legacy_queries() -> None:
    capabilities = CapabilitySet.from_cln_feature_lines(
        [
            "option_data_loss_protect/even",
            "option_anchor_outputs/odd",
            "supports_open_accept_channel_type",
        ]
    )

    assert capabilities.legacy_has_option("option_data_loss_protect") == "even"
    assert capabilities.legacy_has_option("option_anchor_outputs") == "odd"
    assert capabilities.legacy_has_option("supports_open_accept_channel_type") == "true"
    assert capabilities.legacy_has_option("missing_feature") is None


def test_legacy_runner_adapter_delegates_boundary_components() -> None:
    runner = FakeRunner()
    runner.start()
    conn = runner.connect(None, "03")

    runner.recv(None, conn, b"hello")
    assert conn.sent == [b"hello"]
    assert runner.get_output_message(conn, None) == encode_msg(
        "init", globalfeatures="", features=""
    )
    assert runner.getblockheight() == 7

    runner.add_blocks(None, [], 2)
    assert runner.getblockheight() == 9
    runner.expect_tx(None, "txid-a")
    runner.expect_no_tx(None, "txid-b")
    assert runner.chain.expected == ["txid-a"]
    assert runner.chain.unexpected == ["txid-b"]
    assert runner.has_option("option_anchor_outputs") == "odd"
    assert runner.has_option("supports_open_accept_channel_type") == "true"

    runner.disconnect(None, conn)
    assert conn.closed is True


def test_procedural_connect_and_session_convenience_delegate() -> None:
    runner = FakeRunner()
    conn = runner.connect(connprivkey="03")

    assert isinstance(conn, PeerSession)
    conn.send("init", globalfeatures="", features="")
    assert conn.sent == [encode_msg("init", globalfeatures="", features="")]

    msg = conn.recv()
    assert msg.messagetype.name == "init"

    conn.disconnect()
    assert conn.closed is True


def test_multi_session_boundary_keeps_session_state_isolated() -> None:
    runner = FakeRunner()
    conn05 = runner.connect(connprivkey="05")
    conn06 = runner.connect(connprivkey="06")

    assert runner.find_conn("05") is conn05
    assert runner.find_conn("06") is conn06
    assert conn05 is not conn06

    runner.recv(None, conn05, b"from-node-to-05")
    runner.recv(None, conn06, b"from-node-to-06")
    assert conn05.sent == [b"from-node-to-05"]
    assert conn06.sent == [b"from-node-to-06"]

    msg05 = conn05.recv()
    msg06 = conn06.recv()
    assert conn05.get_stash(None, "init") is msg05
    assert conn06.get_stash(None, "init") is msg06
    assert conn05.stash is not conn06.stash

    runner.disconnect(None, conn05)
    assert conn05.closed is True
    assert runner.find_conn("05") is None
    assert runner.find_conn("06") is conn06
    assert conn06.closed is False


def test_legacy_connect_signature_still_works() -> None:
    runner = FakeRunner()
    conn = runner.connect(None, "03")

    assert conn is runner.find_conn("03")

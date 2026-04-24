#! /usr/bin/python3
# #### Dummy runner which you should replace with real one. ####
import io

from typing import Any, List, Optional

from pyln.proto.message import (
    DynamicArrayType,
    EllipsisArrayType,
    FieldType,
    Message,
    SizedArrayType,
)

from .boundary import CapabilitySet, ChainBackend, NodeAdapter, PeerSession
from .event import Event, ExpectMsg, MustNotMsg
from .keyset import KeySet
from .namespace import namespace
from .runner import Conn, Runner


class DummyPeerSession(PeerSession):
    def __init__(self, connprivkey: str, verbose: bool = False):
        super().__init__(connprivkey)
        self.verbose = verbose
        self.recv_queue: List[bytes] = []

    def send_raw(self, payload: bytes) -> None:
        if self.verbose:
            print("[RECV {}]".format(payload.hex()))

    def recv_raw(self, timeout: Optional[int] = None) -> bytes:
        if not self.recv_queue:
            msg = Message(
                namespace().get_msgtype("init"), globalfeatures="", features=""
            )
            binmsg = io.BytesIO()
            msg.write(binmsg)
            self.recv_queue.append(binmsg.getvalue())
        return self.recv_queue.pop(0)

    def close(self) -> None:
        if self.verbose:
            print("[CLOSE {}]".format(self))


class DummyChainBackend(ChainBackend):
    def __init__(self, config: Any):
        self.config = config
        self.blockheight = 102

    def start(self) -> None:
        self.blockheight = 102

    def stop(self) -> None:
        return

    def restart(self) -> None:
        self.blockheight = 102

    def block_height(self) -> int:
        return self.blockheight

    def trim_blocks(self, newheight: int) -> None:
        if self.config.getoption("verbose"):
            print("[TRIMBLOCK TO HEIGHT {}]".format(newheight))
        self.blockheight = newheight

    def mine_blocks(self, event: Event, txs: List[str], n: int) -> None:
        if self.config.getoption("verbose"):
            print("[ADDBLOCKS {} WITH {} TXS]".format(n, len(txs)))
        self.blockheight += n

    def expect_tx(self, event: Event, txid: str) -> None:
        if self.config.getoption("verbose"):
            print("[EXPECT-TX {}]".format(txid))

    def expect_no_tx(self, event: Event, txid: str) -> None:
        if self.config.getoption("verbose"):
            print("[EXPECT-NO-TX {}]".format(txid))


class DummyNodeAdapter(NodeAdapter):
    def __init__(self, config: Any):
        self.config = config
        self.running = False
        self._capabilities = CapabilitySet()

    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.running = True

    def stop(self, print_logs: bool = False) -> None:
        self.running = False

    def restart(self) -> None:
        self.running = True

    def open_session(self, connprivkey: str) -> PeerSession:
        return DummyPeerSession(
            connprivkey, verbose=bool(self.config.getoption("verbose"))
        )

    def capabilities(self) -> CapabilitySet:
        return self._capabilities

    def legacy_get_keyset(self) -> KeySet:
        return KeySet(
            revocation_base_secret="11",
            payment_base_secret="12",
            htlc_base_secret="14",
            delayed_payment_base_secret="13",
            shachain_seed="FF" * 32,
        )

    def legacy_add_startup_flag(self, flag: str) -> None:
        if self.config.getoption("verbose"):
            print("[ADD STARTUP FLAG {}]".format(flag))

    def legacy_get_node_privkey(self) -> str:
        return "01"

    def legacy_get_node_bitcoinkey(self) -> str:
        return "10"

    def legacy_fundchannel(
        self,
        event: Event,
        conn: Conn,
        amount: int,
        feerate: int = 253,
        expect_fail: bool = False,
    ) -> None:
        if self.config.getoption("verbose"):
            print(
                "[FUNDCHANNEL TO {} for {} at feerate {}. Expect fail? {}]".format(
                    conn, amount, feerate, expect_fail
                )
            )

    def legacy_init_rbf(
        self,
        event: Event,
        conn: Conn,
        channel_id: str,
        amount: int,
        utxo_txid: str,
        utxo_outnum: int,
        feerate: int,
    ) -> None:
        if self.config.getoption("verbose"):
            print(
                "[INIT_RBF TO {} (channel {}) for {} at feerate {}. {}:{}".format(
                    conn, channel_id, amount, feerate, utxo_txid, utxo_outnum
                )
            )

    def legacy_invoice(self, event: Event, amount: int, preimage: str) -> None:
        if self.config.getoption("verbose"):
            print("[INVOICE for {} with PREIMAGE {}]".format(amount, preimage))

    def legacy_accept_add_fund(self, event: Event) -> None:
        if self.config.getoption("verbose"):
            print("[ACCEPT_ADD_FUND]")

    def legacy_addhtlc(
        self, event: Event, conn: Conn, amount: int, preimage: str
    ) -> None:
        if self.config.getoption("verbose"):
            print(
                "[ADDHTLC TO {} for {} with PREIMAGE {}]".format(conn, amount, preimage)
            )

    def legacy_close_channel(self, channel_id: str) -> None:
        if self.config.getoption("verbose"):
            print("[CLOSE-CHANNEL {}]".format(channel_id))


class DummyRunner(Runner):
    def __init__(self, config: Any):
        super().__init__(config)
        self.chain = DummyChainBackend(config)
        self.node = DummyNodeAdapter(config)

    def _is_dummy(self) -> bool:
        return True

    def restart(self) -> None:
        super().restart()
        if self.config.getoption("verbose"):
            print("[RESTART]")

    def connect(
        self, event: Optional[Event] = None, connprivkey: Optional[str] = None
    ) -> Conn:
        if connprivkey is None and isinstance(event, str):
            printable_event = None
            printable_connprivkey = event
        else:
            printable_event = event
            printable_connprivkey = connprivkey
        if self.config.getoption("verbose"):
            print("[CONNECT {} {}]".format(printable_event, printable_connprivkey))
        return super().connect(event, connprivkey)

    def disconnect(self, event: Event, conn: Conn) -> None:
        super().disconnect(event, conn)
        if self.config.getoption("verbose"):
            print("[DISCONNECT {}]".format(conn))

    def recv(self, event: Event, conn: Conn, outbuf: bytes) -> None:
        if self.config.getoption("verbose"):
            print("[RECV {} {}]".format(event, outbuf.hex()))
        super().recv(event, conn, outbuf)

    @staticmethod
    def fake_field(ftype: FieldType) -> str:
        if isinstance(ftype, DynamicArrayType) or isinstance(ftype, EllipsisArrayType):
            if ftype.elemtype.name == "byte":
                return ""
            return "[]"
        if isinstance(ftype, SizedArrayType):
            if ftype.elemtype.name == "byte":
                return "00" * ftype.arraysize
            return (
                "["
                + ",".join([DummyRunner.fake_field(ftype.elemtype)] * ftype.arraysize)
                + "]"
            )
        if ftype.name in (
            "byte",
            "u8",
            "u16",
            "u32",
            "u64",
            "tu16",
            "tu32",
            "tu64",
            "bigsize",
            "varint",
        ):
            return "0"
        if ftype.name in ("chain_hash", "channel_id", "sha256"):
            return "00" * 32
        if ftype.name == "point":
            return "038f1573b4238a986470d250ce87c7a91257b6ba3baf2a0b14380c4e1e532c209d"
        if ftype.name == "short_channel_id":
            return "0x0x0"
        if ftype.name == "signature":
            return "01" * 64
        raise NotImplementedError("don't know how to fake {} type!".format(ftype.name))

    def get_output_message(self, conn: Conn, event: ExpectMsg) -> bytes:
        if self.config.getoption("verbose"):
            print("[GET_OUTPUT_MESSAGE {}]".format(conn))

        msg = Message(event.msgtype, **event.resolve_args(self, event.kwargs))
        for missing_field in msg.missing_fields():
            field_type = msg.messagetype.find_field(missing_field.name)
            msg.set_field(missing_field.name, self.fake_field(field_type.fieldtype))

        binmsg = io.BytesIO()
        msg.write(binmsg)
        return binmsg.getvalue()

    def check_error(self, event: Event, conn: Conn) -> str:
        super().check_error(event, conn)
        if self.config.getoption("verbose"):
            print("[CHECK-ERROR {}]".format(event))
        return "Dummy error"

    def check_final_error(
        self,
        event: Event,
        conn: Conn,
        expected: bool,
        must_not_events: List[MustNotMsg],
    ) -> None:
        pass

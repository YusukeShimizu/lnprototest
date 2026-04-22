#! /usr/bin/python3
import functools
import logging
import shutil
import tempfile

import coincurve

from typing import Any, Callable, Dict, List, Optional, Union

from .bitfield import bitfield
from .boundary import ChainBackend, NodeAdapter, PeerSession
from .errors import SpecFileError
from .event import Event, ExpectMsg
from .keyset import KeySet
from .structure import Sequence
from .utils import privkey_expand


Conn = PeerSession
RunnerConn = PeerSession


class LegacyRunnerAdapter:
    """Compatibility layer that keeps the Event DSL running on top of the new boundary."""

    def __init__(self, config: Any):
        self.config = config
        self.directory = tempfile.mkdtemp(prefix="lnpt-cl-")
        self.conns: Dict[str, Conn] = {}
        self.last_conn: Optional[Conn] = None
        self.stash: Dict[str, Dict[str, Any]] = {}
        self.node: Optional[NodeAdapter] = None
        self.chain: Optional[ChainBackend] = None
        self.logger = logging.getLogger(__name__)
        if self.config.getoption("verbose"):
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

    def _is_dummy(self) -> bool:
        return False

    def _node(self) -> NodeAdapter:
        if self.node is None:
            raise RuntimeError("node adapter is not configured")
        return self.node

    def _chain(self) -> ChainBackend:
        if self.chain is None:
            raise RuntimeError("chain backend is not configured")
        return self.chain

    def find_conn(self, connprivkey: Optional[str]) -> Optional[Conn]:
        if connprivkey is None:
            return self.last_conn
        if connprivkey in self.conns:
            self.last_conn = self.conns[connprivkey]
            return self.last_conn
        return None

    def add_conn(self, conn: Conn) -> None:
        self.conns[conn.name] = conn
        self.last_conn = conn

    def disconnect(self, event: Event, conn: Conn) -> None:
        if conn is None:
            raise SpecFileError(event, "Unknown conn")
        del self.conns[conn.name]
        self.check_final_error(event, conn, conn.expected_error, conn.must_not_events)

    def check_error(self, event: Event, conn: Conn) -> Optional[str]:
        conn.expected_error = True
        return None

    def post_check(self, sequence: Sequence) -> None:
        for conn_name in list(self.conns.keys()):
            logging.debug(
                f"disconnection connection with key={conn_name} and value={self.conns[conn_name]}"
            )
            self.disconnect(sequence, self.conns[conn_name])

    def _close_connections(self) -> None:
        for conn in list(self.conns.values()):
            try:
                conn.close()
            except Exception as ex:
                logging.debug(f"ignoring connection close failure: {ex}")

    def restart(self) -> None:
        self._close_connections()
        self.conns = {}
        self.last_conn = None
        self.stash = {}
        if self._node().is_running():
            self._node().stop()
        self._chain().restart()
        self._node().start()

    def run(self, events: Union[Sequence, List[Event], Event]) -> None:
        sequence = Sequence(events)
        self.start()
        while True:
            all_done = sequence.action(self)
            self.post_check(sequence)
            if all_done:
                self.stop()
                return
            self.restart()

    def add_stash(self, stashname: str, vals: Any) -> None:
        self.stash[stashname] = vals

    def get_stash(self, event: Event, stashname: str, default: Any = None) -> Any:
        if stashname not in self.stash:
            if default is not None:
                return default
            raise SpecFileError(event, "Unknown stash name {}".format(stashname))
        return self.stash[stashname]

    def teardown(self) -> None:
        self._node().teardown()
        self._chain().teardown()
        shutil.rmtree(self.directory, ignore_errors=True)

    def runner_features(
        self,
        additional_features: Optional[List[int]] = None,
        globals: bool = False,
    ) -> str:
        if additional_features is None:
            return ""
        return bitfield(*additional_features)

    def is_running(self) -> bool:
        return self._node().is_running()

    def connect(self, event: Event, connprivkey: str) -> Conn:
        conn = self._node().open_session(connprivkey)
        self.add_conn(conn)
        return conn

    def start(self) -> None:
        self._chain().start()
        self._node().start()

    def stop(self, print_logs: bool = False) -> None:
        self._close_connections()
        if self._node().is_running():
            self._node().stop(print_logs=print_logs)
        self._chain().stop()

    def recv(self, event: Event, conn: Conn, outbuf: bytes) -> None:
        conn.send_raw(outbuf)

    def get_output_message(self, conn: Conn, event: ExpectMsg) -> Optional[bytes]:
        return conn.recv_raw()

    def getblockheight(self) -> int:
        return self._chain().block_height()

    def trim_blocks(self, newheight: int) -> None:
        self._chain().trim_blocks(newheight)

    def add_blocks(self, event: Event, txs: List[str], n: int) -> None:
        self._chain().mine_blocks(event, txs, n)

    def expect_tx(self, event: Event, txid: str) -> None:
        self._chain().expect_tx(event, txid)

    def invoice(self, event: Event, amount: int, preimage: str) -> None:
        self._node().legacy_invoice(event, amount, preimage)

    def accept_add_fund(self, event: Event) -> None:
        self._node().legacy_accept_add_fund(event)

    def fundchannel(
        self,
        event: Event,
        conn: Conn,
        amount: int,
        feerate: int = 253,
        expect_fail: bool = False,
    ) -> None:
        self._node().legacy_fundchannel(
            event, conn, amount, feerate=feerate, expect_fail=expect_fail
        )

    def init_rbf(
        self,
        event: Event,
        conn: Conn,
        channel_id: str,
        amount: int,
        utxo_txid: str,
        utxo_outnum: int,
        feerate: int,
    ) -> None:
        self._node().legacy_init_rbf(
            event,
            conn,
            channel_id,
            amount,
            utxo_txid,
            utxo_outnum,
            feerate,
        )

    def addhtlc(self, event: Event, conn: Conn, amount: int, preimage: str) -> None:
        self._node().legacy_addhtlc(event, conn, amount, preimage)

    def get_keyset(self) -> KeySet:
        return self._node().legacy_get_keyset()

    def get_node_privkey(self) -> str:
        return self._node().legacy_get_node_privkey()

    def get_node_bitcoinkey(self) -> str:
        return self._node().legacy_get_node_bitcoinkey()

    def has_option(self, optname: str) -> Optional[str]:
        return self._node().capabilities().legacy_has_option(optname)

    def add_startup_flag(self, flag: str) -> None:
        self._node().legacy_add_startup_flag(flag)

    def close_channel(self, channel_id: str) -> None:
        self._node().legacy_close_channel(channel_id)

    def check_final_error(
        self,
        event: Event,
        conn: Conn,
        expected: bool,
        must_not_events: List[Any],
    ) -> None:
        conn.close()


class Runner(LegacyRunnerAdapter):
    """Compatibility name kept for tests and external runners."""

    pass


def remote_revocation_basepoint() -> Callable[[Runner, Event, str], str]:
    """Get the remote revocation basepoint"""

    def _remote_revocation_basepoint(runner: Runner, event: Event, field: str) -> str:
        return runner.get_keyset().revocation_basepoint()

    return _remote_revocation_basepoint


def remote_payment_basepoint() -> Callable[[Runner, Event, str], str]:
    """Get the remote payment basepoint"""

    def _remote_payment_basepoint(runner: Runner, event: Event, field: str) -> str:
        return runner.get_keyset().payment_basepoint()

    return _remote_payment_basepoint


def remote_delayed_payment_basepoint() -> Callable[[Runner, Event, str], str]:
    """Get the remote delayed_payment basepoint"""

    def _remote_delayed_payment_basepoint(
        runner: Runner, event: Event, field: str
    ) -> str:
        return runner.get_keyset().delayed_payment_basepoint()

    return _remote_delayed_payment_basepoint


def remote_htlc_basepoint() -> Callable[[Runner, Event, str], str]:
    """Get the remote htlc basepoint"""

    def _remote_htlc_basepoint(runner: Runner, event: Event, field: str) -> str:
        return runner.get_keyset().htlc_basepoint()

    return _remote_htlc_basepoint


def remote_funding_pubkey() -> Callable[[Runner, Event, str], str]:
    """Get the remote funding pubkey (FIXME: we assume there's only one!)"""

    def _remote_funding_pubkey(runner: Runner, event: Event, field: str) -> str:
        return (
            coincurve.PublicKey.from_secret(
                privkey_expand(runner.get_node_bitcoinkey()).secret
            )
            .format()
            .hex()
        )

    return _remote_funding_pubkey


def remote_funding_privkey() -> Callable[[Runner, Event, str], str]:
    """Get the remote funding privkey (FIXME: we assume there's only one!)"""

    def _remote_funding_privkey(runner: Runner, event: Event, field: str) -> str:
        return runner.get_node_bitcoinkey()

    return _remote_funding_privkey


def remote_per_commitment_point(n: int) -> Callable[[Runner, Event, str], str]:
    """Get the n'th remote per-commitment point"""

    def _remote_per_commitment_point(
        n: int, runner: Runner, event: Event, field: str
    ) -> str:
        return runner.get_keyset().per_commit_point(n)

    return functools.partial(_remote_per_commitment_point, n)


def remote_per_commitment_secret(n: int) -> Callable[[Runner, Event, str], str]:
    """Get the n'th remote per-commitment secret"""

    def _remote_per_commitment_secret(runner: Runner, event: Event, field: str) -> str:
        return runner.get_keyset().per_commit_secret(n)

    return _remote_per_commitment_secret

#!/usr/bin/python3
# This script exercises the core-lightning implementation

# Released by Rusty Russell under CC0:
# https://creativecommons.org/publicdomain/zero/1.0/

import hashlib
import logging
import os
import shutil
import socket
import struct
import subprocess
import time

from concurrent import futures
from contextlib import closing
from datetime import date
from typing import Any, Callable, Dict, List, Optional, cast

import bitcoin.core
import lnprototest
import pyln.client
import pyln.proto.wire

from lnprototest import Event, EventError, MustNotMsg, namespace, wait_for
from lnprototest.backend import Bitcoind
from lnprototest.boundary import CapabilitySet, ChainBackend, NodeAdapter, PeerSession

TIMEOUT = int(os.getenv("TIMEOUT", "60"))
LIGHTNING_SRC = os.path.join(os.getcwd(), os.getenv("LIGHTNING_SRC", "../lightning/"))


class CLightningPeerSession(PeerSession):
    def __init__(self, connprivkey: str, port: int):
        privkey = lnprototest.privkey_expand(connprivkey)
        self.connection = pyln.proto.wire.connect(
            pyln.proto.wire.PrivateKey(bytes.fromhex(privkey.to_hex())),
            pyln.proto.wire.PublicKey(
                bytes.fromhex(
                    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
                )
            ),
            "127.0.0.1",
            port,
        )
        super().__init__(connprivkey)

    def send_raw(self, payload: bytes) -> None:
        self.connection.send_message(payload)

    def recv_raw(self, timeout: Optional[int] = None) -> bytes:
        return self.connection.read_message()

    def close(self) -> None:
        self.connection.connection.close()


class CLightningChainBackend(ChainBackend):
    def __init__(self, basedir: str):
        self.basedir = basedir
        self.bitcoind: Optional[Bitcoind] = None
        self._node_height: Optional[Callable[[], int]] = None

    def set_node_height(self, callback: Callable[[], int]) -> None:
        self._node_height = callback

    def _bitcoind(self) -> Bitcoind:
        if self.bitcoind is None:
            raise RuntimeError("bitcoind is not initialized")
        return self.bitcoind

    def start(self) -> None:
        if self.bitcoind is None:
            self.bitcoind = Bitcoind(self.basedir)
        self.bitcoind.start()

    def stop(self) -> None:
        if self.bitcoind is not None:
            self.bitcoind.stop()

    def restart(self) -> None:
        if self.bitcoind is None:
            self.start()
            return
        self.bitcoind.restart()

    def block_height(self) -> int:
        return self._bitcoind().rpc.getblockcount()

    def trim_blocks(self, newheight: int) -> None:
        block_hash = self._bitcoind().rpc.getblockhash(newheight + 1)
        self._bitcoind().rpc.invalidateblock(block_hash)

    def mine_blocks(self, event: Event, txs: List[str], n: int) -> None:
        for tx in txs:
            self._bitcoind().rpc.sendrawtransaction(tx)
        self._bitcoind().rpc.generatetoaddress(n, self._bitcoind().rpc.getnewaddress())
        if self._node_height is not None:
            wait_for(lambda: self._node_height() == self.block_height())

    def expect_tx(self, event: Event, txid: str) -> None:
        revtxid = bitcoin.core.lx(txid).hex()
        try:
            wait_for(lambda: revtxid in self._bitcoind().rpc.getrawmempool())
        except ValueError:
            raise EventError(
                event,
                "Did not broadcast the txid {}, just {}".format(
                    revtxid,
                    [
                        (mempool_txid, self._bitcoind().rpc.getrawtransaction(mempool_txid))
                        for mempool_txid in self._bitcoind().rpc.getrawmempool()
                    ],
                ),
            )


class CLightningNodeAdapter(NodeAdapter):
    def __init__(self, config: Any, basedir: str, chain: CLightningChainBackend):
        self.config = config
        self.basedir = basedir
        self.chain = chain
        self.running = False
        self.rpc: Optional[pyln.client.LightningRpc] = None
        self.proc: Optional[subprocess.Popen[Any]] = None
        self.cleanup_callbacks: List[Callable[[], None]] = []
        self.fundchannel_future: Optional[Any] = None
        self.is_fundchannel_kill = False
        self.executor = futures.ThreadPoolExecutor(max_workers=20)
        self.startup_flags = [
            "--{}".format(flag) for flag in config.getoption("runner_args")
        ]
        self._capabilities = self._load_capabilities()
        self.lightning_dir = os.path.join(self.basedir, "lightningd")
        self.lightning_port: Optional[int] = None

    def _load_capabilities(self) -> CapabilitySet:
        ret = subprocess.run(
            [
                "{}/lightningd/lightningd".format(LIGHTNING_SRC),
                "--developer",
                "--help",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if ret.returncode != 0:
            self.startup_flags.append("--developer")

        feature_lines = (
            subprocess.run(
                [
                    "{}/lightningd/lightningd".format(LIGHTNING_SRC),
                    "--list-features-only",
                ],
                stdout=subprocess.PIPE,
                check=True,
            )
            .stdout.decode("utf-8")
            .splitlines()
        )
        return CapabilitySet.from_cln_feature_lines(feature_lines)

    def capabilities(self) -> CapabilitySet:
        return self._capabilities

    def __reserve(self) -> int:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("", 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return sock.getsockname()[1]

    def __init_sandbox_dir(self) -> None:
        if not os.path.exists(self.lightning_dir):
            os.makedirs(self.lightning_dir)

    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.__init_sandbox_dir()
        self.lightning_port = self.__reserve()
        bitcoind = self.chain._bitcoind()
        self.proc = subprocess.Popen(
            [
                "{}/lightningd/lightningd".format(LIGHTNING_SRC),
                "--lightning-dir={}".format(self.lightning_dir),
                "--funding-confirms=3",
                "--dev-force-privkey=0000000000000000000000000000000000000000000000000000000000000001",
                "--dev-force-bip32-seed=0000000000000000000000000000000000000000000000000000000000000001",
                "--dev-force-channel-secrets=0000000000000000000000000000000000000000000000000000000000000010/0000000000000000000000000000000000000000000000000000000000000011/0000000000000000000000000000000000000000000000000000000000000012/0000000000000000000000000000000000000000000000000000000000000013/0000000000000000000000000000000000000000000000000000000000000014/FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
                "--dev-bitcoind-poll=1",
                "--dev-fast-gossip",
                "--dev-allow-localhost",
                "--dev-no-htlc-timeout",
                "--bind-addr=127.0.0.1:{}".format(self.lightning_port),
                "--network=regtest",
                "--bitcoin-rpcuser=rpcuser",
                "--bitcoin-rpcpassword=rpcpass",
                f"--bitcoin-rpcconnect=127.0.0.1:{bitcoind.port}",
                "--log-level=debug",
                "--log-file=log",
                "--htlc-maximum-msat=2000sat",
            ]
            + self.startup_flags
        )
        self.rpc = pyln.client.LightningRpc(
            os.path.join(self.lightning_dir, "regtest", "lightning-rpc")
        )
        self.running = True

        def node_ready(rpc: pyln.client.LightningRpc) -> bool:
            try:
                rpc.getinfo()
                return True
            except Exception as ex:
                logging.debug(f"waiting for core-lightning: Exception received {ex}")
                return False

        wait_for(lambda: node_ready(self.rpc), timeout=TIMEOUT)
        self.chain.set_node_height(lambda: self.rpc.getinfo()["blockheight"])
        for _ in range(5):
            self.rpc.newaddr()

    def stop(self, print_logs: bool = False) -> None:
        if not self.running or self.rpc is None:
            return
        for cb in list(self.cleanup_callbacks):
            cb()
        self.cleanup_callbacks = []
        self.rpc.stop()
        if self.proc is not None:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
            self.proc = None
        self.rpc = None
        self.lightning_port = None
        self.running = False
        if print_logs:
            log_path = f"{self.lightning_dir}/regtest/log"
            if os.path.exists(log_path):
                with open(log_path) as log:
                    logging.info("---------- core-lightning logging ----------------")
                    logging.info(log.read())
                    shutil.copy(
                        log_path,
                        f'/tmp/c-lightning-log_{date.today().strftime("%b-%d-%Y_%H:%M:%S")}',
                    )
        regtest_dir = os.path.join(self.lightning_dir, "regtest")
        if os.path.exists(regtest_dir):
            shutil.rmtree(regtest_dir, ignore_errors=True)

    def restart(self) -> None:
        self.stop()
        self.start()

    def open_session(self, connprivkey: str) -> PeerSession:
        if self.lightning_port is None:
            raise RuntimeError("lightning port is not initialized")
        return CLightningPeerSession(connprivkey, self.lightning_port)

    def legacy_get_keyset(self) -> lnprototest.KeySet:
        return lnprototest.KeySet(
            revocation_base_secret="0000000000000000000000000000000000000000000000000000000000000011",
            payment_base_secret="0000000000000000000000000000000000000000000000000000000000000012",
            delayed_payment_base_secret="0000000000000000000000000000000000000000000000000000000000000013",
            htlc_base_secret="0000000000000000000000000000000000000000000000000000000000000014",
            shachain_seed="FF" * 32,
        )

    def legacy_get_node_privkey(self) -> str:
        return "01"

    def legacy_get_node_bitcoinkey(self) -> str:
        return "0000000000000000000000000000000000000000000000000000000000000010"

    def legacy_add_startup_flag(self, flag: str) -> None:
        logging.debug("[ADD STARTUP FLAG '{}']".format(flag))
        self.startup_flags.append("--{}".format(flag))

    def legacy_fundchannel(
        self,
        event: Event,
        conn: PeerSession,
        amount: int,
        feerate: int = 253,
        expect_fail: bool = False,
    ) -> None:
        if self.fundchannel_future and not self.fundchannel_future.done():
            raise RuntimeError(
                "{} called fundchannel while another channel funding (fundchannel/init_rbf) is still in process".format(
                    event
                )
            )
        self.fundchannel_future = None

        def _fundchannel(
            node: CLightningNodeAdapter,
            peer_session: PeerSession,
            amount: int,
            feerate: int,
            expect_fail: bool = False,
        ) -> str:
            peer_id = peer_session.pubkey.format().hex()
            try:
                return (
                    node.rpc.fundchannel(
                        peer_id, amount, feerate="{}perkw".format(feerate)
                    ),
                    False,
                )
            except Exception as ex:
                logging.error(f"{ex}")
                return str(ex), True

        def _done(fut: Any) -> None:
            result, ok = fut.result()
            if not ok and not self.is_fundchannel_kill and not expect_fail:
                raise Exception(result)
            self.fundchannel_future = None
            self.is_fundchannel_kill = False
            if self.kill_fundchannel in self.cleanup_callbacks:
                self.cleanup_callbacks.remove(self.kill_fundchannel)

        time.sleep(1)
        fut = self.executor.submit(_fundchannel, self, conn, amount, feerate, expect_fail)
        fut.add_done_callback(_done)
        self.fundchannel_future = fut
        self.cleanup_callbacks.append(self.kill_fundchannel)

    def legacy_close_channel(self, channel_id: str) -> None:
        logging.debug("[CLOSE CHANNEL with channel id: '{}']".format(channel_id))
        self.rpc.close(peer_id=channel_id)

    def kill_fundchannel(self) -> None:
        fut = self.fundchannel_future
        self.fundchannel_future = None
        self.is_fundchannel_kill = True
        if fut:
            try:
                fut.result(0)
            except futures.TimeoutError:
                pass

    def legacy_init_rbf(
        self,
        event: Event,
        conn: PeerSession,
        channel_id: str,
        amount: int,
        utxo_txid: str,
        utxo_outnum: int,
        feerate: int,
    ) -> None:
        if self.fundchannel_future:
            self.kill_fundchannel()

        startweight = 42 + 172
        fmt_feerate = "{}perkw".format(feerate)
        utxos = ["{}:{}".format(utxo_txid, utxo_outnum)]
        initial_psbt = self.rpc.utxopsbt(
            amount,
            fmt_feerate,
            startweight,
            utxos,
            reservedok=True,
            min_witness_weight=110,
            locktime=0,
            excess_as_change=True,
        )["psbt"]

        def _run_rbf(node: CLightningNodeAdapter) -> Dict[str, Any]:
            bump = node.rpc.openchannel_bump(
                channel_id, amount, initial_psbt, funding_feerate=fmt_feerate
            )
            update = node.rpc.openchannel_update(channel_id, bump["psbt"])
            while not update["commitments_secured"]:
                update = node.rpc.openchannel_update(channel_id, update["psbt"])
            signed_psbt = node.rpc.signpsbt(update["psbt"])["signed_psbt"]
            return node.rpc.openchannel_signed(channel_id, signed_psbt)

        fut = self.executor.submit(_run_rbf, self)
        fut.add_done_callback(lambda task: task.exception(0))

    def legacy_invoice(self, event: Event, amount: int, preimage: str) -> None:
        self.rpc.invoice(
            msatoshi=amount,
            label=str(event),
            description="invoice from {}".format(event),
            preimage=preimage,
        )

    def legacy_accept_add_fund(self, event: Event) -> None:
        self.rpc.call(
            "funderupdate",
            {
                "policy": "match",
                "policy_mod": 100,
                "fuzz_percent": 0,
                "leases_only": False,
            },
        )

    def legacy_addhtlc(
        self, event: Event, conn: PeerSession, amount: int, preimage: str
    ) -> None:
        payhash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()
        routestep = {
            "msatoshi": amount,
            "id": conn.pubkey.format().hex(),
            "delay": 4,
            "channel": "1x1x1",
        }
        self.rpc.sendpay([routestep], payhash)


class Runner(lnprototest.Runner):
    def __init__(self, config: Any):
        super().__init__(config)
        self.chain = CLightningChainBackend(self.directory)
        self.node = CLightningNodeAdapter(config, self.directory, self.chain)

    def recv(self, event: Event, conn: PeerSession, outbuf: bytes) -> None:
        try:
            conn.send_raw(outbuf)
        except BrokenPipeError:
            fut = self.node.executor.submit(
                cast(CLightningPeerSession, conn).connection.read_message
            )
            try:
                msg = fut.result(1)
            except futures.TimeoutError:
                msg = None
            if msg:
                raise EventError(
                    event, "Connection closed after sending {}".format(msg.hex())
                )
            raise EventError(event, "Connection closed")

    def get_output_message(
        self, conn: PeerSession, event: Event, timeout: int = TIMEOUT
    ) -> Optional[bytes]:
        fut = self.node.executor.submit(
            cast(CLightningPeerSession, conn).connection.read_message
        )
        try:
            return fut.result(timeout)
        except futures.TimeoutError as ex:
            logging.error(f"timeout exception {ex}")
            return None
        except Exception as ex:
            logging.error(f"{ex}")
            return None

    def check_error(self, event: Event, conn: PeerSession) -> Optional[str]:
        super().check_error(event, conn)
        msg = self.get_output_message(conn, event)
        if msg is None:
            return None
        return msg.hex()

    def check_final_error(
        self,
        event: Event,
        conn: PeerSession,
        expected: bool,
        must_not_events: List[MustNotMsg],
    ) -> None:
        if not expected:
            cast(CLightningPeerSession, conn).connection.connection.send(bytes(18))

            while True:
                binmsg = self.get_output_message(conn, event)
                if binmsg is None:
                    break
                for must_not in must_not_events:
                    if must_not.matches(binmsg):
                        raise EventError(
                            event, "Got msg banned by {}: {}".format(must_not, binmsg.hex())
                        )

                msgtype = struct.unpack(">H", binmsg[:2])[0]
                if msgtype == namespace().get_msgtype("error").number:
                    raise EventError(event, "Got error msg: {}".format(binmsg.hex()))

        conn.close()

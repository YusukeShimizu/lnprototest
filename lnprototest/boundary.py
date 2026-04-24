from __future__ import annotations

import io

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import coincurve
from pyln.proto.message import Message

from .errors import SpecFileError
from .keyset import KeySet
from .namespace import namespace
from .utils import privkey_expand

if TYPE_CHECKING:
    from .event import Event


class CapabilityLevel(Enum):
    ABSENT = "absent"
    SUPPORTED = "supported"
    REQUIRED = "required"


@dataclass
class CapabilityInfo:
    level: CapabilityLevel
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilitySet:
    """Normalized capability view used by the core boundary."""

    def __init__(self) -> None:
        self.protocol: Dict[str, CapabilityInfo] = {}
        self.extensions: Dict[str, bool] = {}

    def set_protocol(
        self,
        name: str,
        level: CapabilityLevel,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.protocol[name] = CapabilityInfo(level=level, metadata=metadata or {})

    def set_extension(self, name: str, enabled: bool) -> None:
        self.extensions[name] = enabled

    def protocol_level(self, name: str) -> CapabilityLevel:
        info = self.protocol.get(name)
        if info is None:
            return CapabilityLevel.ABSENT
        return info.level

    def extension_enabled(self, name: str) -> bool:
        return self.extensions.get(name, False)

    def supports(self, name: str) -> bool:
        return self.protocol_level(
            name
        ) != CapabilityLevel.ABSENT or self.extension_enabled(name)

    def legacy_has_option(self, name: str) -> Optional[str]:
        if name in self.extensions:
            return "true" if self.extensions[name] else None
        level = self.protocol_level(name)
        if level == CapabilityLevel.REQUIRED:
            return "even"
        if level == CapabilityLevel.SUPPORTED:
            return "odd"
        return None

    @classmethod
    def from_cln_feature_lines(cls, feature_lines: List[str]) -> "CapabilitySet":
        capabilities = cls()
        for line in feature_lines:
            if line.startswith("supports_"):
                capabilities.set_extension(line, True)
                continue
            name, legacy_value = line.split("/", 1)
            if legacy_value == "even":
                level = CapabilityLevel.REQUIRED
            elif legacy_value == "odd":
                level = CapabilityLevel.SUPPORTED
            else:
                level = CapabilityLevel.ABSENT
            capabilities.set_protocol(name, level, {"legacy_value": legacy_value})
        return capabilities


class PeerSession(ABC):
    """Protocol-conversation boundary."""

    def __init__(self, connprivkey: str):
        self.name = connprivkey
        self.connprivkey = privkey_expand(connprivkey)
        self.pubkey = coincurve.PublicKey.from_secret(self.connprivkey.secret)
        self.expected_error = False
        self.must_not_events: List[Any] = []
        self.stash: Dict[str, Any] = {}

    def __str__(self) -> str:
        return self.name

    def add_stash(self, stashname: str, vals: Any) -> None:
        self.stash[stashname] = vals

    def get_stash(self, event: "Event", stashname: str, default: Any = None) -> Any:
        if stashname not in self.stash:
            if default is not None:
                return default
            raise SpecFileError(event, "Unknown stash name {}".format(stashname))
        return self.stash[stashname]

    def send_msg(self, msg_name: str, **kwargs: Any) -> None:
        msgtype = namespace().get_msgtype(msg_name)
        if not msgtype:
            raise SpecFileError(self, "Unknown msgtype {}".format(msg_name))
        msg = Message(msgtype, **kwargs)
        missing = msg.missing_fields()
        if missing:
            raise SpecFileError(self, "Missing fields {}".format(missing))
        binmsg = io.BytesIO()
        msg.write(binmsg)
        self.send_raw(binmsg.getvalue())

    def recv_msg(self, timeout: Optional[int] = None) -> Message:
        raw_msg = self.recv_raw(timeout=timeout)
        msg = Message.read(namespace(), io.BytesIO(raw_msg))
        self.add_stash(msg.messagetype.name, msg)
        return msg

    def send(self, msg_name: str, **kwargs: Any) -> None:
        self.send_msg(msg_name, **kwargs)

    def recv(self, timeout: Optional[int] = None) -> Message:
        return self.recv_msg(timeout=timeout)

    def disconnect(self) -> None:
        self.close()

    @abstractmethod
    def send_raw(self, payload: bytes) -> None:
        pass

    @abstractmethod
    def recv_raw(self, timeout: Optional[int] = None) -> bytes:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class NodeAdapter(ABC):
    @abstractmethod
    def is_running(self) -> bool:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self, print_logs: bool = False) -> None:
        pass

    @abstractmethod
    def restart(self) -> None:
        pass

    @abstractmethod
    def open_session(self, connprivkey: str) -> PeerSession:
        pass

    @abstractmethod
    def capabilities(self) -> CapabilitySet:
        pass

    def teardown(self) -> None:
        return

    def legacy_get_keyset(self) -> KeySet:
        raise NotImplementedError

    def legacy_get_node_privkey(self) -> str:
        raise NotImplementedError

    def legacy_get_node_bitcoinkey(self) -> str:
        raise NotImplementedError

    def legacy_add_startup_flag(self, flag: str) -> None:
        raise NotImplementedError

    def legacy_fundchannel(
        self,
        event: "Event",
        conn: PeerSession,
        amount: int,
        feerate: int = 253,
        expect_fail: bool = False,
    ) -> None:
        raise NotImplementedError

    def legacy_init_rbf(
        self,
        event: "Event",
        conn: PeerSession,
        channel_id: str,
        amount: int,
        utxo_txid: str,
        utxo_outnum: int,
        feerate: int,
    ) -> None:
        raise NotImplementedError

    def legacy_invoice(self, event: "Event", amount: int, preimage: str) -> None:
        raise NotImplementedError

    def legacy_accept_add_fund(self, event: "Event") -> None:
        raise NotImplementedError

    def legacy_addhtlc(
        self, event: "Event", conn: PeerSession, amount: int, preimage: str
    ) -> None:
        raise NotImplementedError

    def legacy_close_channel(self, channel_id: str) -> None:
        raise NotImplementedError


class ChainBackend(ABC):
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def restart(self) -> None:
        pass

    def teardown(self) -> None:
        return

    @abstractmethod
    def block_height(self) -> int:
        pass

    @abstractmethod
    def trim_blocks(self, newheight: int) -> None:
        pass

    @abstractmethod
    def mine_blocks(self, event: "Event", txs: List[str], n: int) -> None:
        pass

    @abstractmethod
    def expect_tx(self, event: "Event", txid: str) -> None:
        pass

    @abstractmethod
    def expect_no_tx(self, event: "Event", txid: str) -> None:
        pass

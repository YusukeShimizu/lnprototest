# BOLT8 Test Gap

この文書は、BOLT8 encrypted transport の不足テストを、現在の runner boundary 再設計と接続して整理する。目的は、BOLT8 を Event DSL に無理に載せることではない。BOLT8 は Lightning message の前段にある transport protocol なので、`Msg` / `ExpectMsg` の namespace ではなく、connection owner と raw transport owner の境界を先に明確にする必要がある。

## Context

Discord 議論で繰り返し出ていた問題は、単に test syntax を変えたいという話ではなかった。Rusty の `lnprotest` では、message を普通の Python 変数として持ち、minor variant を自然な分岐として書きたいという方向が示された。一方で cdecker は、`RunnerConn` が no-op に見えることや、multiple connection case で runner が自動選択する connection state が曖昧になることを問題にしていた。

この文脈では、BOLT8 はよい proving target になる。BOLT8 handshake と encrypted message framing は、BOLT1 `init` よりも一段下の transport layer であり、どの object が TCP socket、handshake acts、post-handshake encrypted message I/O を所有するかが曖昧なままだと、テストを書いても責務が混ざる。

現在の再設計では、post-handshake の protocol conversation は `PeerSession` に残す。`PeerSession.send_msg()` / `recv_msg()` は Lightning message を扱う stable seam であり、BOLT1/BOLT2/BOLT7 の既存テストはここに乗せる。一方、BOLT8 の act one / act two / act three や malformed handshake は、Lightning message ではなく raw transport bytes として扱う。

out-of-tree runner の観点でも同じである。LDK や Lampo のような runner が本体外にある場合、node lifecycle は `NodeAdapter`、post-handshake message I/O は `PeerSession`、chain observation は `ChainBackend` に置ける。しかし BOLT8 handshake 自体は `PeerSession` のさらに下にある transport setup なので、test-only の raw harness を明示的に用意しないと、外部 runner author に fat `Runner` 相当の隠れ責務を押し戻してしまう。

## Missing BOLT8 Cases

| Area | 不足しているケース | 初回で書くべき形 |
| --- | --- | --- |
| Initiator handshake | successful handshake、act2 short read、bad version、bad pubkey serialization、bad MAC/tag | `tests/test_bolt8_transport_vectors.py` で公式 transport vector を `Bolt8TransportHarness` に流す |
| Responder handshake | successful handshake、act1 short read、bad version、bad pubkey、bad tag、act3 bad version、short read、bad ciphertext MAC、bad static pubkey、bad tag | 同じ unit vector test で responder mode を分ける |
| Message encryption | encrypted length、encrypted payload、nonce increment、公式 output 0 / 1 / 500 / 501 / 1000 / 1001 | `hello` 1001 回の公式 vector を使い、key rotation 境界も固定する |
| Supplemental framing | 65535 byte 上限、length MAC 改ざん、payload MAC 改ざん | 公式 vector とは別の local supplemental unit として追加する |
| Small live behavior | CLN responder が malformed act1 を受けたとき、act2 を返さず接続を閉じる | `tests/test_bolt8_transport_live.py` で `RawTransportProbe` から raw socket を使う |

ここで重要なのは、unit vector と live behavior を混ぜないことだ。unit vector は BOLT8 crypto / framing の deterministic proof であり、node process は不要である。small live は実装が malformed handshake を外から見てどう扱うかの smoke proof であり、公式 vector の代替ではない。

## Current Code Obstacles

現行の `PeerSession` は BOLT8 後の seam としてはよいが、BOLT8 自体を直接テストする seam ではない。`PeerSession.send_raw()` / `recv_raw()` という名前は raw に見えるが、CLN runner では `pyln.proto.wire.LightningConnection.send_message()` / `read_message()` に委譲される。つまりここで送受信しているのは、BOLT8 handshake bytes ではなく、handshake 済み connection 上の Lightning payload である。

`CLightningPeerSession` は constructor で `pyln.proto.wire.connect(...)` を呼ぶ。この helper は TCP connection を作り、Noise_XK handshake を完了してから `LightningConnection` を返す。結果として、test author が act one を改ざんする、act two を短く読む、bad tag を注入する、といった BOLT8 の失敗点へ入る前に handshake が隠蔽される。

現行 Event DSL の `Msg` / `ExpectMsg` も BOLT8 には合わない。`tests/conftest.py` は peer message namespace として BOLT1/BOLT2/BOLT7 を扱っており、BOLT8 acts は message type ではない。ここに BOLT8 を message として入れると、transport protocol と inner Lightning message protocol の境界が崩れる。

さらに、ローカルで確認した `pyln-proto` の `LightningConnection` 実装には、bad MAC / bad tag path を前提にしてよいかを先に検証すべきリスクがある。少なくとも `InvalidTag` を受けた path は unit vector で実際に失敗として観測し、期待どおり例外が伝播するかを固定してから、live probe の土台にする必要がある。

## How Re-Architecture Helps

再設計後も、通常の post-handshake message tests は `PeerSession` のままでよい。BOLT1 `init`、BOLT2 `channel_reestablish`、BOLT7 gossip filter のようなテストは、`conn.recv_msg()` / `conn.send_msg(...)` / `conn.disconnect()` を connection owner の下で使う。これは Discord 議論で問題になった auto-selected connection state を避けるための stable seam である。

BOLT8 の unit vector は、この stable seam の下に test-only の `Bolt8TransportHarness` を置いて書く。これは public runner API ではなく、公式 vector を deterministic に流すための harness である。役割は次に限定する。

- initiator / responder の固定 secret と固定 ephemeral key を受け取る。
- act one / act two / act three の input / output bytes を直接扱う。
- successful handshake 後の `sk` / `rk` と nonce を見て、message encryption vector と key rotation を検証する。
- bad version、bad pubkey、bad tag、short read を Lightning message に変換せず、transport error として扱う。

small live では、`RawTransportProbe` を `NodeAdapter` の補助として扱う。これは `PeerSession` を置き換えるものではない。CLN の `NodeAdapter` が node を起動し、probe は `lightning_port` に raw socket で接続し、bad act1 version または bad act1 MAC を送る。期待値は、act2 が返らず connection が閉じることだけにする。通常の `pyln.proto.wire.connect` は handshake を隠すため、この live probe では使わない。

この分け方にすると、BOLT8 を追加しても fat `Runner` に戻らない。`PeerSession` は post-handshake conversation、`Bolt8TransportHarness` は deterministic transport unit、`RawTransportProbe` は live responder smoke として責務が分かれる。BOLT8 の不足テストを足すこと自体が、runner boundary の設計が正しいかを確認する材料になる。

## Implementation Order

1. `tests/test_bolt8_transport_vectors.py` を追加し、公式 Appendix A の initiator / responder / message encryption vector を unit test にする。
2. `pyln-proto` の bad MAC / bad tag path が期待どおり fail するかを unit test で確認し、必要なら test harness 側で例外を明示的に正規化する。
3. `tests/test_bolt8_transport_live.py` を optional live test として追加し、CLN runner 環境でのみ raw socket malformed act1 smoke を走らせる。
4. live test は act1 bad version から始める。bad MAC は次の候補にし、最初から複数実装の詳細ログ比較まではしない。

## Non-Goals

- BOLT8 acts を Event DSL の `Msg` / `ExpectMsg` に入れない。
- `PeerSession` の public API を BOLT8 handshake 操作用に拡張しない。
- 初回で BOLT8 helper API を stable public contract にしない。
- live test で full interop matrix を作らない。
- gRPC / remote adapter の wire schema をここで決めない。

## References

- [BOLT #8: Encrypted and Authenticated Transport](https://github.com/lightning/bolts/blob/master/08-transport.md)
- [`discord.md`](../discord.md)
- [`runner-boundary.md`](./runner-boundary.md)
- [`test-authoring.md`](./test-authoring.md)

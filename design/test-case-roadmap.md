# Test Case Roadmap

この文書は、runner boundary split 後にどの executable test を足すかを段階化する。目的は、splicing や BLIP32 のような広い仕様領域を一気に実装することではなく、`CapabilitySet` / `NodeAdapter` / `PeerSession` / `ChainBackend` / `LegacyRunnerAdapter` の分割によって、これまで runner-wide state や chain assertion の曖昧さで書きにくかったケースを書けるかを確認することである。

## Phase 1: Multi-Session Runner Boundary Proving Cases

最初に executable にするのは、protocol conversation と chain observation の境界が必要になる小さなケースに限定する。中心は authoring style ではなく、session / chain / node の責務分割である。特に issue #105 への返答としては、「新しい書き方ができる」よりも「これまで見通しが悪かった multi-session case を増やせる形に近づく」ことを主証明にする。

- Primary proof は multi-session boundary に置く。既存の `tests/test_bolt7-10-gossip-filter.py` は、`connprivkey="05"` と `"06"` が同時に異なる gossip filter state を持つ実プロトコル例であり、session owner と peer-local expectation が runner-wide state に埋もれる問題を示す reference case として扱う。
- `tests/test_runner_boundary.py` では二つの `PeerSession` が別々の send / recv / stash / disconnect state を持ち、片方の disconnect がもう片方を閉じないことを unit level で固定する。
- BOLT2 `channel_reestablish` は chain boundary proof として残す。既存正常系の setup を helper 化し、正常 reconnect と abnormal reconnect が同じ channel/session 前提を共有できることを示す。
- outdated `next_commitment_number` を送ったとき、peer が error / disconnect の前に commitment transaction を即座に mempool へ出さないことを `ExpectNoTx` で表現する。
- `ExpectNoTx` は `ChainBackend` の最小補助として追加する。ここでは「その時点の mempool に specific txid がない」だけを確認し、時間幅を持つ liveness assertion は導入しない。
- BOLT1 `init` echo / reconnect の procedural tests は secondary smoke として残す。`runner.connect(connprivkey="03")`, `conn.recv_msg()`, `conn.send_msg(...)` が動くことは見るが、boundary split の主証明とは扱わない。
- `PeerSession.recv()`, `PeerSession.send(...)`, `PeerSession.disconnect()` は convenience として追加し、既存 `recv_msg`, `send_msg`, `close` に委譲されることを unit test で固定する。

この phase では `runner.choose([...])` は実装しない。分岐網羅は従来通り `TryAll` や pytest の明示的な test case に任せ、探索 semantics は後続設計に回す。

## Phase 2: Channel Reestablish Abnormal Cases

次に伸ばす候補も、`channel_reestablish` の outdated / inconsistent state 周辺に置く。ここは lightning/bolts issue #934 と lnprototest issue #49 の重なりが大きく、runner boundary の価値を示しやすい。

- `your_last_per_commitment_secret` が不整合な場合の error / disconnect behavior を追加する。
- `next_revocation_number` が進みすぎている場合と遅れている場合を分け、どちらが fail-fast で、どちらが data loss protection flow に入るべきかを明示する。
- BOLT7 gossip filter の既存 multi-session test を新 boundary 上の authoring target として分解し、peer-local gossip filter state と future gossip expectation を session-local に表現できるか確認する。
- `runner.choose([...])` を入れる前に、既存 Event DSL だけで abnormal cases が表現できる限界を確認する。

## Phase 3: Later Specification Backlog

runner boundary の proving が終わってから、仕様面の大きな backlog を別 issue / PR に分ける。

- splicing
- attributable failures
- dual-funding RBF
- BLIP32 / onion message DNS resolution
- BOLT12 offer / invoice request / invoice flow

これらは重要だが、v1 boundary の acceptance line には入れない。最初の acceptance line は multi-session boundary を primary proof にし、`channel_reestablish` abnormal case は chain-boundary proof、`init` と disconnect / reconnect は smoke として補助する。ここが成立してから feature-specific extension を増やす。

## Public References

- rustyrussell/lnprotest README: 後続 authoring layer の参考形。
- rustyrussell/lnprototest PR #95: session state と `RunnerConn` 導入方向の先行議論。
- rustyrussell/lnprototest issue #49: `channel_reestablish` failure case の executable test 化。
- lightning/bolts issue #934: outdated `channel_reestablish` 受信時に commitment を publish すべきでない問題意識。

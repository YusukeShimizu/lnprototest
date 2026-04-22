# Runner Boundary

この文書は、現行 `Runner` contract をどの責務に分割し、core v1 に何を残すかを決める。ここでの設計判断は、この bundle の中心である。`external runner` を first-class に認めるだけでは、現行の fat contract が別 repo に移るだけで問題は解決しない。先に必要なのは boundary cleanup である。

## The Problem Being Solved

[`lnprototest/runner.py`](../lnprototest/runner.py) は protocol conversation の最小面を超えて広すぎる。`connect`、`recv`、`get_output_message` のような peer I/O に加えて、`getblockheight`、`add_blocks`、`expect_tx`、`fundchannel`、`init_rbf`、`addhtlc`、`get_keyset`、`get_node_privkey`、`get_node_bitcoinkey`、`has_option`、`add_startup_flag` が並んでいる。[`HACKING.md`](../HACKING.md) もこの surface をそのまま new runner に要求しており、[`lnprototest/dummyrunner.py`](../lnprototest/dummyrunner.py) ですら広い stub surface を持つ。

この contract は [`lnprototest/clightning/clightning.py`](../lnprototest/clightning/clightning.py) の実装形を見るとさらに問題が見える。CLN runner は `lightningd --list-features-only` から `self.options` を組み立て、`has_option(...)` に `even`, `odd`, `true` を返しながら、同じクラス内で `Bitcoind` lifecycle と wallet compatibility も抱え込む。[`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) が指摘する capability leakage は、この混線の一症状にすぎない。

[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) は session state を connection 側へ寄せたいとしたが、そこでもまだ `Runner` contract の細分化までは終わっていない。Discord 断片で cdecker が `RunnerConn` の no-op 感と multiple connection での flexibility 低下を問題視したのは、connection object の有無ではなく「最小責務の切り方がまだ曖昧だ」ということを示している。

## Decision

core boundary は次の 5 面に固定する。

### `CapabilitySet`

`CapabilitySet` は、protocol-level capability と implementation-local toggle を分けて保持する。ここで扱うのは feature bit、role、support level、extension flag であり、表現は CLN 固有の `"even"`, `"odd"`, `"true"` にしない。値は少なくとも `required`, `supported`, `absent` を表現できる三値的な support level を持ち、必要なら metadata を追加できる shape にする。

この面を設けることで、`has_option("...")` を core contract から外せる。既存 Event DSL や helper が feature 判定を必要とする場合は、互換層が `CapabilitySet` を読んで従来の query をエミュレートする。

### `NodeAdapter`

`NodeAdapter` は node process と implementation-owned operation を受け持つ。core v1 で必須なのは `start`, `stop`, `restart`, `capabilities()` だけに絞る。`fund_channel`, `init_rbf`, `invoice`, `add_htlc`, `accept_add_fund` のような operation は optional extension として切り出し、phase 5 より前の stable boundary に入れない。

ここでの重要な判断は、「Lightning node に依存する helper operation は protocol conversation の最小 contract ではない」という点である。funding や RBF は重要なテスト題材だが、boundary 定義の起点にはしない。

### `PeerSession`

`PeerSession` は protocol conversation の最小面である。ここで必須とするのは `open/connect`、`send_raw` または `send_msg`、`recv_raw` または `recv_msg`、`disconnect`、session-local stash のみである。session state は runner 全体ではなく connection/session 単位で保持する。Vincenzo が Discord 断片で「stash logic make sense to be per-connection and not per-runner」と言い直した線を、この面で正式化する。

acceptance line は三つで固定する。`init` がこの面だけで書けること。disconnect / reconnect が session lifecycle として表現できること。`channel_reestablish` が session-local stash で扱えること。この三つを超える node-local operation は最初から必須にしない。

### `ChainBackend`

`ChainBackend` は Bitcoin 側の lifecycle と chain control を Lightning node adapter から分離する。core v1 では `block_height`, `mine_blocks`, `trim_blocks`, `expect_tx` を持つ。`bitcoind` wallet initialization や version compatibility はここで吸収し、Lightning node adapter が Bitcoin process 管理を当然に負う設計をやめる。

この分離で解きたいのは、「他実装向け runner を書きたいだけなのに CLN runner 的な bitcoind assumptions まで背負う」という問題である。[`issue #102`](https://github.com/rustyrussell/lnprototest/issues/102) はこの混線の一部を露出している。

### `LegacyRunnerAdapter`

`LegacyRunnerAdapter` は、現行 Event DSL と `Runner`-shaped API を新境界の上で維持する互換層である。ここにより `Runner` をいきなり delete するのではなく、旧 API を `CapabilitySet`, `NodeAdapter`, `PeerSession`, `ChainBackend` へ委譲する構成へ落とす。互換層があることで Event DSL を phase 2 の時点で壊さずに済み、authoring の刷新は phase 3 に分離できる。

## What This Solves By Phase

Phase 1 では、この boundary split 自体はまだ実装しない。ただし [`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) に対し、「core と runner package の ownership を分ける」と明文化することで、どこまでが core responsibility かを先に見やすくする。

Phase 2 でこの文書の設計を固定する。ここで解消されるのは、`Runner` の fat contract、CLN-shaped capability leakage、runner-wide stash 前提、session owner の曖昧さである。逆にこの phase では procedural syntax の final form や remote API はまだ決めない。

Phase 3 では `LegacyRunnerAdapter` の上に Event DSL と procedural API を並べることで、authoring 議論を boundary split の後段へ移す。

Phase 4 では `PeerSession` と `ChainBackend` のみで `init`, disconnect / reconnect, `channel_reestablish` を通すことで、この boundary が本当に小さくて足りるかを検証する。

Phase 5 では remote adapter が export する対象を `NodeAdapter` / `PeerSession` / `ChainBackend` に限定することで、fat `Runner` をそのまま RPC 化しないようにする。

## Non-Goals

この文書では次を決めない。

- `CapabilitySet` の Python class 具体形
- `NodeAdapter` extension の naming
- funding / RBF を optional extension にした後の helper API 群
- dummy runner を `PeerSession` 実装としてどう再配置するか

それらは設計の後続課題だが、ここでの判断に依存する。先に確定させるのは責務の owner と stable contract の幅だけである。

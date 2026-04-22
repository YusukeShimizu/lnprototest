# Problem Map

この文書は、`lnprototest` の redesign をめぐる公開議論を「どの問題が、どの source で、どの phase に回収されるか」という形に束ね直すための map である。ここで重要なのは、runner 分割や procedural 化を一つの大きな thread として扱わないことだ。実際の議論は、[`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105)、[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95)、[`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98)、[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128)、[`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131)、[`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133)、そして 2023-06-20 から 2023-07-04 にかけてのユーザー提供 Discord 断片に分散している。

## Three Problem Families

### 1. Runner Boundary Is Too Fat

もっとも構造的な問題は、現行 [`lnprototest/runner.py`](../lnprototest/runner.py) の `Runner` が session I/O、capability modelling、node lifecycle、Bitcoin backend、高水準 node operation を同じ contract に抱え込んでいることだ。`connect`、`recv`、`get_output_message` に加えて、`get_keyset`、`get_node_privkey`、`has_option`、`fundchannel`、`init_rbf`、`addhtlc`、`add_blocks`、`expect_tx` までを同一抽象が背負うので、他実装向け runner は protocol conversation を再利用したいだけでも CLN shaped な surface を埋める必要がある。

この問題を直接示しているのは [`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) と [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) である。`#98` は `has_option(...)` が C-Lightning 固有の文字列表現に依存していることを指摘し、`PR #95` は runner を stateless に、connection を stateful に寄せたいと提案する。Discord 断片でも、Vincenzo は runner 内の state machine を消したいと言い、cdecker は `RunnerConn` の no-op 感や multiple connection での柔軟性低下を懸念している。つまりここで争われているのは syntax ではなく、責務と state の owner である。

### 2. Test Authoring Is Harder Than It Needs To Be

現行 DSL は [`HACKING.md`](../HACKING.md) が説明する通り DAG 的実行器をすでに持っているが、test author が straight-line に session を追うには負荷が高い。Rusty は [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest) で `runner.choose([...])` を使った authoring prototype を示し、「関数分割ベースの composability は elegant だが test writing is awkward」という不満を明言している。`PR #95` はその流れの上で `RunnerConn` による procedural example を置き、[`cdecker/lnpt`](https://github.com/cdecker/lnpt) は decorator / DAG 的な別方向の authoring experiment を提示している。

この問題は [`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の 2024-11-11 の [コメント](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818) でも再登場する。ただしそこでは event-based complexity、typed messages、proxy PoC が近接して語られており、そのままだと「何を先に解けばよいか」がぼやける。したがって `design/` では、authoring friction を boundary design の後段に置き直す。

### 3. External Runner And Remote Decoupling Are Mixed Together

[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) は dependency split の必要性を直接記録している。CLN runner を使わないのに `pyln-client` や `grpcio` 由来依存に巻き込まれる install path は package architecture の問題であり、transport の問題ではない。一方、[`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) と [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) は [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) を相手にした external runner / workflow 実例であり、[`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) も implementation-owned な test package を持っている。

これとは別に、`#105` comment と [`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2) には proxy / sidecar 的な remote 化の線がある。ここを混ぜると、「runner を外へ出すには最初から gRPC が必要だ」という誤解が生じる。しかし公開実例はそうではない。external runner は remote transport なしでも成立しており、remote 化は boundary 固定後の optional bridge として扱うべきだ。

## Source To Problem To Phase

| Source | 主に語っている問題 | この bundle で回収する phase |
| --- | --- | --- |
| [`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) | redesign の総論、event complexity、procedural API、typed message、proxy | Phase 2-5 |
| [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) | stateless runner、stateful connection、procedural example | Phase 2-3 |
| [`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) | CLN-shaped capability leakage | Phase 2 |
| [`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) | dependency split、ownership split | Phase 1 |
| [`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) | external runner 実例 | Phase 1 |
| [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) | external runner を workflow へ取り込む実務 | Phase 1 |
| [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest) | straight-line authoring、`runner.choose([...])` | Phase 3 |
| [`cdecker/lnpt`](https://github.com/cdecker/lnpt) | decorator/DAG authoring experiment | Phase 3 |
| ユーザー提供 Discord 断片 | state machine 除去、per-connection stash、multiple connection 懸念 | Phase 2-3 |
| [`lnprototest` issue `#49`](https://github.com/rustyrussell/lnprototest/issues/49) | `channel_reestablish` proving target | Phase 4 |
| [`lightning/bolts` issue `#934`](https://github.com/lightning/bolts/issues/934) | outdated `channel_reestablish` behavior | Phase 4 |

## What Each Phase Actually Resolves

Phase 1 は package ownership の混線を解消する。ここで解くのは「なぜ CLN dependency が core に乗っているのか」「external runner が intended extension point なのか」という問題であり、authoring の自然さや remote API の形はまだ確定しない。

Phase 2 は boundary split を解消する。ここで解くのは `Runner` の fat contract、`has_option(...)` leakage、session state の owner 不在であり、procedural syntax の最終形ではない。`CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend`、`LegacyRunnerAdapter` の 5 面を固定するのはこの段階である。

Phase 3 は authoring layer の混線を解消する。ここで解くのは Event DSL と procedural API の関係であり、「どの syntax が良いか」より先に「境界の上に authoring choice を載せる」という整理を完成させる。

Phase 4 は proving scenario の不足を解消する。ここで解くのは、新境界が本当に `init`、disconnect / reconnect、`channel_reestablish` を扱えるかどうかである。広い feature matrix や implementation-specific helper はまだ要らない。

Phase 5 は remote decoupling を optional bridge として解消する。ここで解くのは process boundary 越しの adapter 実行であり、external runner の存在そのものではない。従って gRPC first にはしない。

## Deferred Problems

この bundle では、次の問題は関連論点として触れるが中心設計には置かない。

- `BLIP32` のような implementation-specific feature の共通化
- funding / RBF / invoice / HTLC helper の共通 contract
- typed-message code generator の入出力仕様
- BOLT `MUST` / `SHOULD` policy の全面整理
- dummy runner をいつ削除するかという project policy

これらは phase の後ろに回す。理由は単純で、boundary と proving scenario が固定されていない段階で helper API や policy だけを固めても、次の refactor で壊れるからである。

# Test Authoring

この文書は、Event DSL、procedural API、decorator / DAG experiment をどう位置づけるかを決める。ここでの結論は単純で、authoring 改善は boundary split の上に載る上位層であり、先に fix すべきものではない。どの syntax が良いかを先に争うのではなく、何が stable session seam かを先に固定する。

## The Problem Being Solved

現行 Event DSL は弱いのではなく、むしろ機能が多い。[`HACKING.md`](../HACKING.md) が説明する通り、test は `Events in a DAG` であり、`Sequence`, `OneOf`, `AnyOrder`, `TryAll` が実行器として分岐と探索を担っている。`tests/test_bolt1-01-init.py` や `tests/test_bolt2-02-reestablish.py` を見ると、`init` と `channel_reestablish` も現行 DSL 上で既に表現できている。したがって「DAG がないから redesign が必要」という理解は誤りである。

問題は authoring friction にある。Rusty は [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest) で `runner.choose([...])` を示し、minor variant を straight-line な Python の `if` として書ける自然さを重視した。`PR #95` はその流れで `Runner.connect(...) -> RunnerConn` の procedural example を置いている。Discord 断片でも Rusty は「message を普通の Python 変数として持ちたい」「stash すら不要にできる」と語り、Vincenzo は現行 lnprototest にこの書き味を取り込みたいとしている。

一方で cdecker は procedural 化そのものではなく、その背後にある session model を問題にしている。`RunnerConn` が no-op に見えること、auto-selected connection が strange であること、gossip / forwarding test のような multiple connection case で flexibility が落ちうることを指摘した。この応酬から分かるのは、authoring syntax と session boundary が切り離されていないと議論が混線するという事実である。

## Decision

authoring layer は三層で考える。

### Layer 1: Stable Session Seam

最下層は [`runner-boundary.md`](./runner-boundary.md) で定義した `PeerSession` である。ここでは `open/connect`, `send_raw/send_msg`, `recv_raw/recv_msg`, `disconnect`, session-local stash しか要求しない。この layer が確定しない限り、どんな authoring syntax も transport や capability の誤った仮定を含みやすい。

### Layer 2: Compatibility Layer

次に `LegacyRunnerAdapter` の上で現行 Event DSL を動かす。ここでの判断は「Event DSL を捨てない」である。既存の `ExpectMsg` partial match、ignore handler、`TryAll` による branch exploration は既に資産であり、これを phase 2 で破壊する理由はない。従来テストは可能な限りそのまま走り続けることを前提にする。

### Layer 3: Alternative Authoring Styles

その上に procedural authoring と decorator / DAG authoring を置く。procedural line の参照先は [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest) と [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) であり、decorator / DAG line の参照先は [`cdecker/lnpt`](https://github.com/cdecker/lnpt) である。ただし両者は boundary の代替ではなく、boundary の上に乗る authoring choice として扱う。

このとき procedural API の v1 で保証するものは限定する。`conn = session.open(...)` 相当の session handle を取得し、`recv_msg()`, `send_msg()`, `disconnect()` を使って straight-line に会話を書けること。これは smoke test にはなるが、boundary split の主証明ではない。主証明は、BOLT7 gossip filter のような multi-session case で peer ごとの state / expectation を分離できることと、BOLT2 `channel_reestablish` のように session state と chain observation が絡むケースを fat `Runner` に戻さずに書けることである。そこに `runner.choose([...])` 相当の variant helper や typed-message convenience を積むのは次段階とする。最初から branching DSL や decorator graph を core contract にしない。

## What This Solves By Phase

Phase 2 では authoring syntax はまだ変えない。その代わり `LegacyRunnerAdapter` を置ける boundary を固めて、Event DSL を守る前提を成立させる。

Phase 3 で authoring layer を再配置する。ここで解消されるのは、「Event DSL と procedural API はどちらが正しいか」という不毛な二択である。実際には両者は同じ minimal seam の上に共存できる。`lnprotest` の straight-line style は layer 3 の procedural API へ、`lnpt` の DAG experiment は別 authoring style へ、それぞれ位置づける。

Phase 4 では multi-session case と `channel_reestablish` abnormal case を主対象にし、`init` と disconnect / reconnect は補助 smoke として扱う。Event DSL と procedural API のどちらを使うかより、同じ session seam と chain backend seam で必要な conversation を表現できることを確認する。ここで proving target が成立しないなら authoring layer ではなく boundary split が誤っている。

Phase 5 では remote adapter を導入しても authoring layer が変わらないことを確認する。transport の違いで authoring API を作り替える設計は採らない。

## Non-Goals

この文書では次を決めない。

- procedural API の exact function names
- `runner.choose([...])` 相当 helper の final shape
- typed-message codegen の API surface
- decorator / DAG DSL を mainline に統合するかどうか

これらはすべて `PeerSession` seam の安定後に決める。ここで重要なのは、「authoring 改善の議論は必要だが、boundary split の代替ではない」と設計上はっきり線を引くことである。

# issue #105 への返信方針

今回の runner 分割は、手続き的なテスト構文を入れるためだけの提案ではない。主眼は、`lnprototest` 本体と外部 runner の境界を明確にし、テストケースを増やしやすい構造にすることである。

特に重要なのは、runner が本体外の package として提供される流れである。`ldk-lnprototest` のような out-of-tree runner が出てくるなら、`lnprototest` 本体が各実装の runner を抱え込む設計ではなく、外部 runner が実装しやすい core contract を持つ設計が必要になる。太い `Runner` interface をそのまま外部 package に要求すると、node lifecycle、connection transport、chain observation、implementation-specific helper が混ざったままになる。

この PoC では、その contract を三つの境界に分ける。

- `NodeAdapter` は node の起動、停止、capability、実装固有 helper を持つ。
- `PeerSession` は connection ごとの protocol stream を持つ。
- `ChainBackend` は block generation と mempool observation を持つ。

`LegacyRunnerAdapter` は、既存の Event DSL を壊さずに残すための互換層である。既存テストは従来通り `Connect`、`Msg`、`ExpectMsg`、`Block` などを使える。一方で内部の処理は、`NodeAdapter`、`PeerSession`、`ChainBackend` に委譲される。

Discord での議論に対する答えとしては、stash を中心に置かない。stash は既存 Event DSL との互換のために残る実装上の詳細である。Rusty の `lnprotest` 的な方向では、message を Python 変数として保持できれば stash は薄くできる。したがって、今回の提案で強調すべきなのは stash の移動ではなく、send / recv / disconnect / error expectation がどの connection に属するかを明示することである。

multi-session case は、この分割の最初の proving target である。既存の `tests/test_bolt7-10-gossip-filter.py` は、`connprivkey="05"` と `"06"` が同時に異なる gossip filter state を持つ実例になっている。現行 Event DSL でも書けるが、connection の owner が runner-wide に見えやすい。今回の `PeerSession` 分割では、connection ごとの protocol stream を独立した object として扱うため、gossip tests や forwarding tests のような複数接続のケースを整理しやすくなる。

`runner.choose` はまだ実装しない。`choose` は minor variant を自然に書くための authoring layer として有用だが、branch ごとの state owner が曖昧なまま入れると、runner-wide state machine を別の形で再導入する危険がある。まず `PeerSession` / `NodeAdapter` / `ChainBackend` の境界を固定し、その上に `choose` を載せる順序がよい。

issue #105 へ返すなら、次の要旨にするのが正確である。

今回の提案は、まず procedural syntax の変更として見るべきではない。より重要なのは runner contract の整理である。runner はすでに本体外へ出る流れがあるため、`lnprototest` 側は外部 runner が実装しやすい小さな surface を持つ必要がある。外部 runner package に、node lifecycle、connection transport、protocol I/O、chain observation が混ざった太い `Runner` interface をそのまま要求すべきではない。

この branch では、その surface を `NodeAdapter`、`PeerSession`、`ChainBackend` に分ける。同時に、`LegacyRunnerAdapter` によって既存 Event DSL は維持する。Discord で議論されていた multiple connection の問題に対して重要なのは `PeerSession` である。`PeerSession` は、send / recv / disconnect の owner を明示する。session-local stash は現在の Event DSL 互換のための詳細であり、設計の中心ではない。

したがって、最初の proof は straight-line procedural test だけでは不十分である。multi-session behavior を示す必要がある。既存の BOLT7 gossip-filter test はこの重要性をすでに示している。この branch の boundary test は、二つの session が protocol stream と lifecycle state を共有しないという低レベルの不変条件を固定する。BOLT2 `channel_reestablish` は、`ExpectNoTx` によって chain boundary を示す。

`runner.choose` は次の layer として扱う。branch state の owner が明確になってから追加する方が、runner-wide state machine を再導入しにくい。

この返信は、Discord 議論と out-of-tree runner の流れの両方に対応している。ただし、typed message、signing helper、`pyln.proto` rewrite、LDK 本家 CI への採用までは主張しない。今回の PoC が示すのは、その前段となる core boundary の整理である。

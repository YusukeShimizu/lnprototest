# lnprototest Design Bundle

この `design/` ディレクトリは、`lnprototest` の設計判断を implementation-oriented に固定するための bundle である。ここでの読者は、次のコード変更を実際に進めるエンジニアや別 agent であり、「背景を理解する」だけでなく「どの順番で、何を、どこまで決めた設計として扱うか」を追加判断なしで読めることを目標にする。

この fork では、`design/` を implementation-facing な設計入口として扱う。背景分析の補助資料は public issue / PR / prototype への link として appendix に集約し、実装時に最初に読むべきものはこの bundle だと固定する。

この bundle で固定する設計軸は三つだけである。第一に、fat `Runner` contract をどの責務に分解するか。第二に、Event DSL / procedural API / decorator DAG の議論をどう整理するか。第三に、runner と node の疎結合化をどの transport 順で進めるかである。これらはしばしば一つの redesign として語られるが、実際には別々の設計判断であり、着手順も異なる。

## Reading Order

1. [`problem-map.md`](./problem-map.md)
   2026-04-22 JST 時点で公開されている issue / PR / prototype / Discord 断片を、どの問題群に対応づけるかを固定する。
2. [`runner-boundary.md`](./runner-boundary.md)
   `Runner` の責務分割と、core 側に残す最小契約を決める。
3. [`test-authoring.md`](./test-authoring.md)
   authoring 改善を boundary の上位層としてどう扱うかを決める。
4. [`test-case-roadmap.md`](./test-case-roadmap.md)
   `runner-boundary.md` と `test-authoring.md` の proving step として、最初に executable にする multi-session / chain-boundary テストケースを固定する。
5. [`bolt8-test-gap.md`](./bolt8-test-gap.md)
   BOLT8 encrypted transport の不足テストを、post-handshake `PeerSession` と raw transport harness の境界に分けて整理する。
6. [`issue-105-feedback.md`](./issue-105-feedback.md)
   public issue #105 へ返すための argument を、multi-session test expansion を中心に整理する。
7. [`remote-adapter.md`](./remote-adapter.md)
   `stdio` / Unix socket / HTTP / gRPC の導入順序と非目標を固定する。
8. [`migration-phases.md`](./migration-phases.md)
   各 phase で何が解消され、何がまだ残るかを migration path として確定する。
9. [`appendix-links.md`](./appendix-links.md)
   証拠 URL、private Discord の扱い、公開ソースとの対応関係を参照する。

## Decision Summary

この bundle で先に固定する大枠は次の通りである。

- `external runner 化` と `core boundary 改善` は別工程として扱う。
- `Runner` は最終的に `CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend`、`LegacyRunnerAdapter` に分かれる。
- v1 の stable contract は `PeerSession` 中心であり、multi-session state、`init`、disconnect / reconnect、`channel_reestablish` を扱えることを acceptance line にする。
- BOLT8 は `PeerSession` の下にある raw transport として扱い、unit vector は test-only harness、live malformed handshake は raw probe で確認する。
- Event DSL は捨てず、互換層の上位 API として残す。procedural API はその後に足す。
- remote adapter は boundary 固定後に導入する。初手は `stdio` か Unix socket sidecar であり、gRPC は最初の transport ではない。
- `BLIP32` のような feature-specific extension は core v1 の境界に含めず、implementation-owned external test package で先行させる。

## Non-Goals

この bundle は次を直接は決めない。

- 実際の Python package split のファイル構成
- gRPC / HTTP の wire schema 詳細
- typed-message codegen の生成器仕様
- funding, RBF, invoice, HTLC helper の cross-implementation contract
- dummy runner を最終的に削除するかどうかの project policy

それらは無関係なのではなく、順序上まだ決めないという意味で deferred である。先に固めるべきは boundary と proving scenario であり、ここを飛ばして transport や helper API を確定させない。

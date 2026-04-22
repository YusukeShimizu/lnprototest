# lnprototest アーキテクチャ再構成メモ

この bundle は、`lnprototest` の現状を単に棚卸しするためのものではなく、「理想形を先に置き、その理想形から見て今どこが詰まっているのか」を整理するための内部設計メモである。確認日の基準は 2026-04-22 JST であり、GitHub 上の issue / PR / release / commit、手元の checkout、`pr-95` ブランチ、そして [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) / [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) 周辺の外部 runner 実例を参照している。加えて、2023-06-20 から 2023-07-04 にかけての Discord 議論については、ユーザー提供の一次ログ断片を補助資料として使っている。

最初に結論を固定しておく。理想形は、`lnprototest` core を protocol-conversation engine と共通 test library に絞り込み、各 Lightning 実装向けの adapter は runner package として外へ切り出し、feature test は実装 repo か外部 repo で first-class に持たせる構成である。現在の blocker は Python そのものではなく、現行 `Runner` が capability modeling、peer transport、node lifecycle、chain backend、高水準 node operation をまとめて抱え込んだ fat contract になっている点にある。

もうひとつ先に切り分けておきたいのは、「external runner 化」と「core boundary の改善」は同じ話ではない、という点だ。公開された議論をたどると、[Rusty の `lnprotest` prototype](https://github.com/rustyrussell/lnprotest) は straight-line な test authoring と `runner.choose([...])` を、[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) は stateless runner と `RunnerConn` を、[`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) は `has_option(...)` leakage を、[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) は dependency split を、[`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) と [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) は LDK 寄りの外部 runner / workflow 実務をそれぞれ扱っているが、これらを一本の thread が統合しているわけではない。このメモは、その分散した材料を束ね直し、「理想設計から逆算すると何を先に固定すべきか」という観点で再構成したものである。

この前提に立つと、次の一手は rewrite でも gRPC でもない。まず `CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend` という 4 つの境界を固定したうえで、`Runner` は互換層か composition root としてだけ残すべきである。remote adapter はその後の話であり、しかも初手は `stdio` か Unix socket sidecar で十分である。control plane が安定する前に gRPC を選んでしまうと、fat contract を別 transport へ焼き直すだけで終わる。

## Bundle Map

- `01-current-state.md`: 2026-04-22 時点の公開議論を、2023-06 の Discord / `lnprotest` prototype line も含めて、`external runner 化` と `core boundary 再設計` の二軸で読み直す。
- `02-runner-boundary.md`: `Runner` の責務を packaging、responsibility、transport の 3 面から分解し、理想境界を `CapabilitySet` / `NodeAdapter` / `PeerSession` / `ChainBackend` に固定する。
- `03-test-authoring-and-dag.md`: Event DSL、procedural API、decorator DAG を「境界の上に乗る authoring choice」として整理し、minimal session API を先に定義する。
- `04-grpc-runner-evaluation.md`: gRPC 単独の評価ではなく、`stdio` / Unix socket / HTTP / gRPC を remote adapter option として並べて比較し、なぜ gRPC を初手にしないのかを明確にする。
- `05-recommended-path.md`: dependency split と external-runner posture の明文化から始める、段階的な migration path を示す。
- `appendix-evidence.md`: 日付つきの確認元と、Lampo / LDK-Sample の外部 runner 実例をまとめる。

## 推奨読み順

1. `01-current-state.md` で、「議論がない」のではなく「議論が分散している」状態を押さえる。
2. `02-runner-boundary.md` で、external runner 化だけでは解決しない fat contract の存在を明確にする。
3. `03-test-authoring-and-dag.md` で、authoring の議論を minimal session boundary の後ろへ置き直す。
4. `04-grpc-runner-evaluation.md` で、remote adapter は boundary 固定後の選択肢であることを確認する。
5. `05-recommended-path.md` で、実際の変更順を確認する。

## Acceptance Lens

この bundle は、absolute date を維持し、推測と proposal を明確に分けて使うことを前提としている。とりわけ、`external runner 化` と `core boundary 改善` は別個の達成条件として扱う。前者は packaging と ownership の問題であり、後者は stable contract の問題だからである。また minimal session API は、少なくとも `init`、disconnect / reconnect、`channel_reestablish` の 3 ケースで妥当性を説明できることを要求する。

## Short Conclusion

理想設計から見ると、`lnprototest` は protocol-conversation engine と共通 test library に絞り込まれるべきであり、runner は各実装側へ寄せるのが自然である。これは [`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131)、[`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs)、[`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) のような外部 runner 実例とも整合する。ただし、external runner が存在するだけでは不十分で、core がいまの fat `Runner` 契約を抱えたままなら、外へ出した adapter がその歪みをそのまま引き継ぐだけになる。

実務的な次の一手は二層に分けるのがよい。理想設計としては `CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend` を first-class boundary に固定し、`Runner` を互換層へ落とす。現実的な進め方としては、まず [`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) の dependency split と external-runner posture を明文化し、続いて minimal session API を切り出して `init` と `channel_reestablish` で検証し、remote adapter は最後に optional な bridge として選ぶ。

`BLIP32` のような feature は、この最初の境界定義の中心には置かない。まずは implementation-owned な外部 test package で扱い、共通 seam として upstream へ戻せる部分だけを後で抽出するのが安全である。

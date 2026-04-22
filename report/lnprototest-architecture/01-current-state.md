# 01. Current State

この章の目的は、2026-04-22 時点の公開材料を「どこに理想設計の断片が存在し、どこがまだつながっていないのか」という観点から読み直すことにある。ここで重要なのは、「runner 分割の大方針を説明した一本の issue や PR がある」と期待しないことだ。実際の議論は、2023-06 の Discord で出た [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest) prototype、[`PR #94`](https://github.com/rustyrussell/lnprototest/pull/94) の implementation compatibility 改善、[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) の stateless runner / `RunnerConn`、[`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) の capability leakage、[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) の packaging pain、そして [`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) と [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) の LDK 向け外部 runner / workflow 実務というかたちで、別々の場所に分散している。

## 現状

公開議論のハブとして最も明示的なのは [`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) である。`#105` は 2023-08-24 に opened され、body では [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) を design experimentation として直接参照しつつ、Rust rewrite を先にやるつもりはないと明言している。さらに 2024-11-11 の [コメント](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818) では、現行ライブラリの複雑さ、event-based authoring の負担、procedural API への寄せ方、strictly typed message、そして proxy PoC までが、一つの redesign 課題として語られている。つまり「現状に不満がある」というより、「どこを redesign したいのか」はすでにかなり言語化されている。

ただし、この流れの起点をより正確にたどると、`#105` より前の 2023-06-20 から 2023-07-04 にかけての Discord 議論が重要になる。ユーザー提供のログ断片によれば、Rusty は [`lnprotest`](https://github.com/rustyrussell/lnprotest) を示しつつ、「関数境界をまたいだ composability は elegant だが test が awkward になるのが今の不満であり、`runner.choose([...])` で分岐を straight-line な Python の中に書けるようにしたい」と説明している。Vincenzo はそれに対し、「hack を入れれば現行 lnprototest に統合できそうだ」「runner 内の state machine を消したい」と応じている。ここでの論点は、まだ transport ではなく、test authoring と state の置き場所だった。

Discord の直後に見えてくるのが [`PR #94`](https://github.com/rustyrussell/lnprototest/pull/94) である。`#94` は 2023-06-19 に opened され、body では `runner_features()` を runner class に追加して「implementation が必要とする features を lnprototest 側から送れるようにし、他 implementation との互換性を上げる」と説明している。Discord 断片でも Vincenzo は 2023-06-24 に [この review](https://github.com/rustyrussell/lnprototest/pull/94#pullrequestreview-1496402602) を参照しており、authoring の議論と implementation compatibility の作業が並行して進んでいたことが分かる。

一方、実際の code-level experimentation は [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) に寄っている。PR `#95` は 2023-07-03 に draft として作られ、2025-04-10 に更新されたが、2026-04-22 時点でも open / draft / unmerged のままである。body では runner を stateless にし connection を stateful に寄せる方針が示され、`RunnerConn` を軸に procedural authoring を試しつつ、[`cdecker/lnpt`](https://github.com/cdecker/lnpt) が authoring idea の参照先として置かれている。ここから読み取れるのは、「runner 分割」は transport の議論より先に session responsibility の議論として始まっていた、ということだ。

しかも Discord の 2023-07-04 のやり取りを見ると、その争点はかなり具体的である。cdecker は `RunnerConn` ラップが no-op に見えること、runner 側の auto-selected connection が不自然であること、gossip test や forwarding test のように複数接続を扱う場合には柔軟性が落ちることを懸念している。Vincenzo はこれに対し、「本当にやりたいのは `runner.connect()` が connection を返して procedural に扱えることだ」「stash も per-runner ではなく per-connection のほうが自然になる」と言い直している。ここで既に、後の report でいう `PeerSession` 的な境界が暗に問題化していた。

別の角度から同じ問題を示しているのが [`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98) と [`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) である。`#98` は 2023-07-13 に、`has_option(...)` が CLN 特有の文字列表現に依存しすぎていると指摘した。これは単なる API naming の問題ではなく、capability modeling が core 抽象ではなく CLN 互換層として設計されていることの露出だと言える。`#128` は 2024-11-24 に、CLN runner を使わないのに `pyln-client` や `grpcio` 由来の重い依存に巻き込まれる packaging pain を記録している。こちらは install path の痛みとして現れているが、本質は `core` と `implementation-owned runner` の dependency boundary が崩れていることにある。

external runner の実務的な線は [`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) と [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) に現れる。PR `#131` は 2025-01-22 に opened され、body では [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) を `lnprototest` framework と通信させる runner script だと説明されているが、2025-03-21 に close され未 merge のまま終わった。その直後の PR `#133` は 2025-03-21 に opened され、2025-04-01 に merged されて、LDK workflow と dockerfile を mainline に入れた。つまり upstream は「LDK を完全に generic runner abstraction へ載せた」わけではないが、「外部の LDK 実装を対象にした test wiring を workflow と Docker の形で持ち込む」ところまでは受け入れている。

この redesign line が未統合であっても、repo 自体が止まっているわけではない。release `v0.0.7` は 2025-04-10 に公開され、`master` の最新コミット `aa6d80a` は 2025-06-19 の dependency bump である。止まっているのは redesign の landing であって、maintenance 全体ではない。

## 理想形

理想形は、公開議論をつなぎ合わせるとかなり明確になる。`lnprototest` core は protocol-conversation engine と共通 test library に集中し、各実装ごとの runner は implementation-owned adapter package として外へ出す。実装差分の大きい feature test は、まず実装 repo あるいは外部 repo で first-class に育て、共通化できる seam だけを後から upstream に戻す。2023-06 の Discord で Rusty が示した [`lnprotest`](https://github.com/rustyrussell/lnprotest) は straight-line authoring の prototype として、[`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) の [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) runner と [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) 側の `tests/lnprototest` ディレクトリは implementation-owned runner の prototype として、この理想形を別々の面から先取りしている。

この理想形では、「core に残すべきもの」と「runner package に切り出すべきもの」の境界が先に決まっている。capability は `has_option(...)` ではなく構造化された shape に正規化され、session は `Runner` ではなく connection 単位で状態を持ち、chain backend は Lightning node adapter と切り離される。remote transport はこの boundary が定まったあとに選ぶ補助手段であって、設計の出発点ではない。

## ギャップ

現状と理想形のズレは二段階に分かれる。第一に、external runner の方向性そのものは packaging と workflow の実務で既に現れているのに、core 側ではそれを支える最小契約がまだ固定されていない。第二に、authoring の議論、typed message の議論、proxy / remote 化の議論が、同じ redesign の話としてまとめて語られやすく、どこから着手すべきかがぼやけている。

特に誤解しやすいのは、「`#131` や Lampo のような外部 runner 実例があるのだから、あとは remote 化を進めればよい」という見方だ。実際には、外へ出た runner が現行の `Runner` 契約をそのまま実装している限り、fat contract と CLN-shaped capability checks も一緒に外へ運ばれてしまう。external runner 化だけでは、core boundary の問題は解決しない。

また typed message や code generator も重要だが、minimal session API より先に stable contract へ組み込むべきではない。`#105` コメントの problem statement では両者が近くに置かれているものの、理想設計から見れば、typed message は minimal transport seam の上に乗る第二段階の整理である。

## 次の一手

ここからの読み方は単純で、「議論がないから新しく作る」ではなく、「既にある分散した議論を、理想設計に沿って順序づけ直す」である。最初にやるべきは、external-runner posture を明文化しつつ、core 側で `Runner` 契約を縮めることだ。具体的には、`#128` が示した dependency split を packaging の入口に、`#95` が示した connection-centric な発想を session boundary の入口に、そして `#98` が示した capability leakage を contract cleanup の入口に据える。

検証対象としては `init`、disconnect / reconnect、`channel_reestablish` がちょうどよい。`lightning/bolts` issue `#934` と `lnprototest` issue `#49` は、session-local state と reconnect semantics を検証する practical な target になっており、remote 化を始める前に minimal boundary の妥当性を問う材料として適している。

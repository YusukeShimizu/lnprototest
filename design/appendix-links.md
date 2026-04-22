# Appendix Links

確認基準日: 2026-04-22 JST

この appendix は `design/` bundle で参照する source と、その取り扱い方針をまとめる。ここでは設計判断に直接関係する URL と引用方針だけを残し、実装時に必要な evidence anchor をこの bundle 内で完結させる。

## Public Sources

- [`lnprototest` issue `#105`](https://github.com/rustyrussell/lnprototest/issues/105)
- [`lnprototest` issue `#105` comment by `vincenzopalazzo` on 2024-11-11](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818)
- [`lnprototest` pull request `#95` `[WIP] lnprototest refactoring`](https://github.com/rustyrussell/lnprototest/pull/95)
- [`lnprototest` issue `#98` `The has_option method is really specific to C-Lightning`](https://github.com/rustyrussell/lnprototest/issues/98)
- [`lnprototest` issue `#128` `do not depend on core lightning dependencies when not running the cln runner`](https://github.com/rustyrussell/lnprototest/issues/128)
- [`lnprototest` pull request `#131` `Runner script for LDK added`](https://github.com/rustyrussell/lnprototest/pull/131)
- [`lnprototest` pull request `#133` `LDK workflow and dockerfile added`](https://github.com/rustyrussell/lnprototest/pull/133)
- [`lnprototest` issue `#49` `bolt2: implementing test to clarify channel reestablish failure`](https://github.com/rustyrussell/lnprototest/issues/49)
- [`lightning/bolts` issue `#934` `Nodes shouldn't publish their commitment when receiving outdated channel_reestablish`](https://github.com/lightning/bolts/issues/934)
- [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest)
- [`cdecker/lnpt`](https://github.com/cdecker/lnpt)
- [`lnspec-tools/ln-fundamentals`](https://github.com/lnspec-tools/ln-fundamentals)
- [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample)
- [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs)
- [`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2)
- [`PR #94` `runner_features added in runner.py and tests modified`](https://github.com/rustyrussell/lnprototest/pull/94)
- [`PR #94` review `#1496402602`](https://github.com/rustyrussell/lnprototest/pull/94#pullrequestreview-1496402602)

## Private Discord Handling

2023-06-20 から 2023-07-04 にかけての Discord 議論は、ユーザー提供の一次ログ断片として参照する。public permalink は手元にないため、`design/` bundle では Discord 自体を source of record にしない。代わりに以下の公開材料へ対応づけて使う。

- `runner.choose([...])` と straight-line authoring
  対応先: [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest)
- stateful connection / stateless runner
  対応先: [`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95)
- implementation compatibility の並行作業
  対応先: [`PR #94`](https://github.com/rustyrussell/lnprototest/pull/94) と [review `#1496402602`](https://github.com/rustyrussell/lnprototest/pull/94#pullrequestreview-1496402602)
- decorator / DAG inspiration
  対応先: [`cdecker/lnpt`](https://github.com/cdecker/lnpt)
- typed-message / BOLT CI integration の検討先
  対応先: [`lnspec-tools/ln-fundamentals`](https://github.com/lnspec-tools/ln-fundamentals)

Discord 由来の記述を本文で使うときは、「ユーザー提供の Discord 断片によれば」と明示し、その直後に対応する公開 source を並べる。private log の内容だけで設計を固定しない。

## Citation Rules For `design/`

`design/` bundle の本文では次の書き方を守る。

- fact は public URL で裏づける
- proposal は `この bundle では ... と決める` のように proposal と分かる書き方をする
- absolute date が意味を持つ場合は日付を書く
- private Discord は補助資料と明記する

このルールで、design bundle の decision-complete prose と公開 source の対応関係が曖昧にならないようにする。

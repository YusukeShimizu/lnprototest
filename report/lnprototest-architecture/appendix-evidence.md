# Appendix: Evidence

確認日: 2026-04-22 JST

この appendix は、本文で使った事実の確認元をまとめたものである。Issue / PR / release / commit の state と日付は GitHub 公開ページと `gh api` の両方で照合した。コードに関する観察はローカル checkout、`pr-95` ブランチ、外部 runner 実例の公開 repo / branch から読んでいる。

## GitHub Issues And PRs

- [`lnprototest` issue `#105` `Feedback: Gather feedback on the usage of 'lnprototest' in the implementation`](https://github.com/rustyrussell/lnprototest/issues/105)
  確認: 2026-04-22 JST
  備考: open。作成 2023-08-24、更新 2024-11-11。body で PR `#95` を design experimentation として参照し、Rust rewrite は先送りすると明記している。

- [`lnprototest` issue `#105` comment by `vincenzopalazzo`](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818)
  確認: 2026-04-22 JST
  備考: 作成 2024-11-11。event-based complexity、procedural API、strictly typed messages、HTTP proxy PoC を redesign 課題として列挙している。

- [`lnprototest` pull request `#95` `[WIP] lnprototest refactoring`](https://github.com/rustyrussell/lnprototest/pull/95)
  確認: 2026-04-22 JST
  備考: open draft。作成 2023-07-03、更新 2025-04-10。body で stateless runner / stateful connection、procedural test example、`lnpt` 参照を説明している。

- [`lnprototest` issue `#98` `The has_option method is really specific to C-Lightning`](https://github.com/rustyrussell/lnprototest/issues/98)
  確認: 2026-04-22 JST
  備考: open。作成 2023-07-13、更新 2023-07-13。CLN 固有の `options` 文字列表現が他 runner を困らせると明記している。

- [`lnprototest` issue `#128` `do not depend on core lightning dependencies when not running the cln runner`](https://github.com/rustyrussell/lnprototest/issues/128)
  確認: 2026-04-22 JST
  備考: open。作成 2024-11-24、更新 2024-11-24。LDK runner の反復作業の文脈で `pyln-client` や `grpcio` 由来の install pain を記録している。

- [`lnprototest` pull request `#131` `Runner script for LDK added`](https://github.com/rustyrussell/lnprototest/pull/131)
  確認: 2026-04-22 JST
  備考: closed、未マージ。作成 2025-01-22、close 2025-03-21。body は [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) と lnprototest framework を通信させる runner script だと説明している。

- [`lnprototest` pull request `#133` `LDK workflow and dockerfile added`](https://github.com/rustyrussell/lnprototest/pull/133)
  確認: 2026-04-22 JST
  備考: merged。作成 2025-03-21、merge 2025-04-01。body は [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) integration workflow と dockerfile 追加を説明している。

- [`lnprototest` issue `#49` `bolt2: implementing test to clarify channel reestablish failure`](https://github.com/rustyrussell/lnprototest/issues/49)
  確認: 2026-04-22 JST
  備考: open。作成 2022-04-22。`lightning/bolts #934` を直接参照し、integration testing で clarification を得たいとしている。

## Discord And Prototype Line

- ユーザー提供の Discord 議論断片
  確認: 2026-04-22 JST
  備考: 2023-06-20 から 2023-07-04 の発言断片。public permalink は提供されていないため、この report では一次ログ断片としてのみ参照した。主な論点は `lnprotest` prototype、state machine を runner から外したいという意図、stash の per-connection 化、typed message / `pyln.proto` 再設計、`RunnerConn` と複数 connection の扱いである。

- [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest)
  確認: 2026-04-22 JST
  備考: 作成 2023-06-19。Discord で Rusty が提示した prototype。README には `runner.choose([...])` と straight-line な `if` を使った test authoring の例が書かれている。

- [`lnprototest` pull request `#94` `fix: runner_features added in runner.py and tests modified`](https://github.com/rustyrussell/lnprototest/pull/94)
  確認: 2026-04-22 JST
  備考: opened 2023-06-19、merged 2023-07-11。body では `runner_features()` を導入して implementation compatibility を高めると説明している。

- [`PR #94` review `#1496402602` by `vincenzopalazzo`](https://github.com/rustyrussell/lnprototest/pull/94#pullrequestreview-1496402602)
  確認: 2026-04-22 JST
  備考: submitted 2023-06-24。Discord 断片でも `@Psycho-Pirate I like this` として参照されていた review。

- [`cdecker/lnpt`](https://github.com/cdecker/lnpt)
  確認: 2026-04-22 JST
  備考: 作成 2023-06-15。`PR #95` body から参照される decorator / DAG experiment。

- [`lnspec-tools/ln-fundamentals`](https://github.com/lnspec-tools/ln-fundamentals)
  確認: 2026-04-22 JST
  備考: Discord 断片で Vincenzo が typed message / BOLT CI integration の検討先として言及していた公開 repo。

## Releases And Commits

- [最新リリース `v0.0.7`](https://github.com/rustyrussell/lnprototest/releases/tag/v0.0.7)
  確認: 2026-04-22 JST
  備考: 公開 2025-04-10。

- [確認時点の `master` 最新コミット `aa6d80a2760d3d6a8ee189fa34d60d65e3e1ed00`](https://github.com/rustyrussell/lnprototest/commit/aa6d80a2760d3d6a8ee189fa34d60d65e3e1ed00)
  確認: 2026-04-22 JST
  備考: `build(deps): bump requests from 2.32.3 to 2.32.4`。author date 2025-06-19。

- [直前のメンテナンスコミット `3a24e7dbcdfb454ff2a0c746649e5e43118e68e3`](https://github.com/rustyrussell/lnprototest/commit/3a24e7dbcdfb454ff2a0c746649e5e43118e68e3)
  確認: 2026-04-22 JST
  備考: `build(deps): bump urllib3 from 2.4.0 to 2.5.0`。同日 2025-06-19 の maintenance line。

## BOLTs Discussion

- [`lightning/bolts` issue `#934` `Nodes shouldn't publish their commitment when receiving outdated channel_reestablish`](https://github.com/lightning/bolts/issues/934)
  確認: 2026-04-22 JST
  備考: open。作成 2021-11-08、更新 2023-01-16。古い `channel_reestablish` 受信時の期待挙動を明文化している。

- [`lightning/bolts` issue `#1328` `Lightning Specification Meeting 2026/04/06`](https://github.com/lightning/bolts/issues/1328)
  確認: 2026-04-22 JST
  備考: closed。作成 2026-03-23、close 2026-04-20。

- [`lightning/bolts` issue `#1332` `Lightning Specification Meeting 2026/05/04`](https://github.com/lightning/bolts/issues/1332)
  確認: 2026-04-22 JST
  備考: open。作成 2026-04-20。

## Local Checkout Evidence

- リポジトリパス: `/Users/bruwbird/projects/github.com/rustyrussell/lnprototest`
- 確認ブランチ: `master`
- ローカルブランチ `pr-95`: `tests/test_v2_bolt1-01-init.py` に procedural `RunnerConn` 例があり、`lnprototest/runner.py` に `RunnerConn.recv_msg()` / `send_msg()` が実装されていることを確認した。
- 参照したファイル:
  - `README.md`
  - `HACKING.md`
  - `pyproject.toml`
  - `lnprototest/runner.py`
  - `lnprototest/dummyrunner.py`
  - `lnprototest/clightning/clightning.py`
  - `lnprototest/backend/bitcoind.py`
  - `tests/test_bolt1-01-init.py`
  - `tests/test_bolt2-02-reestablish.py`
  - `.github/workflows/testing.yml`
  - `docker/Dockerfile.ldk`
  - `docker/ldk-entrypoint.sh`

## External Runner Examples

- [`Psycho-Pirate/lnprototest` branch `ldk_runner`](https://github.com/Psycho-Pirate/lnprototest/tree/ldk_runner)
  確認: 2026-04-22 JST
  備考: PR `#131` の head branch。`lnprototest/ldk/ldk.py` が LDK-Sample 向けの `Runner` 実装を持ち、外部 runner を fork 側で first-class に育てていた実例。

- [`rustyrussell/lnprototest` current `master` `docker/Dockerfile.ldk`](https://github.com/rustyrussell/lnprototest/blob/master/docker/Dockerfile.ldk)
  確認: 2026-04-22 JST
  備考: `docker/Dockerfile.ldk` は `Psycho-Pirate/ldk-sample.git` を clone して build し、`pip install ldk-lnprototest` と `docker/ldk-entrypoint.sh` を通じて LDK 側 adapter package を外部依存として扱っている。

- [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs)
  確認: 2026-04-22 JST
  備考: `tests/lnprototest/lampo_lnprototest/runner.py` が Lampo 向け runner 実装を repo 内 package として持ち、`docker/lnprototest-entrypoint.sh` が `tests/lnprototest` に移動して `poetry run make check` を実行する。implementation-owned external test package の実例として扱える。

- [`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2)
  確認: 2026-04-22 JST
  備考: `cmd/main.go` と `lnprototest-cli/src/main.rs` が `lnprototestd` / Unix socket 経由の proxy PoC を持ち、`#105` コメントで言及された proxy 方向の補助証拠になる。

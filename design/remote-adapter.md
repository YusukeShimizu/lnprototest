# Remote Adapter

この文書は、runner と node の疎結合化を remote adapter としてどう進めるかを決める。先に結論を書くと、remote 化は必要になりうるが最初の設計判断ではない。先に boundary を fix し、その最小面を process boundary 越しに通せることを軽い transport で確認する。gRPC は最初の選択肢ではない。

## The Problem Being Solved

remote 化の動機は複数ある。[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) が示す dependency split、[`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) / [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) や [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) が示す implementation-owned external runner、[`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の 2024-11-11 の [コメント](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818) が示す HTTP proxy PoC である。これらはすべて「core と実装の結合を弱めたい」という大きな方向では一致している。

しかし remote 化だけでは解かない問題もある。現行 `Runner` をそのまま RPC 化したら、`has_option(...)`, `get_node_privkey()`, `fundchannel(...)`, `init_rbf(...)` のような fat contract と CLN bias が、そのまま network boundary に焼き付く。これは decoupling ではなく coupling の固定化である。従って remote adapter は [`runner-boundary.md`](./runner-boundary.md) の boundary split 後にしか設計してはいけない。

## Decision

remote adapter が export してよいのは `NodeAdapter`, `PeerSession`, `ChainBackend` の最小面だけである。Lightning message 本体は raw wire bytes か既存 parser / serializer を通して扱い、別 IDL に全面複製しない。`CapabilitySet` は control plane の metadata として返せばよいが、Lightning message 全体を `.proto oneof` に起こす設計は採らない。

transport の導入順は次で固定する。

### First: `stdio`

最初の選択肢は `stdio` である。理由は最も安価で、local subprocess との相性が良く、control plane がまだ動いている段階でも schema lock-in が小さいからだ。external runner を別 process へ逃がしても `init`, disconnect / reconnect, `channel_reestablish` が通るかを見るだけなら、これで十分である。

### Second: Unix Socket Sidecar

次に Unix socket sidecar を比較対象にする。ローカルマシン前提なら `stdio` より session handle や multiplex の面が整理しやすく、[`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2) の PoC とも整合する。ここでのゴールは generated client ではなく、軽い process boundary を保ったまま control plane を少しだけ明確にすることだ。

### Third: HTTP

HTTP は PoC としては扱いやすいが、request / response 思考に寄りやすく、session-oriented な read loop や disconnect timing を無理に request semantics に押し込む危険がある。従って comparison target には置くが、初手としては推奨しない。

### Last: gRPC

gRPC は最後に比較評価する。双方向 streaming、generated clients、cross-language tooling に利点はあるが、`PeerSession` と `CapabilitySet` の最小面が固まる前に `.proto` を書くと誤った責務分割を長期安定 API として保存してしまう。gRPC が悪いのではなく、「正しい boundary が見えていない時点で最も schema-heavy な transport を選ぶ」のが悪い。

## What This Solves By Phase

Phase 1 では remote transport をまだ決めない。ここで解くのは package ownership と dependency split であり、transport の問題ではない。

Phase 2 で「何を remote に出してよいか」を fix する。ここで export 対象を `NodeAdapter`, `PeerSession`, `ChainBackend` に限定し、現行 `Runner` 全体を transport boundary に乗せない方針を確定する。

Phase 3 では authoring layer が transport 非依存であることを守る。Event DSL でも procedural API でも、同じ `PeerSession` seam を使うので、transport が変わっても authoring を作り直さない。

Phase 4 では remote adapter なしで `init`, disconnect / reconnect, `channel_reestablish` を proving target として成立させる。これが通らないなら remote 化以前に boundary split が未完である。

Phase 5 で `stdio` first, Unix socket second の順に lightweight bridge を評価する。ここで初めて remote 化が解消するのは、「implementation-owned runner を別 process / 別 runtime へ逃がしたい」「core package から runner runtime を分離したい」という要求である。gRPC は multi-host 運用、generated client、長期安定 API の必要が明確になった場合だけ再評価する。

## Non-Goals

この文書では次を決めない。

- wire schema の JSON shape
- gRPC service definition
- auth / ACL / TLS model
- multi-host deployment topology

これらは必要になってから詰めればよい。最初の判断で必要なのは、「remote 化は optional bridge であり、boundary cleanup の代替ではない」とはっきり書くことである。

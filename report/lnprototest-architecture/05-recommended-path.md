# 05. Recommended Path

ここまでの議論を踏まえると、推奨 path は「external runner を認めること」と「core の最小境界を固定すること」を別工程として進める形になる。理想設計は強く意識するが、最初から全部を mainline に載せる必要はない。むしろ phase を分けたほうが、どこで abstraction が破綻したのかを見失わずに済む。

## Phase 1: Dependency split と external-runner posture の明文化

最初にやるべきことは remote 化でも procedural API でもない。[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) が示した packaging pain を受け、`lnprototest` core は CLN dependency を前提にしないこと、そして runner package は implementation-owned adapter として外へ切り出しうることを、README / packaging / developer docs のレベルで明文化する。ここでの目標は、[`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) や [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) のような外部 runner 実例を「例外的な fork 作業」ではなく、意図された拡張点として位置づけ直すことにある。

この phase で必要なのは ownership の整理であって、stable remote API の定義ではない。`external runner 化` を upstream posture として認めるだけでも、core に残すべき責務を狭く捉えやすくなる。

## Phase 2: Minimal session boundary の固定

次に、core 側の最小境界を `CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend` に固定する。ここで v1 の必須境界に入れるのは `PeerSession` の最小 API だけである。`open/connect`、`send_raw` または `send_msg`、`recv_raw` または `recv_msg`、`disconnect`、そして session-local stash。この面だけで `init` と reconnect conversation を表現できるところまで contract を縮める。

Event DSL はこの時点では捨てない。`LegacyRunnerAdapter` のような互換層として残し、新しい境界の上でそのまま動かせる形にしておく。procedural authoring や typed-message layer も重要だが、ここでは二次的な関心事として扱い、minimal boundary より後ろへ置く。

## Phase 3: `init` と `channel_reestablish` で境界を検証する

新しい境界の妥当性は、広い feature matrix ではなく狭い conversation で検証する。最初に通すべきは `init` であり、これは handshake と message I/O だけで成立する最小ケースである。次に disconnect / reconnect を通し、そのうえで `channel_reestablish` を検証する。`channel_reestablish` は session-local stash、再接続 semantics、capability negotiation のうち何が core に必要かを露出させるため、minimal boundary の評価対象として最も都合がよい。

検証の題材としては [`lnprototest issue #49`](https://github.com/rustyrussell/lnprototest/issues/49) と [`lightning/bolts issue #934`](https://github.com/lightning/bolts/issues/934) が適している。ここは広いノード制御 API を先に安定させなくても、conversation と state handling の妥当性を見ることができる。

## Phase 4: Optional remote adapter を足す

boundary が固まったあとで、必要なら remote adapter を追加する。最初の候補は `stdio` か Unix socket sidecar で十分であり、ここで process boundary を跨いでも `init` と `channel_reestablish` が維持できるかを見ればよい。HTTP や gRPC もこの phase の比較対象にはなるが、初手の必須要件ではない。

この phase の成否は transport の豪華さではなく、「remote 化しても fat contract を持ち込んでいないか」で判定すべきだ。control plane が軽く、Lightning message を別 IDL へ複製しておらず、`NodeAdapter` の高水準 operation が stable 必須面に入っていないなら、bridge としては十分成功していると言える。

## Phase 5: Funding / RBF / feature-specific extension を最後に足す

ここまで成立して初めて、`fund_channel`、`init_rbf`、typed-message helper、feature-specific extension をどう扱うかを決める。もし funding や RBF が implementation 間で大きく揺れるなら、それらは `NodeAdapter` の optional extension に留め、core v1 の必須契約には入れないほうがよい。

`BLIP32` のような feature もここに属する。まずは implementation-owned な external test package で試し、共通 adapter seam として切り出せるものだけを upstream に持ち込む。feature を起点に core contract を設計するのではなく、core contract が feature extension を安全に外出しできるかを確認する段階で扱う、という順序である。

## Decision Rule

推奨 path を一文でまとめると、「まず external-runner posture と minimal boundary を固め、そのあとで remote 化と高水準 operation を足す」となる。順番を逆にしてはならない。external runner が先に存在しても boundary cleanup は終わらないし、gRPC を先に入れても contract はよくならない。この二つを別工程として扱うこと自体が、今回の proposal の核である。

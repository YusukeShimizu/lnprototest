# Migration Phases

この文書は、`lnprototest` redesign をどの順番で進め、各 phase でどの問題が解消されるかを固定する。ここでの狙いは、議論が再び「全部つながっている redesign」へ膨らむのを防ぐことにある。各 phase は独立した問いを持ち、前 phase が終わってから次 phase に進む。

## Phase 1: Dependency Split And External-Runner Posture

最初に fix するのは packaging と ownership である。対象は [`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128)、その前史である [`issue #17`](https://github.com/rustyrussell/lnprototest/issues/17)、そして [`PR #131`](https://github.com/rustyrussell/lnprototest/pull/131) / [`PR #133`](https://github.com/rustyrussell/lnprototest/pull/133) / [`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) が示す external runner 実例である。

この phase で解消する問題は、「CLN runner を使わないのに CLN dependency が core install path に乗ってくる」「external runner が例外的 fork work に見える」という二点である。ここでは core package と implementation-owned runner package を conceptually 分離し、external runner を intended extension point として扱う。まだ `Runner` の中身は割らないし、transport も決めない。

完了条件は、設計上「core に残す責務」と「runner package に出せる責務」が区別されていること、そして external runner が project direction として正当化されていることである。

## Phase 2: Boundary Split

次に fix するのは責務境界である。対象は [`issue #98`](https://github.com/rustyrussell/lnprototest/issues/98)、[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95)、Discord 断片の per-connection stash / multiple connection 論点、[`lnprototest/runner.py`](../lnprototest/runner.py)、[`lnprototest/clightning/clightning.py`](../lnprototest/clightning/clightning.py) の現行 surface である。

この phase で解消する問題は、fat `Runner` contract、CLN-shaped capability leakage、runner-wide stash 前提、session owner の不在である。ここで `CapabilitySet`, `NodeAdapter`, `PeerSession`, `ChainBackend`, `LegacyRunnerAdapter` を official boundary として固定する。`PeerSession` の stable API は `open/connect`, `send_raw/send_msg`, `recv_raw/recv_msg`, `disconnect`, session-local stash だけとし、funding や RBF は optional extension に回す。

完了条件は、「何を core v1 に含め、何を後ろに送るか」が追加判断なしで読めることだ。まだ procedural syntax も remote transport も final にはしない。

## Phase 3: Authoring Layer Reframe

ここで初めて authoring 改善に入る。対象は [`rustyrussell/lnprotest`](https://github.com/rustyrussell/lnprotest)、[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95)、[`cdecker/lnpt`](https://github.com/cdecker/lnpt)、[`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の comment である。

この phase で解消する問題は、「Event DSL か procedural API か」という二択で議論が止まることだ。ここでは Event DSL を `LegacyRunnerAdapter` の上位 API として残し、その上で procedural API や decorator / DAG experiment を alternative authoring style として位置づける。境界は phase 2 で確定済みなので、authoring choice は boundary の上で評価できる。

完了条件は、Event DSL を壊さずに procedural authoring を議論できる設計位置が定まっていることだ。typed-message helper や codegen はまだ optional である。

## Phase 4: Proving Scenarios

ここでは boundary が本当に成立するかを小さな conversation で証明する。対象は `init`, disconnect / reconnect, `channel_reestablish` の三つであり、議論ソースとしては [`lnprototest` issue `#49`](https://github.com/rustyrussell/lnprototest/issues/49) と [`lightning/bolts` issue `#934`](https://github.com/lightning/bolts/issues/934) が中心になる。

この phase で解消する問題は、「新 boundary はきれいだが、実際に protocol conversation を書けるのか」という疑いである。`PeerSession` と session-local stash だけで三つの proving target を通せるなら、core v1 boundary は十分小さく、かつ十分強いとみなせる。

完了条件は、三つの proving target が boundary の追加拡張なしで説明できることだ。broad feature matrix や implementation-specific helper はまだ不要である。

## Phase 5: Optional Remote Adapter

最後に remote adapter を足す。対象は [`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の proxy line、[`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2)、そして implementation-owned external runner を別 process に逃がしたい要求である。

この phase で解消する問題は、「boundary は良いが process / runtime がまだ密結合している」という点である。ここで最初に試すのは `stdio`、次に Unix socket sidecar とし、HTTP と gRPC は comparison target に留める。gRPC は multi-host 運用や generated client の要求が明示された後にのみ採用検討する。

完了条件は、remote 化しても fat contract を export していないこと、authoring API が transport に依存していないこと、`init`, disconnect / reconnect, `channel_reestablish` が process boundary 越しでも説明できることである。

## Deferred After Phase 5

Phase 5 まで終えても、まだ後ろに置くべきものがある。

- funding / RBF helper の common contract
- typed-message codegen
- `BLIP32` のような feature-specific extension
- BOLT `MUST` / `SHOULD` policy の全面整理
- dummy runner の最終処遇

これらは boundary が固まり、proving scenario と remote bridge が成立した後に扱う。とくに `BLIP32` は upstream redesign の起点ではなく、implementation-owned external package で先行させる optional feature として扱う。

# 04. Remote Adapter Options と疎結合化

この章で扱う問いは「gRPC を採用すべきか」ではない。正しい問いは、「minimal boundary が固まったあと、どの remote adapter を最初の bridge に選ぶべきか」である。[`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の [2024-11-11 コメント](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818) には HTTP proxy PoC への言及があり、[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) には packaging pain があり、[`vincenzopalazzo/lampo.rs`](https://github.com/vincenzopalazzo/lampo.rs) や [`Psycho-Pirate/ldk-sample`](https://github.com/Psycho-Pirate/ldk-sample) には外部 runner の実例がある。つまり remote 化の動機そのものは確かに存在する。しかし、それだけで gRPC を初手にする理由にはならない。

## 現状

現在の remote 化動機は 3 つに整理できる。ひとつめは dependency split であり、`#128` が示したように、CLN を使わない runner でも `pyln-client` やその周辺依存に引きずられる install path を軽くしたい、という動機である。ふたつめは implementation-owned runner を Python core から疎結合にしたいという動機で、`#131` や Lampo の実例がこの線にある。みっつめは proxy / sidecar に Bolt8 や node-local runtime を閉じ込めたいという動機で、これは `#105` コメントの HTTP proxy PoC に表れている。

ただし、いまの `Runner` 契約は remote 化に向いた形をしていない。`get_keyset`、`get_node_privkey`、`get_node_bitcoinkey`、`has_option`、`fundchannel`、`init_rbf` をまとめて network 越しに export すれば、fat contract と CLN-shaped capability model がそのまま remote API として固定されてしまう。したがって remote adapter の比較は、`CapabilitySet` / `NodeAdapter` / `PeerSession` / `ChainBackend` という boundary を仮定したうえで行う必要がある。

## 理想形

理想形において remote adapter は、control plane と peer session seam を運ぶだけの bridge である。Lightning message 自体は raw wire bytes か既存 message parser を通して扱い、別 IDL に全面複製しない。control plane が落ち着くまで、remote adapter は「core の代替プロトコル定義」ではなく「adapter 実装を別プロセスへ逃がす transport」として振る舞うべきだ。

この条件で眺めると、最初の選択肢は `stdio` か Unix socket sidecar が自然である。`stdio` はローカル subprocess と相性がよく、導入コストが最も低い。Unix socket はローカルマシン前提であれば API 面を少し明確にでき、[`vincenzopalazzo/lnprototest-v2`](https://github.com/vincenzopalazzo/lnprototest-v2) の Unix socket / JSON-RPC 的な PoC とも整合する。どちらにも「control plane がまだ揺れている段階で、運用や認証の複雑さを不必要に増やさずに済む」という利点がある。

HTTP は PoC としては扱いやすいが、session-oriented な長寿命会話よりも request / response に思考が寄りやすい。`channel_reestablish` 自体は扱えるとしても、session handle、disconnect timing、streaming 的な read loop をどう表現するかで余計な設計が増えがちである。gRPC は streaming、IDL、クロスランゲージ tooling に強みを持つが、control plane が未確定な段階で選ぶと「安定させるには早すぎる schema」を作り込みやすい。

## ギャップ

なぜ gRPC を初手にしないのか。理由は protocol complexity ではなく interface stability にある。gRPC 自体が悪いわけではない。問題は、`PeerSession` や `CapabilitySet` の最小面がまだ固定されていない段階で `.proto` を書くと、その時点での誤った責務分割が schema として残ってしまうことだ。とりわけ Lightning message 全体を `.proto oneof` に複製する案は避けるべきである。`lnprototest` はすでに BOLT CSV と `pyln` の message definition を持っており、そこへ別の IDL を重ねれば、仕様の source of truth を二重化するだけに終わる。

さらに、gRPC を初手にすると「transport を整えれば external runner 化が完成する」という誤解を招きやすい。だが実際には、external runner 化と remote 化は別の話である。LDK-Sample の runner script や Lampo の `tests/lnprototest` は、remote adapter を必須とせずとも外部 runner を成立させている。したがって初手に必要なのは汎用 RPC stack ではなく、「core が要求する最小面を小さく保てているか」を検証できる transport である。

## 次の一手

最初の remote adapter option としては `stdio` か Unix socket sidecar を推奨する。どちらも最小 boundary の検証には十分であり、process boundary を導入しつつ control plane を過度に固定せずに済む。ここで最初に通すべきケースは `init`、次に disconnect / reconnect、そして `channel_reestablish` である。これらが通るなら、remote 化しても session-local state と reconnect semantics が保てることを示せる。

そのうえで、multi-host 運用、generated client、長期安定 API、双方向 streaming の必要性が明確になった段階で、gRPC を比較対象として再評価すればよい。その頃には `CapabilitySet`、`PeerSession`、`ChainBackend` のどこを export すべきかが見えているため、gRPC は設計の出発点ではなく実装手段として位置づけられる。

要するに、remote adapter の議論で守るべき順番は一つしかない。boundary を固定し、それを最も軽い transport で検証し、それでも足りない要求が生じたときにだけ transport を強くする。この順番を崩さない限り、gRPC は有効な選択肢になりうる。崩せば、fat contract の remote mirror を作るだけで終わる。

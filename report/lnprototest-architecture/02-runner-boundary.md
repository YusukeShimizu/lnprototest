# 02. Runner Boundary

この章では、`external runner` という packaging 上の姿勢と、`core contract` の縮小という設計上の仕事を切り分けて論じる。結論から言えば、前者だけでは足りない。現行 `Runner` をそのまま外部 package に追い出しても、fat contract が別 repo に移るだけだからである。必要なのは、packaging split、responsibility split、transport split の順序を守った boundary cleanup である。

## 現状

`lnprototest/runner.py` の `Runner` は、session lifecycle、execution engine、stash、peer I/O、chain control、capability / identity、そして高水準の node operation までを、ひとつの abstract base class に抱え込んでいる。`connect`、`recv`、`get_output_message` といった peer conversation の入口に加えて、`getblockheight`、`add_blocks`、`expect_tx`、`fundchannel`、`init_rbf`、`addhtlc`、`get_keyset`、`get_node_privkey`、`get_node_bitcoinkey`、`has_option`、`add_startup_flag` までが同じ契約面に並んでいる。`DummyRunner` ですらこの広いサーフェスを埋めなければならないことは、現行 boundary が test execution の最小要件を超えて膨らんでいることの証左だ。

この混線は、CLN runner を見るとさらに鮮明になる。`lnprototest/clightning/clightning.py` の runner は、`lightningd --list-features-only` から `self.options` を組み立て、`has_option(...)` で `even`、`odd`、`true` といった CLN 由来の文字列表現を返す。同じクラスの中で `Bitcoind` を起動し、wallet compatibility を吸収し、Lightning node の起動 flag まで握っている。capability modeling、peer transport、node process 管理、Bitcoin backend 管理が、最初から一体として実装されているのである。

[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) はこの状態を緩めようとして、runner を stateless 寄りに、connection を stateful 寄りに配置する発想を示した。しかし `RunnerConn` は、session state の置き場所を改善する第一歩ではあっても、`Runner` 契約そのものを最小境界まで削り落としたわけではない。ここを読み違えると、「`RunnerConn` があるのだから boundary cleanup はほぼ終わっている」という誤解が生じる。

この点は、ユーザー提供の Discord 断片にある 2023-07-04 の cdecker の反応とも一致する。そこでは `RunnerConn` ラップが no-op に見えること、runner による connection auto-selection が strange であること、複数 connection を必要とする gossip / forwarding test では柔軟性を落としうることが指摘されている。つまり当時から論点は「connection を返す procedural interface かどうか」だけではなく、「複数 session を first-class に扱える最小境界になっているか」だった。

## 理想形

理想形では、core の最小境界は 4 つに固定される。

`CapabilitySet` は capability modeling を担う。feature bit、extension flag、role、support level を構造化して保持し、`has_option("...")` のような CLN-shaped query を core contract から追い出す。ここで本質的なのは、値の型をきれいに整えることではなく、「何が protocol-level capability で、何が implementation-local toggle か」を core 側で区別できるようにすることである。

`NodeAdapter` は、node process と implementation-local operation を受け持つ。`start`、`stop`、`restart`、`capabilities()` はここに置いてよいが、`fund_channel`、`init_rbf`、`invoice`、`close_channel` を最初から必須にはしない。これらは adapter extension として扱えばよく、minimal v1 boundary の中心に据えるべきものではない。

`PeerSession` は、protocol conversation の最小面である。ここで固定したい API は、`open` あるいは `connect`、`send_raw` または `send_msg`、`recv_raw` または `recv_msg`、`disconnect`、そして session-local stash だけだ。`init`、disconnect / reconnect、`channel_reestablish` を表現できるだけの seam を確保し、それ以上の高水準 node operation は別層へ逃がす。

`ChainBackend` は、Lightning node adapter から分離された Bitcoin 側の面であり、`get_block_height`、`mine_blocks`、`trim_blocks`、`expect_tx` を持つ。`bitcoind` の lifecycle や wallet compatibility の都合を runner に抱え込ませない、というのがこの分離の主眼である。

この理想形では、`Runner` は消してよいし、残すとしても `LegacyRunnerAdapter` のような互換層、あるいは composition root に留まる。Event DSL から見れば、従来の `run()` と event traversal を維持したまま、内部では `CapabilitySet` / `PeerSession` / `ChainBackend` に委譲する薄い層となる。

## ギャップ

現状と理想形のズレは、3 種類に整理できる。

第一に、packaging split の不足である。[`issue #128`](https://github.com/rustyrussell/lnprototest/issues/128) が示した通り、CLN runner を使わなくても `pyln-client` やその周辺依存を抱え込む install path になってしまうのは、core と runner package の ownership が分かれていないことの結果だ。external runner を first-class にするのであれば、まず dependency surface から split しなければならない。

第二に、responsibility split の不足である。現行 `Runner` は、session、chain、node operation、capability を同じ abstract surface に載せているため、外部 runner が実装すべき責務の種類も混ざったままになる。ここが整理されていない状態では、外部化は抽象の改善ではなく、責務の単なる移送にしかならない。

第三に、transport split の順序違反である。gRPC や HTTP や Unix socket の議論は、「どの面を remote に出してよいか」が固まったあとに行うべきだ。現行 `Runner` をそのまま RPC 化してしまえば、`has_option(...)` や `fundchannel(...)` のような CLN bias と高水準 node operation が、そのまま network boundary に固定されてしまう。

## 次の一手

boundary cleanup の実装順ははっきりしている。まず packaging と responsibility の分離を先に行い、そのうえで transport を選ぶ。具体的には、`Runner` 契約を `CapabilitySet`、`NodeAdapter`、`PeerSession`、`ChainBackend` に分解して文書化し、Event DSL から使う最小面を `PeerSession` と `ChainBackend` に寄せる。そのうえで `Runner` は `LegacyRunnerAdapter` として残し、既存 Event DSL を壊さずに新境界へ乗せ替える。

ここで v1 の最小 session API を明示しておく意味は大きい。`open/connect`、`send_raw` または `send_msg`、`recv_raw` または `recv_msg`、`disconnect`、stash だけで `init` と `channel_reestablish` を扱えるなら、その境界は protocol-conversation engine として十分に自立している、と言える。Discord 断片でも Vincenzo は「stash logic make sense to be per-connection and not per-runner」と言い直しており、per-runner stash と connection auto-selection を前提にしたままでは最小境界が曖昧なままだと分かる。逆に、最初から `fundchannel` や `init_rbf` を必須にしたくなるようなら、boundary の取り方がまだ implementation operation に引きずられている、ということだ。

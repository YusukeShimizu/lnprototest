# 03. Test Authoring と DAG

`lnprototest` をめぐる議論では、authoring syntax、execution model、runner boundary がしばしば混線する。この章ではまず順番を入れ替えたい。最初に定めるべきは authoring の好みではなく、どの minimal session API を stable seam とみなすかである。その seam が固まってはじめて、Event DSL を残すのか、procedural API を増やすのか、decorator DAG を試すのか、という議論が意味を持つ。

## 現状

現行の Event DSL は、すでに execution DAG を内包している。`HACKING.md` が test を `Events in a DAG` と呼ぶのは比喩ではなく、`Sequence`、`OneOf`、`AnyOrder`、`TryAll` が実際に分岐と再試行を備えた実行器を構成しているからだ。`tests/test_bolt1-01-init.py` は `Connect`、`ExpectMsg`、`Msg`、`Disconnect` の組み合わせで `init` conversation を表現し、`tests/test_bolt2-02-reestablish.py` は disconnect / reconnect と `channel_reestablish` を含む stateful conversation を Event DSL の上で成立させている。したがって、execution DAG が不足していること自体は redesign の中心問題ではない。

[`PR #95`](https://github.com/rustyrussell/lnprototest/pull/95) が狙っていたのは、execution model の刷新よりも procedural authoring への寄せ方である。`pr-95` ブランチでは `Runner.connect(...)` が `RunnerConn` を返し、その connection から `recv_msg()` と `send_msg()` を呼び出す `test_v2_bolt1-01-init.py` が追加されている。これは「ひとつの peer session の中で何が起きたか」を test author が素直に追えるようにする試みであり、session-local state を runner 本体から切り離す方向とも整合する。

ここで 2023-06 の Discord 議論を重ねると、意図はさらに明確になる。Rusty は [`lnprotest`](https://github.com/rustyrussell/lnprotest) の README を指しながら、「`runner.choose([...])` で minor variants を straight-line な Python の `if` として書けること」「関数分割ベースの composability は elegant だが writing tests is awkward だというのが今の main beef であること」を説明している。Vincenzo はそれを現行 lnprototest に取り込みたいと言い、Rusty は「stash すら不要にできる」「message を普通の Python 変数として持ちたい」「`pyln.proto` も作り直したい」と応じている。つまり procedural line は、単に Event DSL が嫌いという話ではなく、Python の straight-line authoring を中心に据えたいという意図から始まっている。

別線として、[`cdecker/lnpt`](https://github.com/cdecker/lnpt) には decorator DAG experiment が存在する。ただし `lnpt` は `lnprototest` mainline に統合されたものではなく、PR `#95` の一部でもない。したがって Event DSL、procedural API、decorator DAG は「次世代 API の三つの候補」ではなく、「同じ最小境界の上に乗せられるかもしれない authoring choice」として並べて扱うべきである。

## 理想形

理想形において、core が提供する stable seam は minimal session API に限られる。必要なのは `open/connect`、`send_raw` または `send_msg`、`recv_raw` または `recv_msg`、`disconnect`、そして session-local stash だけだ。この seam さえあれば、`init` のような最小 handshake、disconnect / reconnect、`channel_reestablish` のような stateful conversation はいずれも表現できる。逆に、この seam を越えて `fundchannel`、`init_rbf`、typed-message codegen、wallet 操作までを v1 contract に押し込む必要はない。

この理想形は Event DSL の破棄を求めない。むしろ Event DSL は `LegacyRunnerAdapter` や compatibility layer の上位 API として残せる。`ExpectMsg` の partial match や ignore handler、`TryAll` の exhaustive branch traversal には既存資産があり、minimal seam が固まる前に DSL ごと捨てる理由は薄い。procedural authoring は、seam が安定したあとに「読みやすい書き方」として積み増せばよい。

この順序を取ると、decorator DAG の位置づけも自然に定まる。`lnpt` のような書き方は authoring sugar として評価に値するが、minimal session seam が不安定なまま導入すれば、graph syntax の議論が transport / boundary の議論と結合してしまう。Lightning protocol test では message content、stash、auto-reply、再接続 semantics のほうが先に固定されるべきであり、graph syntax はその後ろに来る。

## ギャップ

現状の議論で詰まりやすいのは、authoring friction と boundary problem が同じ言葉で語られてしまう点である。[`issue #105`](https://github.com/rustyrussell/lnprototest/issues/105) の [2024-11-11 コメント](https://github.com/rustyrussell/lnprototest/issues/105#issuecomment-2468755818) では event-based complexity、typed message、proxy PoC が近接して扱われているが、理想設計から見ればこれらは別々のレイヤに属する。authoring friction は「読みやすさ」の問題であり、boundary problem は「何を stable contract として export するか」の問題だ。

さらに Discord の 2023-07-04 の応酬は、その境目をよく示している。cdecker は procedural 化そのものに反対しているのではなく、「複数 connection を必要とする test で reduction in flexibility にならないか」「auto-selecting connection は strange ではないか」を問題にしている。つまり争点は syntax の好みだけでなく、その syntax の下にある session model が正しいかどうかに移っている。

もうひとつのギャップは、implementation-specific feature test の置き場である。たとえば `BLIP32` のような実装依存の話題を upstream redesign の中心に据えると、minimal boundary の議論より先に feature-specific helper や typed abstraction を固めたくなってしまう。しかし理想形では逆で、まず implementation-owned な external test package で feature を育て、複数実装で共通化できる seam だけをあとから upstream に戻すべきである。`BLIP32` は boundary 定義の起点ではなく、外部 package 先行が妥当な optional feature の例として位置づけるのがよい。

## 次の一手

authoring に手を入れる前に、minimal session API を設計文書の中心に据えるべきだ。最低限の検証対象は三つある。`init` で handshake と message の送受信が表現できること。disconnect / reconnect で session lifecycle が表現できること。`channel_reestablish` で stash と session-local state が必要十分であること。この三つが stable seam 上で成立するなら、Event DSL を残したままでも procedural authoring を追加できるし、decorator DAG の検討も落ち着いて進められる。

この順序を守れば、Event DSL は過去の遺物ではなく、境界整理後も使い続けられる上位 API として位置づけ直せる。procedural API はその後の authoring 改善として導入でき、`BLIP32` のような feature test は外部 package で先行して試せる。重要なのは syntax を選ぶことではなく、syntax の下にある minimal session seam を安定させることだ。

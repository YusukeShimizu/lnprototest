# Runner 分割 PoC と追加テストケースの説明

この文書はrunner分割のPoCと追加したテストケースの意味を説明します。
対象のコミットは`69f8464 Add runner boundary proving tests`です。
目的は`runner.connect(...)`を手続き的に呼べるようにすることではありません。
大きな課題は実装間の差分を検出できるテストケースを増やすことです。
そのためには複数peerの接続状態やmempoolの観測を隠蔽すべきではありません。
runner内部へ暗黙に押し込める設計は避けます。
どの責務がどこにあるかを分けておく必要があります。
外部runnerが実装すべきcontractを小さくすることも重要です。

既存の`tests/test_bolt7-10-gossip-filter.py`には複数peerの同時接続例があります。
`connprivkey="05"`と`"06"`のpeerがそれぞれ異なるgossip filter stateを持ちます。
現行のEvent DSLでもこのケースは書けます。
しかし様々な要素が同じrunner surfaceに集まっています。
そのためケースを増やすほど見通しが悪くなります。
集まっている要素はconnection identityやprotocol streamなどです。
node lifecycleやchain observationも含まれます。
今回のPoCはこのようなmulti-session caseを整理する境界を作ります。
これは今後テストを書くための事前の準備です。

## Runner 分割の構成

今回の変更では従来の大きな`Runner` surfaceを小さな境界に分けました。

`CapabilitySet`はprotocol featureやextension supportを正規化して保持します。
既存の`runner.has_option(...)`は`legacy_has_option(...)`経由で維持されます。
古いEvent DSLのテストはそのままcapabilityを参照できます。

`PeerSession`はひとつのpeerとのprotocol conversationを表します。
`connprivkey`や`pubkey`などを持ちます。
`expected_error`や`must_not_events`もconnectionごとに扱います。
raw bytesの送受信は`send_raw`や`recv_raw`や`close`を使います。
これらはrunner実装側に任せます。
その上に`send_msg`と`recv_msg`があります。
これらは`pyln.proto.message.Message`のencodeとdecodeを担当します。
既存Event DSLとの互換のため、受信messageをsession側へ保存する経路も残します。
ただしstashは主論点ではありません。
`send`や`recv`や`disconnect`は薄いaliasです。
これらは手続き的に試すための小さなconvenienceです。

`NodeAdapter`はnode lifecycleとimplementation-specific helperの境界です。
`start`、`stop`、`restart`、`open_session`、`capabilities`を提供します。
`fundchannel`や`init_rbf`などの既存runner helperはここへ寄せています。
`invoice`や`addhtlc`なども`legacy_*` hookとして寄せています。

`ChainBackend`はblock heightやblock miningやmempool expectationを扱います。
既存の`ExpectTx`に対応する`expect_tx`が存在します。
今回新たに`ExpectNoTx`用の`expect_no_tx`を追加しました。
これによりnegative assertionをEvent DSLから書けます。
ある時点でのcommitment transactionがmempoolに出ていないことを確認できます。

`LegacyRunnerAdapter`は既存Event DSLを動かし続ける互換層です。
`connect`や`recv`や`get_output_message`などのAPIを残しています。
`add_blocks`や`expect_tx`や`expect_no_tx`などのAPIも残しています。
内部では`NodeAdapter`や`PeerSession`や`ChainBackend`に処理を委譲します。
`Runner`はこの互換層の名前として残しています。
既存テストのimportやrunner指定を大きく変えずに済みます。

この分割はout-of-tree runnerの前提とも合います。
LDKやLampoのような実装側runnerは、本体へ取り込まなくても成立します。
その場合に必要なのは、太い`Runner`を丸ごと真似ることではありません。
node lifecycle、connection transport、chain observationを別々に実装できるcontractです。

## Event DSL からのコードの流れ

既存Event DSLの`Connect(connprivkey="03")`はrunnerに対する接続要求として実行されます。
互換層では`runner.connect(event, "03")`が呼ばれます。
そこで`NodeAdapter.open_session("03")`を実行します。
返ってきた`PeerSession`は`runner.conns`に登録されます。
これは`connprivkey`ごとに登録されます。
また`last_conn`も更新されます。

nodeへmessageを送るイベントは最終的に`PeerSession`へ到達します。
具体的には`PeerSession.send_raw`または`PeerSession.send_msg`です。
逆にnodeから出てくるmessageを確認するイベントは`ExpectMsg`などです。
これは`runner.get_output_message(conn, event)`から`PeerSession.recv_raw`を呼びます。
`PeerSession.recv_msg`を使う手続き的なテストも存在します。
このテストでは受け取ったraw bytesを`Message`としてdecodeします。
既存DSL互換のため、message nameをkeyにsession側へ保存します。

chainに関わるイベントは`ChainBackend`へ流れます。
`Block`は`mine_blocks`を呼びます。
`ExpectTx`は`expect_tx`を呼びます。
新しい`ExpectNoTx`は`expect_no_tx`を呼びます。
core-lightning runnerでは`CLightningChainBackend.expect_no_tx`が動きます。
これはbitcoindのmempoolをその時点で確認します。
指定txidが存在すれば`EventError`を出します。
dummy runnerではprotocol behaviorを検証しません。
verbose時にexpectationを表示するだけです。

`restart`では互換層が現在の接続を閉じます。
`conns`や`last_conn`やrunner-wide stashを消します。
その後chain backendをrestartします。
さらにnode adapterをstartします。
ここでも様々な処理がひとつのrunner methodの中に混ざりません。
接続のcloseやchainの巻き戻しやnodeのlifecycleはそれぞれの境界へ分かれています。

## 追加テストケース

`tests/test_runner_boundary.py`にテストを追加しました。
対象は`test_legacy_runner_adapter_delegates_boundary_components`です。
`FakeRunner`がboundary componentsに処理を委譲していることを確認します。
接続は`NodeAdapter.open_session`から作られます。
messageの送受信は`PeerSession`に流れます。
block heightや`expect_tx`や`expect_no_tx`は`ChainBackend`に流れます。
このテストは既存Event DSLを壊さずにrunnerの内側を分割できているかを見ます。

同じファイルに別のテストも追加しました。
対象は`test_procedural_connect_and_session_convenience_delegate`です。
`runner.connect(connprivkey="03")`が`PeerSession`を返すことを確認します。
`conn.send(...)`や`conn.recv()`や`conn.disconnect()`の動きも確認します。
これらが既存の`send_msg`や`recv_msg`や`close`に委譲されることを見ます。
これは手続き的な書き方が最低限動くことを見るsmoke testです。

またmulti-session boundary proofのテストも追加しました。
対象は`test_multi_session_boundary_keeps_session_state_isolated`です。
このテストでは`connprivkey="05"`と`"06"`で2つの`PeerSession`を作ります。
それぞれのsend bufferやrecv結果が混線しないことを確認します。
既存DSL互換で使うsession-localな保存領域も混ざらないことを見ます。
片方のsessionをdisconnectしてももう片方のsessionはrunnerに残ります。
closeされないことも確認します。
これは複数peerが同時に別stateを持つケースを整理するための土台です。
BOLT7 gossip filterのようなケースがこれに該当します。

さらに既存Event DSL側が壊れていないことを確認するテストも追加しました。
対象は`test_legacy_connect_signature_still_works`です。
`runner.connect(None, "03")`が正しく動くことを見ます。
新しい`runner.connect(connprivkey="03")`を足しても古い呼び出し規約は維持しています。

`tests/test_procedural_bolt1_01_init.py`にテストを追加しました。
BOLT1 `init`の手続き的なsmoke testです。
`test_procedural_echo_init`はstraight-lineな流れを確認します。
`runner.start()`から`runner.stop()`までの流れです。
途中で`runner.connect(connprivkey="03")`や`conn.recv_msg()`を呼びます。
`conn.send_msg("init", ...)`も呼びます。
`test_procedural_echo_init_reconnect`は再接続の挙動を確認します。
一度`conn.disconnect()`した後で別の`connprivkey`で再接続します。
再び最初に`init`が届くことを確認します。
これはrunner分割の主証明ではありません。
`PeerSession`の上に薄いauthoring styleを載せられることを見る補助的なテストです。

`tests/test_bolt2-02-reestablish.py`にもテストを追加しました。
対象は`test_reestablish_outdated_commitment_number_does_not_publish`です。
これは`ChainBackend.expect_no_tx`の使い道を示すテストです。
既存のchannel setup flowを`reestablish_setup`に切り出します。
そのうえでoutdatedな情報を持つ`channel_reestablish`を送ります。
ここで`next_commitment_number=0`を指定します。
直後に`ExpectNoTx(remote_commitment_txid())`を置きます。
commitment transactionがその時点でmempoolに出ていないことを確認します。
その後の挙動はrunnerによって異なります。
core-lightning runnerではdisconnectを期待します。
dummy runnerではerrorを期待します。

## なぜ runner 分割が効いていると言えるか

今回のPoCが示しているのはconnectionの所有者を小さくできることです。
テスト記述の表面構文ではありません。
複数peerを扱うケースでは各要素がどのpeerに属するかが重要になります。
要素とはsend、recv、disconnect、error expectationなどです。
`PeerSession`を明示したことで接続状態を小さく扱えます。
`connprivkey`ごとの接続状態はrunner-wideな一枚の状態ではありません。
session objectの状態として扱えます。
stashはここでの中心ではありません。
既存Event DSLを壊さないために残している互換上の詳細です。
将来messageを通常のPython変数として扱えるなら、stashは薄くできます。

またchain observationを`ChainBackend`に分けた効果もあります。
protocol conversationとmempool assertionを別々に拡張できます。
`channel_reestablish`のabnormal caseではchain側の観測が必要です。
peerとの会話だけでなくcommitment transactionの未publish状態を確認します。
`ExpectNoTx`はそのための最小の補助です。

後方互換も維持しています。
既存のEvent DSLは`LegacyRunnerAdapter`を通って同じように動きます。
内部だけが新しい境界に委譲されます。
したがって既存テストを一気に書き換えずに済みます。
境界を使う新しいテストから少しずつ増やせます。

## まだ証明していないこと

このPoCでは新しいBOLT7 protocol testは追加していません。
BOLT7 gossip filterはmulti-sessionのreference caseとして使っています。
今回は低リスクに進めるため実プロトコルのBOLT7 case追加は見送りました。
代わりにboundary unit testでsession isolationを固定しました。

`runner.choose`も未実装です。
分岐探索のauthoring layerを足す前にstate ownerを明確にします。
branchごとのstate ownerを明らかにします。
今回の分割はその後により高度なAPIを載せやすくするための下準備です。
そのAPIとは`runner.choose`などを指します。

また今回確認したpytestは対象テストに限定しています。
`python3 -m compileall lnprototest tests`や対象pytestは通っています。
black checkや`git diff --check`も通っています。
しかしreal core-lightning runner validationはまだ実行していません。
full suiteもまだ実行していません。

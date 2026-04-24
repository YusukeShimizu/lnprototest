# Discord 議論メモ: lnprototest runner と authoring ergonomics

この文書は、2023年6月から2024年11月にかけて Discord 上で行われた `lnprototest` の test authoring、runner、connection、message typing に関する議論を整理したものです。目的は、現在の runner 分割 PoC や issue #105 へのフィードバックを書く際に、どの問題意識が過去の議論に由来しているかを追えるようにすることです。

## 議論の中心

この一連の議論では、単にテストの構文を変えたいという話ではなく、`lnprototest` で多くの実装者がテストを書ける状態にするための開発者体験が問題になっています。cdecker は、テスト実行の mental model と tooling を共有し、今度こそ dev ergonomics を良くしたいと述べています。これは、特定の少数の人だけがテストを書ける状態から脱したいという問題意識です。

vincenzopalazzo は、現行の Event based workflow は理解すれば難しくない一方で、Lightning の crypto operation、特に署名や署名済み message を返すための道具が不足していると述べています。LDK integration で詰まっていた点としても、custom channel keys の仮定や signing helper の不足が挙げられています。

RustyRussell は、cdecker の提案を受けて `lnprotest` を提示しました。中心にあるのは `runner.choose([...])` であり、minor variant を普通の Python の分岐として自然に書けることを重視しています。Rusty は、message を普通の Python 変数として持てるなら stash も不要になると述べています。また、`pyln.proto` をより sane な static generated Python へ書き直したいという問題意識も示しています。

cdecker は、PR #95 での `RunnerConn` 導入に対して、単なる `Conn` の wrapper に見える点や、runner から直接送信できる形が gossip tests や forwarding tests のような multiple connection case で柔軟性を下げる可能性を指摘しました。これに対し、vincenzopalazzo は multiple connection 自体は可能だが、send / recv を特定 connection へ dispatch する必要があると説明しました。その後、auto-selected connection の magic behavior は奇妙だという点では合意しています。

この流れから見ると、重要なのは procedural API そのものではありません。`runner.connect` が connection を返し、その connection が send / recv / disconnect の owner になることで、multi-session case の ownership を明示できるかが焦点です。stash は既存 Event DSL との互換に関わる副次的な要素であり、主論点ではありません。これは、現在の `PeerSession` 分割 PoC が狙っている問題と一致します。

## Timeline

### 2023-06-19: dev ergonomics と tooling の問題提起

cdecker は、テスト実行と関連 tooling について考えていることを共有し、誰も使わないものに時間を使いすぎる前に mental model を議論したいと述べました。ここでの主眼は、開発者体験を改善し、少数の人だけがテストを書く状態を避けることです。

vincenzopalazzo は、lnprototest の Event based workflow は、node が custom channel keys を使うという前提を理解すれば難しくないと説明しました。一方で、Lightning crypto operation を行うための道具が足りないとも述べています。署名して message を返す処理が不足しており、LDK integration の障害にもなっていました。

この時点で、vincenzopalazzo は次のような API 方向も示しています。

```rust
let msg = AnnouncementSignatures::default()
    .channel_id(channel_id())
    .short_channel_id(short_channel_id)
    .on_signature(|raw_msg| lightning_crypto::sign(raw_msg))
    .on_bitcoin_signature(|raw_msg| lightning_crypto::btc_signature(raw_msg));
let msg = runner.send(connection, msg);
assert!(msg.is_msg("announcement_signatures"), "Expected `announcement_signatures` message but received the `{:?}`", msg);
```

ここでは、state machine を runner の中に持つよりも、core lightning integration testing のように test 側に state を持たせる方向が示されています。runner と connection を作る点が、pyln-testing の node graph とは異なると説明されています。

### 2023-06-20: runner_features と lnprotest / runner.choose

Psycho-Pirate は PR #94 で `runner_features` を追加しました。これは、implementation が必要とする feature を lnprototest 側へ提供するための変更です。

RustyRussell は `lnprotest` を提示しました。中心となる考え方は `runner.choose([...])` です。test は何度も実行され、choice がすべて探索されます。choice は、呼ぶ関数の候補、true / false、複数 flag など、テスト中の小さな variant を表現するために使われます。

Rusty は、function boundary をまたいで test logic を分割すると書きにくくなることを lnprototest への不満として挙げています。`lnprotest` の README のような straight-line style は、自然で明確な test style を実現するための提案です。

vincenzopalazzo は、この方向なら runner 内の state machine をなくし、stash 情報だけにできる可能性があると述べました。Rusty は、message を変数として持てるなら stash も不要だと返しています。普通の Python として message を読み書きし、variant があれば通常の `if` で書くという方向です。

### 2023-06-21 to 2023-06-22: signing helper と pyln.proto の再設計

Rusty は、signing などを library に offload できると良いと述べました。Python で正確に実装する例があるのは有用ですが、taproot などまで自分で実装するつもりはないとも述べています。

choice については、例が単純でも minor variant を自然に書けることが重要だと説明しています。variant を書きやすくしないと thorough tests を書く動機が弱くなる、という問題意識です。

また Rusty は `pyln.proto` の再設計にも触れています。重要なのは、返される class が期待される field を自然な Python type で持つこと、wire type との変換を一貫して扱うこと、wire bytes から適切な message object を返す factory があることです。

vincenzopalazzo は Python の方が素早く iterate できるとしつつ、まだ混乱している点があるため、lnprototest をさらに書いて refactor することで明確になることを期待していました。

### 2023-07-04: PR #95 と RunnerConn / multiple connection 議論

vincenzopalazzo は PR #95 を提示しました。これは、現在の lnprototest に Rusty の提案を取り込めるかを見るための WIP refactoring です。

cdecker は、`Conn` を `RunnerConn` で wrap しても no-op に見えることを指摘しました。また、runner から直接 send できる形は一見便利でも、gossip tests や forwarding tests のように multiple connection が必要なケースでは柔軟性が落ちるのではないかと述べています。

vincenzopalazzo は、multiple connection ができないわけではなく、`runner.connect` が connection list に追加しているため可能だと説明しました。ただし、`send_msg` と `recv_msg` を特定 connection へ dispatch する必要があり、そのために private key を parameter として渡す案を示しています。

PR #95 の狙いは、現行実装が runner 内 state machine を減らせるかを確認することでした。vincenzopalazzo は、現行 tests は state machine ではなく stash function で state を保持していると説明しています。retro-compatible なので LDK integration を壊さず進められる点も強調しています。

cdecker は、auto-selected connection の magic behavior が奇妙だと述べました。vincenzopalazzo もその点を認めています。そのうえで、Rusty の proposal の方が multiple connection の面では明確だと述べています。`runner.connect` が connection を返すため、手続き的に connection を選択できるからです。

また、connection が runner へアクセスする必要があるため stash workflow が少し複雑になるとも述べています。一方で、runner が connection を返すなら stash は runner 単位ではなく connection 単位の方が自然だという見方も示されています。

この部分が、今回の `PeerSession` 分割 PoC に最も直接関係します。`PeerSession` は、connection ごとの protocol stream と lifecycle を持つ明示的な owner です。stash は既存 Event DSL を動かすために残る互換上の詳細です。`LegacyRunnerAdapter` は既存 Event DSL の `connprivkey` を `PeerSession` に map します。これにより、auto-select される runner-wide state ではなく、connection ごとの state を扱う方向へ進めます。

### 2023-07-13 to 2023-07-15: implementation capability と BOLT7 bugs

Psycho-Pirate は issue #98 で、`has_option` が C-Lightning 固有の表示形式に依存している問題を挙げました。これは、複数実装に対応する runner contract を考えるうえで重要な論点です。

続いて PR #99 では tests が `runner_features` を使うように更新されました。これは、複数の Lightning 実装を同時に support しやすくするための変更です。

vincenzopalazzo は PR #100 で、core lightning patch に対する integration testing を追加しました。BOLT7 の `announcement_signatures` message における signature verification の問題を扱うものです。さらに PR #101 では BOLT7 内の error check bug を修正しています。

この時期の議論は、runner / authoring ergonomics だけでなく、実際に protocol bug を検出するテストを増やす必要性を示しています。したがって、runner 分割の価値も「新しい syntax」ではなく「テストケースを増やせる構造」に置くべきです。

### 2023-08-25: event chaining with lnprototest v2

vincenzopalazzo は、PR #95 で実験した内容を少し時間を置いて再考し、`event chaining with lnprototest v2` というスレッドを開始しました。ここでは、current implementation 上で authoring style や runner refactoring をどう進めるかが継続して議論されています。

### 2023-09: CLN changes and lnprototest maintenance

Rusty は ElementsProject/lightning PR #6628 によって lnprototest が壊れた可能性を報告しました。channel が locked in された後に reorg される挙動が変わり、bitcoind reset と lightningd shutdown の順序が疑われています。

その後、CLN invocation への `--developer` 追加や、ElementsProject/lightning PR #6697 による test rework が共有されました。vincenzopalazzo は lnprototest fixes を取り込む CLN 側 PR #6702 を出しています。PR #109 や PR #111 も bug fixing / release の流れとして共有されています。

この時期のやり取りは、runner contract や backend lifecycle の曖昧さが、実装側の変更に追従する際にも問題になることを示しています。`NodeAdapter` と `ChainBackend` を分ける動機にもつながります。

### 2024-11-19: current CLN への rebase と issue #123

vincenzopalazzo は、current core lightning へ lnprototest を rebase する中で issue #123 を共有しました。同じ tests が 24.05 では通り、24.08 では問題が出るため、Python util bug か 24.08 で入った bug かを切り分ける必要があるとしています。PR #127 も共有されています。

これは、lnprototest が実装の変化に継続して追従する必要があることを示しています。runner や backend の責務が明確であれば、どこが protocol behavior で、どこが harness / adapter の問題かを切り分けやすくなります。

## 現在の PoC への対応

今回の runner 分割 PoC は、この Discord 議論のうち次の点を具体化しています。

まず、`runner.connect` が session を返す形を許し、connection ごとの操作を `PeerSession` に寄せています。これは、Rusty の straight-line style と、cdecker が懸念した multiple connection case の両方に関係します。connection-local stash という話も出ていましたが、ここでは stash を中心に置きません。中心は、send / recv / disconnect / error expectation がどの connection に属するかを明示することです。

次に、`LegacyRunnerAdapter` を残しています。これにより、PR #95 で重視されていた retro-compatible な移行を維持します。既存 Event DSL は壊さず、内部だけを `NodeAdapter`、`PeerSession`、`ChainBackend` へ委譲します。

また、multi-session case を runner 分割の主証明に置いています。cdecker が指摘した gossip tests / forwarding tests の懸念に対応するには、単なる procedural syntax では足りません。connection ごとの state owner を明確にする必要があります。今回の `test_multi_session_boundary_keeps_session_state_isolated` は、その最小 proof です。

最後に、`runner.choose` はまだ実装していません。Discord 議論では `runner.choose` が自然な variant 表現として重要でした。しかし、branch ごとの state owner が曖昧なままでは、runner-wide state machine を別の形で再導入する危険があります。現在の PoC では、まず session / node / chain boundary を明確にし、その上に choose 方式を載せる順序を採っています。

## out-of-tree runner 化との関係

Discord 議論とは別に、LDK / Lampo 方面では runner を本体外に置く流れが強くなっています。`ldk-lnprototest` のような外部 package が出てくるなら、`lnprototest` 本体が各実装の runner を抱え込む必要はありません。むしろ本体側が持つべきなのは、外部 runner が実装しやすい小さな contract です。

この文脈では、今回の分割はより直接的に効きます。外部 runner author が太い `Runner` interface を丸ごと再現する必要があると、node lifecycle、BOLT8 transport、message I/O、block generation、mempool observation が一つの class に混ざります。`NodeAdapter`、`PeerSession`、`ChainBackend` に分けると、実装側は自分が担当する境界を順に埋められます。

LDK や Lampo のような runner では、node 起動や capability は `NodeAdapter` に置けます。connection transport や BOLT8 handshake は `PeerSession` に寄せられます。block / mempool の観測は `ChainBackend` に分離できます。将来的に BOLT8 部分を sidecar や Unix socket runner へ切り出す場合も、この分割の方が自然です。

ただし、これは LDK 本家の CI に `lnprototest` が正式採用されたという主張ではありません。現時点で安全に言えるのは、外部 runner package や Lampo 経由の統合が進み、out-of-tree runner を前提にした core boundary が必要になっている、という点です。

## Related Links Mentioned

- https://github.com/rustyrussell/lnprototest/pull/94
- https://github.com/rustyrussell/lnprotest
- https://github.com/rustyrussell/lnprototest/pull/95
- https://github.com/rustyrussell/lnprototest/issues/98
- https://github.com/rustyrussell/lnprototest/pull/99
- https://github.com/rustyrussell/lnprototest/pull/100
- https://github.com/ElementsProject/lightning/pull/6384
- https://github.com/rustyrussell/lnprototest/pull/101
- https://github.com/ElementsProject/lightning/pull/6628
- https://github.com/ElementsProject/lightning/pull/6697
- https://github.com/ElementsProject/lightning/pull/6702
- https://github.com/rustyrussell/lnprototest/pull/109
- https://github.com/rustyrussell/lnprototest/pull/111
- https://github.com/rustyrussell/lnprototest/issues/123
- https://github.com/rustyrussell/lnprototest/pull/127

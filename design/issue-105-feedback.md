# Issue #105 Feedback Draft

The main reason I think the runner split is worth pursuing is not procedural syntax by itself. The larger blocker for moving `lnprototest` forward is adding more useful test cases, and the current runner shape makes some of those cases harder to reason about than they need to be.

The concrete example I would use is multi-session testing. `tests/test_bolt7-10-gossip-filter.py` already shows why this matters: two peers can be connected at the same time, with different gossip filters and different expectations about future gossip. The current Event DSL can express this, but the ownership is implicit: connection identity, session-local stash, node lifecycle, and chain observation all sit behind the same runner surface.

The PoC split tries to make those responsibilities explicit:

- `PeerSession` owns one protocol conversation, including send / receive / close and session-local stash.
- `NodeAdapter` owns node lifecycle, capabilities, and implementation-specific helpers.
- `ChainBackend` owns block and mempool observation, including negative assertions such as `ExpectNoTx`.
- `LegacyRunnerAdapter` keeps the existing Event DSL working while delegating to those smaller boundaries.

That gives a low-risk migration path. Existing tests can continue to run through the Event DSL, while new tests can start proving the smaller boundaries. In this branch, BOLT1 `init` is only a smoke test for straight-line authoring. The more important proof is that multi-session state can be represented as separate `PeerSession` objects, and that BOLT2 `channel_reestablish` abnormal cases can use a chain boundary for "this commitment tx must not appear yet" checks.

I also think this ordering makes `runner.choose` easier to introduce later. `choose` needs a clear state owner for each branch; otherwise it risks becoming another runner-wide state machine. Splitting runner/session/chain first gives us a smaller surface to build branch exploration on.

For external implementations, the same split should make `lnprototest` easier to consume from outside the repository. A runner no longer has to reimplement one fat interface all at once. It can first provide lifecycle, session, and chain adapters. Later, the BOLT8 transport part could be extracted further, possibly sharing an LND-based or sidecar-based transport/proxy layer across implementations, but I would treat that as a follow-up after the session boundary is stable.

So my proposed direction is:

1. keep the Event DSL compatible,
2. land the boundary split with small proving tests,
3. use existing BOLT7 multi-session tests as the reference shape for the next real protocol test cleanup,
4. then add `runner.choose` or another branch-authoring layer on top of the clearer session model.

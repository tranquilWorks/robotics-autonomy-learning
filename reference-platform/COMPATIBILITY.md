# Reference-platform compatibility record

Compatibility family: `robotics-autonomy-learning.reference-platform`

Producer contract: `1.0.0`

Canonicalization: `ral-json-c14n-v1`

Implementation start revision: `ae5764598da09f8c8b9d3629b8f64369c9c7025e`

Declared RP01 product baseline: `f8807640258f1a6c1c77f1dcc9e61734551c585b`

Control revision: `35a09aca04b4f64cc97249ddd3e81e6f46faba6b`

The producer is this target repository. An approved post-review target commit is intentionally not named because RP01 does not commit or release. Future consumers must pin that approved revision before adoption.

## Exchanged fixtures

The compatibility set is the five files under `fixtures/valid/` and their configuration digests in `fixtures/canonical-hashes.json`. A consumer validates the full bundle, the eight schema identities, all cross-document links, and the golden digest before claiming compatibility.

## Upgrade policy

- Version `1.0.0` is exact and strict. Unknown contract or fixture versions are rejected.
- Additive or breaking fields require a new explicit version and side-by-side fixtures. Strict v1 documents do not silently accept unknown fields.
- A producer change names every participating repository, exact producer and consumer revisions, schema versions, exchanged fixtures, retained validation level, human approval, and rollback.
- A green producer test is not evidence that either consumer adopted the change.

## Rollback policy

Keep the last approved v1 schema/index/fixture set pinned until all consumers explicitly migrate. If a later revision fails, restore the prior pinned set and its hashes, retain the rejected revision and reason, and do not rewrite curriculum history. RP01 itself rolls back by reverting only its allowed target-local additions and root documentation links.

Current consumer status is `not_started`: `controls-gnc-learning` was not modified, and Tranquility was not contacted.

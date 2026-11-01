# Delivery worker contract

A provider's event id is unique within one tenant. It is not globally unique.
A tenant's exact repeat must charge once. Two tenants with the same event id each owe their own
usage. The worker is serial. A future multi-worker rollout is outside this review.
Review the receipt identity through schema, storage, handler and ledger. The current smoke test
is evidence for one tenant only. This is a review before integration; do not fix the source.

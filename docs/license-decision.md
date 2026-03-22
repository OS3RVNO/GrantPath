# License Decision

## Recommendation

Use `Apache-2.0` for public publication.

## Why

GrantPath is intended to be adopted by technical teams and potentially by commercial or enterprise users. Compared with `MIT`, `Apache-2.0` adds a clearer patent grant while staying permissive.

That makes it a better fit when:

- the project may evolve into a commercially relevant platform
- external contributors may add novel implementation details
- enterprise users want slightly stronger legal clarity than a bare MIT grant

## MIT vs Apache-2.0

### MIT

Pros:

- extremely simple
- widely understood
- very low friction

Cons:

- no explicit patent grant
- slightly weaker legal story for enterprise consumers

### Apache-2.0

Pros:

- explicit patent grant
- still permissive
- familiar to enterprise legal teams

Cons:

- slightly longer and more formal
- marginally more overhead than MIT

## Decision

For GrantPath, `Apache-2.0` is the better public-facing default.

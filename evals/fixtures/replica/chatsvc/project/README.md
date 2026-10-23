# chatsvc

A chat service in front of a hosted model provider. Callers send chat and embedding requests with
their API key; chatsvc applies its own limits, picks the provider model for the route they call,
and passes the request on with one of our pooled provider keys. It also keeps the feedback people
leave on answers.

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md) and [limits](docs/limits.md)
- [The provider's API](docs/provider.md)
- [Feedback](docs/feedback.md)
- [Operations: stage and prod](docs/operations.md)
- [Releases](docs/releases.md)
- Specs: [provider routing](docs/specs/provider-routing.md), [feedback store](docs/specs/feedback-store.md)

Run it locally with `python3 -m chatsvc` (it calls the real provider, so it needs network and a
provider key); tests and the environments use the offline provider in `fakeprovider/`.

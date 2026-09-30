# ADR-0006: Use REST with OpenAPI for the API

- Status: Accepted
- Date: 2026-09-30
- Task: HK-1
- Deciders: midhun
- Area: api style
- Reversibility: cheap: one client consumes the API, so the contract can be replaced while both sides are rebuilt together

## Context

- One React single-page app (ADR-0003) calls one FastAPI service (ADR-0002).
- FastAPI produces an OpenAPI document from the code.
- No third-party or mobile clients exist.
- Screens such as the comparison view need several resources, but one team owns both sides.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| REST with OpenAPI (chosen) | some screens need two or three calls | one client, one team, a generated typed client |
| GraphQL | a schema and resolvers to own, plus N+1 care, for one client | many clients needing different shapes of the same graph |
| tRPC | needs TypeScript on both ends; the backend is Python | a single TypeScript codebase end to end |
| gRPC | poor fit for a browser client and no service-to-service traffic | internal service-to-service calls |

## Decision

We will expose a REST API described by the OpenAPI document FastAPI generates, and generate the React client's types from it, because one client and one team do not justify a GraphQL layer.

## Consequences

- The OpenAPI file is the contract; contract tests belong in CI (`openapi-spec` skill).
- Versioning follows the `api-versioning` skill when a breaking change is first needed.
- Revisit if a second client with a different data shape appears.

## Commits us to

OpenAPI 3.1 (FastAPI generated), a generated TypeScript client (tool to be chosen in low-level design)

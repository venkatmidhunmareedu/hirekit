# ADR-0005: Use own session authentication with two roles

- Status: Accepted
- Date: 2026-09-30
- Task: HK-1
- Deciders: midhun
- Area: auth
- Reversibility: awkward: switching to an identity provider means migrating users, sessions and the login flow, though role checks stay in one dependency

## Context

- Two roles only: recruiter and interviewer (PRD section 3). The service must refuse forbidden actions itself, not only hide them in the UI (US-00-012).
- Raw resumes are personal data and recruiter-only (REQ-049).
- Q-002 assumes seeded logins for the first version, and the demo must run offline from recordings.
- No client asks for SSO.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Own implementation (chosen) | we own password hashing, session expiry and CSRF | two roles, seeded users, offline demo |
| Keycloak | a heavy extra service to run and secure for two seeded roles | enterprise SSO, MFA, user self-service |
| Auth0 or Okta | an external account and network dependency; the demo must run offline | a hosted deployment with real users |
| Supabase or Firebase Auth | ties identity to a vendor stack not otherwise used | an app already on that vendor |

## Decision

We will implement server-side sessions in a secure cookie with hashed passwords and one role-check dependency on every route, because two seeded roles need no identity provider and the demo must run offline.

## Consequences

- We own password hashing, session expiry and CSRF protection; a permission matrix is written as tests (`auth` skill).
- Seeded users are created by the seed command, never by a default password in code.
- Revisit when a client asks for SSO or a hosted deployment holds real candidate data.

## Commits us to

Python (FastAPI) session middleware, argon2 password hashing (library to be confirmed in low-level design)

# Security

This is an early-stage project (see `README.md` — Status). There is no deployed
instance behind this repository yet, so there is currently no live attack
surface to report against. This file exists so the expectation is set before
one does.

## Reporting a vulnerability

Please do not open a public GitHub issue for a security concern. Instead,
contact Open Source Films directly at **security@opensourcefilms.org** (or
open a private security advisory on this repository, if enabled).

Include enough detail to reproduce the issue. If the report concerns a real
deployment rather than this codebase, do not include any real case data,
photographs, email addresses or other personal information in the report
itself — describe the behaviour, not the evidence.

## Scope notes for when a deployment exists

Once a real instance is running, the following will apply and should be kept
current here:

- how to report a suspected data exposure (e.g. a stolen-bike case or a
  reverse-check submission becoming visible to someone other than its owner);
- how credential compromise for this service (email account, marketplace API
  keys, RunPod access) should be reported and handled;
- expected response time.

Nothing in this repository should be interpreted as a claim that a deployment
is currently monitored for security reports — check `README.md` for current
status first.

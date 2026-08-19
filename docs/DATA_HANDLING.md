# Data handling

This document describes the data-handling boundaries this project is designed
around, ahead of any real deployment collecting real data. See `README.md` —
Status for what is actually implemented today: as of this writing, no case
data, listing archive or database exists anywhere, in this repo or otherwise.
This file records the intended boundary now, while it is cheap to get right,
rather than after real submissions exist.

## What a deployment would collect

Per `docs/HANDOVER.md`, an operational instance would hold:

- stolen-bike case submissions: owner email address, photographs, free-text
  description;
- buyer/shop reverse-check submissions: submitter email address, photographs;
- an archive of marketplace listings collected for matching purposes
  (metadata, images, and where legally permitted a source snapshot);
- match results and owner feedback (YES / NO / UNSURE replies).

This is personal data, and for stolen-bike cases specifically it sits close to
criminal-offence data (allegations/suspicion of theft) under UK data
protection law. See `docs/HANDOVER.md` §11 for the fuller discussion; this
file is the short operational summary, not a substitute for that review.

## What must never be committed to this repository

- real owner or seller email addresses, names, phone numbers;
- real submission photographs or marketplace listing images;
- raw `.eml` files or email archive contents;
- production database files, FAISS indexes, or the content-addressed archive;
- browser session state, cookies, or authentication profiles;
- API keys or credentials of any kind (`.env`, `config.toml` — see
  `.gitignore`, which already excludes both).

Fixtures and tests must use synthetic or explicitly-cleared-for-publication
data only.

## Separation of concerns

The design (`docs/HANDOVER.md`) keeps application code independent of
operational data: the canonical archive, database and model caches all live
outside version control, on the RunPod Network Volume in production
(`/workspace/bikematch/{archive,models,browser_profiles}`, all gitignored) or
in a developer's local, also-gitignored equivalent. Code changes and data
changes are never the same commit by construction.

## Retention and deletion

Not yet implemented. This is a real gap, not an oversight: retention periods,
a deletion workflow for a withdrawn case, and export/removal on request all
need to exist before any real submission is accepted, and should be documented
here (and in `README.md`) once they are built — not asserted in advance of the
code that would make them true.

## Operator responsibilities

Whoever runs a real instance of this project is a data controller under UK
GDPR for the personal data it processes, independent of what this repository
does or doesn't implement. This repository is the tooling; it is not a
compliance program. See `docs/HANDOVER.md` §11 for what that operator needs to
have reviewed (lawful basis, criminal-offence-data conditions, DPIA necessity)
before accepting real submissions.

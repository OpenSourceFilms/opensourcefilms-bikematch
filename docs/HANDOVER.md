# Claude Code implementation handover: Edinburgh stolen-bike visual matching system

## 0. Objective

Build an operational private service on RunPod which helps owners of stolen bicycles in Greater Edinburgh discover marketplace advertisements that may show their bicycle.

The service is deliberately simple from the user's perspective:

**Stolen-bike workflow**

```text
owner emails bike photos
→ system archives email/photos
→ system searches all historic collected advertisements
→ future marketplace advertisements are continually checked
→ likely matches are emailed to that owner
→ owner can reply YES / NO / UNSURE
```

**Buyer/shop workflow**

```text
shop or prospective buyer emails photos of a bike
→ system compares them against submitted stolen-bike cases
→ system replies with no significant match / possible match / strong match
→ relevant original owner can also be alerted
```

There is no public website, no public searchable database and no enforcement component.

Initial marketplace scope:

* eBay UK
* Gumtree UK
* Facebook Marketplace

Initial geographic scope:

* Greater Edinburgh
* Configurable initial radius: approximately 25 miles from central Edinburgh

Do not build functionality for recovering property, confronting sellers, messaging sellers or determining ownership. This project ends at private matching, archiving and notification.

---

# 1. Architecture decisions that are already made

Do not reopen these unless implementation evidence shows an actual blocker.

## 1.1 One main application

Use Python.

Use a single application repository with:

* email polling
* scheduler
* durable jobs
* marketplace collectors
* image processing
* retrieval
* matching
* notification
* administration CLI

Do **not** introduce:

* Celery
* Redis
* RabbitMQ
* Kafka
* Airflow
* Temporal
* Kubernetes
* PostgreSQL
* Qdrant
* Milvus

for the MVP.

They are unnecessary at Edinburgh pilot scale.

## 1.2 RunPod storage split

A RunPod Network Volume mounted at `/workspace` is the canonical persistent store.

RunPod explicitly states that Network Volumes persist independently of compute, mount at `/workspace`, and that simultaneous writes from multiple workers can corrupt data.

Therefore:

```text
/workspace/bikematch/       CANONICAL/PERSISTENT
    archive/
    snapshots/
    models/
    browser_profiles/
    benchmark/
    exports/
    backups/
```

The active SQLite database and active FAISS indexes must **not** be treated as canonical data.

Use fast container-local storage for working copies:

```text
/var/lib/bikematch/
    state.sqlite3
    faiss/
    temp/
```

Container-local state can disappear when the Pod is replaced/reset, so everything required to reconstruct it must exist under `/workspace`. RunPod also recommends separately backing up important Network Volume data.

### Required recovery model

On startup:

```text
1. Inspect /workspace/bikematch/snapshots/
2. Restore latest valid SQLite snapshot if present.
3. Restore matching FAISS snapshot if compatible.
4. Replay canonical manifests/events created after snapshot.
5. Verify DB counts against archive.
6. Verify FAISS vector IDs against DB.
7. Rebuild either cache completely if validation fails.
8. Start scheduler only after state validation passes.
```

Never require re-running GPU inference merely because the working DB/index was lost. Persist expensive derived features to the Network Volume.

## 1.3 Single canonical writer

Only one application process may mutate canonical archive state.

Async collection and inference are fine, but final archive commits go through a single writer abstraction.

Do not have several Pods/processes independently write the same archive.

---

# 2. Runtime/toolchain

## Base container

Start with:

```text
pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime
```

PyTorch 2.13.0 is the current stable release from 8 July 2026, and the official container registry publishes the CUDA 12.6/cuDNN 9 runtime image.

Use:

```text
torch == 2.13.0
torchvision == 0.28.0
```

torchvision 0.28.0 is the matching current release.

Do not use the DR document's `torch==2.6.0` / `torchvision==0.17.0` pair.

## Python

Target:

```text
Python >=3.12,<3.14
```

Prefer the interpreter already supported cleanly by the selected PyTorch image.

Do not spend engineering effort upgrading Python merely to obtain the newest language release.

Python 3.13 is current and well supported, but compatibility of the full ML stack matters more than language recency. Python 3.13.14 is available as of June 2026.

## Dependency management

Use:

```text
uv
pyproject.toml
uv.lock
```

The lockfile is authoritative.

Do not manually freeze dozens of versions copied from the DR report. Resolve the environment once on the actual RunPod runtime, run the complete import/smoke-test suite, then commit `uv.lock`.

Explicitly constrain the packages where current compatibility matters:

```text
torch==2.13.0
torchvision==0.28.0
transformers==5.14.1
faiss-cpu==1.14.3
playwright==1.61.0
APScheduler==3.11.3
IMAPClient==3.1.0
SQLAlchemy==2.0.51
```

These versions were current stable releases at handover time.

PaddleOCR, if later enabled, should use the current 3.x line; PaddleOCR 3.7.0 is current as of June 2026, not the 2.5 release in the research document.

---

# 3. Repository structure

Create approximately:

```text
bikematch/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── README.md
├── config.example.toml
├── src/
│   └── bikematch/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── logging.py
│       ├── ids.py
│       │
│       ├── archive/
│       │   ├── blobs.py
│       │   ├── manifests.py
│       │   ├── events.py
│       │   ├── snapshots.py
│       │   └── integrity.py
│       │
│       ├── db/
│       │   ├── engine.py
│       │   ├── models.py
│       │   ├── repository.py
│       │   ├── migrations/
│       │   └── rebuild.py
│       │
│       ├── jobs/
│       │   ├── scheduler.py
│       │   ├── queue.py
│       │   ├── worker.py
│       │   └── handlers.py
│       │
│       ├── email/
│       │   ├── imap.py
│       │   ├── parsing.py
│       │   ├── routing.py
│       │   ├── replies.py
│       │   ├── smtp.py
│       │   ├── ses.py
│       │   └── templates/
│       │
│       ├── collectors/
│       │   ├── base.py
│       │   ├── ebay.py
│       │   ├── gumtree.py
│       │   └── facebook.py
│       │
│       ├── images/
│       │   ├── normalise.py
│       │   ├── hashes.py
│       │   ├── detection.py
│       │   └── variants.py
│       │
│       ├── features/
│       │   ├── base.py
│       │   ├── dinov3.py
│       │   ├── dinov2.py
│       │   ├── siglip2.py
│       │   ├── local.py
│       │   └── ocr.py
│       │
│       ├── retrieval/
│       │   ├── faiss_index.py
│       │   ├── aggregate.py
│       │   └── rebuild.py
│       │
│       ├── matching/
│       │   ├── signals.py
│       │   ├── rerank.py
│       │   └── feedback.py
│       │
│       └── benchmark/
│           ├── dataset.py
│           ├── run.py
│           ├── metrics.py
│           └── report.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── fixtures/
    └── retrieval/
```

Keep marketplace-specific code completely outside the matching engine.

---

# 4. Canonical filesystem archive

The filesystem is the durable source of truth.

Use:

```text
/workspace/bikematch/archive/
├── blobs/
│   └── sha256/
│       └── ab/
│           └── cd/
│               └── abcdef...<extension>
│
├── email/
│   └── <email-id>/
│       ├── original.eml.ref.json
│       └── manifest.json
│
├── cases/
│   └── <case-id>/
│       ├── manifest.json
│       ├── events/
│       ├── submitted/
│       ├── features/
│       └── notifications/
│
├── listings/
│   └── <source>/
│       └── <listing-id>/
│           ├── manifest.json
│           ├── snapshots/
│           ├── images/
│           └── features/
│
└── checks/
    └── <check-id>/
```

## Blob store

Every immutable raw object is addressed by SHA-256:

* `.eml`
* original uploaded image
* marketplace image
* raw HTTP body
* API response
* HTML
* screenshot
* derived crop if worth retaining

Never overwrite a blob.

Write:

```text
temp file
→ fsync where practical
→ hash
→ atomic rename into blob location
```

If the destination hash already exists, discard the duplicate temporary file.

## Manifests

Manifests are human-readable JSON.

Every manifest includes:

```json
{
  "schema_version": 1,
  "created_at": "...",
  "updated_at": "...",
  "id": "...",
  "archive_revision": 1
}
```

Do not mutate a manifest in place.

Write a replacement to a temporary path and rename atomically.

Important historical states should additionally exist as immutable timestamped snapshots.

---

# 5. IDs and idempotency

Use sortable IDs, preferably UUIDv7 internally.

Human case IDs can be short aliases such as:

```text
EDB-2026-8F3K2Q
```

Database uniqueness requirements:

```text
email Message-ID                       UNIQUE when present
(mailbox, IMAP UIDVALIDITY, UID)       UNIQUE
(source, listing_id)                   UNIQUE
blob sha256                            UNIQUE
(feature_type, entity, model_version)  UNIQUE
(case_id, listing_id)                  UNIQUE match relationship
```

Every job must have an idempotency key.

Examples:

```text
parse_email:<blobsha>
process_image:<blobsha>:<pipeline-version>
fetch_listing:ebay:<listing-id>
embed:<image-id>:dinov3-vitb16:<feature-version>
match_case:<case-id>:<index-generation>
```

Repeating a completed job must be harmless.

---

# 6. Working database

Use local SQLite through SQLAlchemy 2.0.

Use Alembic migrations.

Recommended SQLite settings on the **local** filesystem:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

Do not put active WAL files on `/workspace`.

Tables should cover:

```text
cases
case_emails
checks
emails
images
image_variants
listings
listing_snapshots
listing_images
features
jobs
collector_runs
matches
match_signals
notifications
feedback
model_versions
archive_objects
```

The database is an indexed operational projection of the canonical archive.

Implement:

```text
bikematch rebuild-db
```

before building marketplace collectors.

That command must be capable of reconstructing the core database from `/workspace/bikematch/archive`.

---

# 7. Durable jobs

Use APScheduler 3.11.3 only for recurring triggers.

The jobs table is responsible for durability.

A job needs approximately:

```text
id
type
idempotency_key
payload_json
status
priority
attempts
max_attempts
available_at
leased_until
started_at
completed_at
last_error
created_at
```

Statuses:

```text
pending
leased
running
completed
failed
cancelled
```

Claim jobs transactionally.

If the process dies with a job leased/running, it becomes available after lease expiry.

Use exponential backoff with jitter for network failures.

Do not retry permanently invalid input indefinitely.

### Concurrency

Initial limits:

```text
archive writer            1
Facebook collector        1
Gumtree requests           low bounded concurrency
eBay requests              low bounded concurrency
GPU model inference        1 batch at a time initially
LightGlue pair matching    bounded GPU queue
email sending              small bounded concurrency
```

Optimise later from measurements.

---

# 8. Email ingress

Use:

```text
IMAPClient 3.1.0
Python stdlib email package
```

IMAPClient 3.1.0 is current and production-stable.

Support two configured destination addresses or aliases:

```text
stolen@...
check@...
```

They may resolve to the same physical mailbox.

Poll approximately every 60 seconds.

Do not make IMAP IDLE a dependency for the MVP.

## On receiving an email

First action:

```text
fetch RFC822 bytes
→ archive the exact raw .eml
```

Only then parse it.

Preserve:

```text
Message-ID
In-Reply-To
References
From
To/Cc
Subject
Date
IMAP UID
UIDVALIDITY
```

Walk MIME parts and accept useful image attachments/inline images.

Support at least:

```text
JPEG
PNG
WebP
HEIC/HEIF
```

Ignore decorative tiny email-signature images using dimensions/file size heuristics, but retain their original bytes in the `.eml`.

## Case creation

A valid stolen-bike report requires only:

```text
sender email
+ at least one usable bicycle photograph
```

No serial number, receipt, make/model or prose is required.

Reply with:

```text
case ID
number of accepted photographs
short explanation that historical and future advertisements will be checked
```

Additional replies containing images attach to the existing case.

Resolve threads using:

1. `In-Reply-To` / `References`
2. case ID in subject
3. sender address only as final fallback

---

# 9. Outgoing email

Implement a transport protocol:

```python
class MailSender(Protocol):
    async def send(message: OutgoingMessage) -> SendResult: ...
```

Implement SMTP first because it makes development trivial.

Also implement Amazon SES v2 as the production transport if SES credentials are supplied.

SES supports inline attachments/CID images and messages up to 40 MB. Use much smaller messages operationally.

Match emails should usually remain below approximately 5–10 MB.

Use Python `EmailMessage` plus Jinja2.

Each match digest contains:

```text
case ID
submitted-bike thumbnail
candidate number
advertisement thumbnail(s)
source
price
location
first seen
listing date if known
live URL
overall rank
short signal summary
```

No claim that the bike is stolen.

Reply syntax:

```text
YES 2
NO 1 3 5
UNSURE 4
```

Also accept reasonably obvious variants.

NO suppresses that `(case, listing)` pair permanently unless an administrator resets it.

---

# 10. Image normalisation

Always preserve original bytes.

Create deterministic processing variants.

For each usable image:

```text
original
display-normalised image
thumbnail
optional bicycle crop(s)
optional mirrored crop(s)
```

Correct EXIF orientation before inference.

Convert inference variants to sRGB RGB.

Use Pillow plus pillow-heif initially.

Introduce pyvips only if profiling demonstrates meaningful benefit. Do not make libvips a blocker for the first working pipeline.

Generate email thumbnails around 320–480 px on the long side.

Retain substantially higher resolution for local-feature matching.

## Hashing

Compute:

```text
SHA-256
pHash
dimensions
MIME type
```

Important distinction:

* An exact/near duplicate **between a stolen-bike photo and an advertisement photo is a very strong positive signal**.
* An exact/near duplicate **between several marketplace listings** is a deduplication/grouping signal.

Do not apply the earlier research suggestion of penalising exact query/candidate photographs.

---

# 11. Detection

Do not use Ultralytics YOLO as the required default.

Ultralytics' current licensing states that its trained models and software are AGPL-3.0 unless an Enterprise licence is obtained; private deployment without releasing the whole project is one of the cases for which Ultralytics says an Enterprise licence is required.

Use the permissively licensed RT-DETR baseline instead:

```text
PekingU/rtdetr_r50vd_coco_o365
```

The official Hugging Face model is Apache-2.0 and directly supported through Transformers.

Detection is not allowed to become a recall bottleneck.

For every photograph:

```text
embed full image
AND
if one or more bicycle detections exist:
    produce generous crop around every bike
    expand bounding box about 15–20%
    embed those crops too
```

If detector confidence is poor, retain the full-image path.

The benchmark must test whether detected crops actually improve retrieval.

---

# 12. Global visual retrieval benchmark

Do **not** choose the production embedding model before benchmarking.

The three mandatory initial candidates are:

### DINOv3 Base

```text
facebook/dinov3-vitb16-pretrain-lvd1689m
```

Official Meta checkpoint, approximately 86M parameters, gated on Hugging Face. DINOv3 uses Meta's custom DINOv3 licence.

### DINOv2 with Registers Base

```text
facebook/dinov2-with-registers-base
```

Official Meta model, 86.6M parameters, Apache-2.0.

### SigLIP 2 Base

```text
google/siglip2-base-patch16-384
```

Official Google model, Apache-2.0.

Do not use the invented or unrelated model identifiers in the research report's final manifest.

## Embedding variants

For DINO models test:

```text
CLS
mean patch tokens
CLS + mean-patch representation if practical
```

For each source photograph compare:

```text
whole image
detected bicycle crop
horizontal mirror of crop
```

Do not assume mirroring helps. Measure it.

Use official `AutoImageProcessor` preprocessing first.

Do not arbitrarily force every model to 224×224 merely to standardise them.

Persist:

```text
model ID
model revision
processor configuration
input variant
vector dimensionality
normalisation method
feature-pipeline version
```

Use L2-normalised vectors.

---

# 13. Benchmark dataset

This stage comes **before production model lock-in**.

The prior research correctly identified Recall@K as the essential operational metric.

Claude Code should make it possible to build the first benchmark without requiring 30 cooperative bike owners.

## Phase A: marketplace identity benchmark

Collect approximately:

```text
200 multi-photo bicycle listings
3+ substantially different photos per listing
2,000+ photos from unrelated bike listings
```

A multi-image listing supplies weak but useful ground truth:

```text
photos in one listing = same physical bicycle
```

For every listing:

* hold one image as query
* place its other images among the gallery
* add thousands of distractors

Hard negatives should preferentially include:

* same make
* same model words
* same colour
* visually similar bike type

Do not allow the identical photograph into both query and gallery.

## Phase B: hard hand-labelled set

Create a smaller manually validated set containing:

* same-model/different-bike pairs
* different viewpoints
* changed accessories
* low-quality screenshots
* opposite sides
* occlusion
* indoor/outdoor changes

## Phase C: eventual real owner/ad pairs

As the pilot receives confirmed YES matches, preserve them as the highest-quality evaluation set.

Never train on the evaluation-only subset.

## Metrics

Produce:

```text
Recall@1
Recall@5
Recall@10
Recall@20
MRR
median true-match rank
90th-percentile true-match rank
average irrelevant candidates before true match
same-model hard-negative error rate
embedding latency
local-rerank latency
storage per image
```

Primary criterion:

> How often does the correct physical bike appear within the first 20 candidates?

Secondary criterion:

> How many candidates does an owner need to inspect?

Do not optimise benchmark performance solely around Recall@1.

---

# 14. Model-selection rule

Do not hardcode DINOv3 simply because it is newer.

After benchmark execution, create:

```text
/workspace/bikematch/benchmark/selected_pipeline.json
```

It should identify the selected model and processing configuration.

A reasonable decision rule is:

1. Highest Recall@20 is primary.
2. Recall@10 breaks close ties.
3. Fewer same-model hard-negative errors breaks the next tie.
4. If results are statistically near-equivalent, prefer:

   * permissive licence
   * smaller model
   * lower inference/storage cost

Therefore DINOv2-with-registers should win over DINOv3 if performance is effectively equivalent, because its Apache-2.0 licensing is considerably simpler. DINOv2 explicitly supports nearest-neighbour image retrieval.

Do not make a legal interpretation of the DINOv3 licence in code. Record it as `custom-dinov3-license` and require an explicit project-level decision before DINOv3 becomes the production default.

---

# 15. FAISS retrieval

Use:

```text
faiss-cpu==1.14.3
IndexFlatIP
```

FAISS 1.14.3 is the current release and supplies current CPython wheels.

Because vectors are L2-normalised:

```text
inner product = cosine similarity
```

Start with exact search.

Do not introduce IVF, HNSW or quantisation until measurements show exact retrieval is a bottleneck.

Expected Edinburgh-scale corpus is well within the useful range for exact search initially.

Maintain two logical indexes:

```text
advertisement vectors
stolen-case vectors
```

One entity may generate several vectors:

```text
listing
 ├ image 1 full
 ├ image 1 crop
 ├ image 1 mirrored crop
 ├ image 2 full
 └ ...
```

FAISS IDs map through SQLite to:

```text
entity_type
entity_id
image_id
variant
feature_version
```

## Deletion

Do not physically delete vectors immediately.

Maintain tombstones/filter state in SQLite and periodically rebuild the index.

## Index generation

Every complete index gets:

```text
generation UUID
model ID
feature pipeline version
vector count
SHA-256
creation time
```

Do not load a snapshot generated by a different embedding configuration.

---

# 16. Candidate aggregation

Retrieval happens at image/vector level.

Results shown to users happen at **listing level**.

For each query photograph:

```text
retrieve top N vectors
map them to listings
```

Combine results from every query photograph and variant.

Initial listing aggregation should remain simple and transparent.

Record:

```text
best global similarity
second-best independent photo similarity
number of independently matching source photographs
number of independently matching listing photographs
```

A listing with several independently strong photo pairs should outrank a listing supported by only one weak pair.

Do not average every photograph indiscriminately because irrelevant listing photos would suppress good evidence.

Keep all raw pair scores.

---

# 17. ALIKED + LightGlue reranking

Use the official:

```text
cvg/LightGlue
ALIKED extractor
```

Pin an exact Git commit in the lock/environment after the first tested installation.

Do not depend on an invented PyPI version.

LightGlue officially supports ALIKED. Prefer ALIKED over SuperPoint because of the cleaner licensing path.

Run local verification only against the strongest global candidates.

Initial:

```text
top 20–30 listings
```

For each listing, select the most promising image pairs from global retrieval rather than comparing every possible pair.

Use:

```text
ALIKED
→ LightGlue correspondences
→ OpenCV USAC/MAGSAC geometric verification
```

Try a fundamental matrix as the primary geometry model for substantial viewpoint variation.

Homography may be used as an additional model where appropriate.

Record:

```text
raw correspondence count
geometrically verified inlier count
inlier ratio
median match confidence
coverage over bicycle crop
```

Local matching is a **positive bonus**, not a mandatory gate.

Opposite sides of the same bike, substantial occlusion and component swaps may produce few local matches.

A low local-feature score must therefore not automatically eliminate an otherwise strong global candidate.

---

# 18. Segmentation

Do not enable segmentation in the initial production pipeline.

If tested, use SAM 2.1.

Contrary to the DR report's licence table, official SAM 2 checkpoints and code are Apache-2.0.

Benchmark:

```text
loose detector crop
versus
SAM foreground mask
```

Measure Recall@10/20 and false candidates.

Only retain SAM as a dependency if there is a meaningful measured improvement.

Thin bike structures such as spokes and tubes make segmentation an empirical question rather than an automatic improvement.

---

# 19. OCR

OCR is phase-two auxiliary evidence.

If implemented, use:

```text
PaddleOCR 3.7.x
```

not 2.5.x.

Run only after the visual baseline works.

Use OCR to extract things such as:

```text
TREK
SPECIALIZED
ROCKHOPPER
GIANT
Shimano
model decals
```

OCR agreement can add evidence.

OCR disagreement must not strongly penalise an image because:

* lettering may be invisible from another side
* OCR may be wrong
* decals may have been removed
* marketplace resolution may be poor

Do not make serial-number OCR part of the required workflow.

---

# 20. No VLM in MVP scoring

Do not initially install Qwen3-VL or another large VLM for matching.

The earlier research proposed VLM reranking, but there is no project-specific evidence yet that it improves ranking beyond DINO + LightGlue. The initial system should measure that first.

A VLM can later be experimentally evaluated on the top five candidates for:

* human-readable observations
* describing apparent component differences
* identifying visible distinctive marks

It must not output a pseudo-probability that is treated as calibrated confidence.

---

# 21. Initial match scoring

Do not implement arbitrary fixed research weights such as 35/30/25/10.

Store separate signals.

Initial rank can be based largely on:

```text
global listing similarity
+ independent-view support
+ positive local-feature evidence
```

Optional later bonuses:

```text
OCR agreement
colour similarity
near-duplicate photograph
```

No strong hard-negative penalties except incontrovertible incompatibilities learned through validation.

The operational output is a ranking rather than a declaration.

Thresholds are chosen only after observing the benchmark and pilot candidate distributions.

---

# 22. eBay collector

Use the official eBay Browse API.

Browse API supports:

* keyword/category search
* image-based search
* item summaries
* detailed item retrieval
* item location

Do not scrape eBay in the MVP unless an important field is demonstrably unavailable through the API.

Implement:

```python
EbayCollector.discover()
EbayCollector.fetch()
EbayCollector.refresh()
```

Authentication:

```text
OAuth client credentials
X-EBAY-C-MARKETPLACE-ID: EBAY_GB
```

### Discovery

Use category/keyword discovery sorted toward newly listed items.

Do not use the seller-arranged local-pickup radius filter as the sole Edinburgh filter because that excludes bikes whose sellers offer postage.

Instead:

```text
discover GB bike listings
→ inspect returned itemLocation
→ retain those satisfying configured Greater Edinburgh rules
```

Use the current taxonomy API/current Browse responses rather than burying an eternal bicycle category number in code.

Category IDs belong in configuration/cache and can be refreshed.

### Image search

For every new stolen-bike case, eBay `searchByImage` is a useful second independent candidate source.

Archive image-search candidates even if they were not found by scheduled category discovery, subject to the Edinburgh filter.

### Archive

Persist:

```text
raw API response
item ID
URL
title
description if available
price
currency
item location
seller public ID if returned
start/origin time where returned
first-seen time
last-seen time
all accessible image URLs and downloaded originals
```

---

# 23. Gumtree collector

Implement a progressive fallback architecture.

## Level 1

Use:

```text
HTTPX
HTML parser
```

Prefer Selectolax or lxml after a simple implementation comparison.

Fetch current Edinburgh bicycle search/results directly.

Attempt extraction from, in order:

```text
JSON-LD / structured data
embedded application JSON
ordinary HTML attributes/text
```

## Level 2

If a listing/search field cannot reliably be obtained through HTTP, use Playwright for that path.

Do not automatically make all Gumtree collection browser-based.

The DR session found current Gumtree pages sufficiently server-rendered for direct parsing, but treat selectors as data that may change rather than immutable assumptions.

### Parser fixtures

Every live collector run should be capable of saving representative raw pages.

Tests should load these fixtures offline.

If required fields fall below extraction thresholds after a site change, fail the collector visibly instead of silently archiving empty/bad records.

Required extraction-health fields:

```text
listing ID
URL
at least one image
price or explicit missing-price state
location
title
```

---

# 24. Facebook Marketplace collector

Use:

```text
Playwright Python 1.61.0
bundled Chromium
persistent browser context
```

Playwright 1.61 currently ships Chromium 149.0.7827.55.

Do not use Camoufox, Patchright, CAPTCHA solvers or stealth plugins in the default implementation.

### Persistent profile

Use:

```python
browser_type.launch_persistent_context(
    user_data_dir="/workspace/bikematch/browser_profiles/facebook",
    ...
)
```

Only one Facebook collector process can use this profile.

Initial authentication is human.

Provide:

```text
bikematch facebook-login
```

which launches a headed browser through an available RunPod graphical path/noVNC if necessary.

After login, subsequent collection uses the persistent context.

### Collection

Use Marketplace's bicycle category and configured Edinburgh location/radius.

Discover listing IDs/URLs from the rendered results.

For each unseen listing:

```text
open listing
extract public listing fields
download all available listing images
archive HTML/available structured response
take diagnostic screenshot if needed
```

Prefer stable structured state/network data where readily available, but do not couple the entire collector to undocumented GraphQL internals if DOM extraction is adequate.

### Challenges

Explicitly detect:

```text
login page
checkpoint
challenge
temporary block
unexpected empty result
session expiration
```

On any of those:

```text
STOP Facebook collection
preserve trace/screenshot
send admin alert
wait for human action
```

Do not attempt automated challenge bypass.

Use low frequency and one browser session.

---

# 25. Common collector protocol

Implement:

```python
class MarketplaceCollector(Protocol):
    source: Marketplace

    async def discover(
        self,
        cursor: DiscoveryCursor | None
    ) -> DiscoveryResult:
        ...

    async def fetch(
        self,
        ref: ListingReference
    ) -> RawListing:
        ...

    async def refresh(
        self,
        listing_id: str
    ) -> RawListing:
        ...
```

`RawListing` should preserve source-specific fields before normalisation.

`Listing` normalised schema:

```text
source
listing_id
canonical_url
title
description
price_amount
price_currency
advertised_location_text
advertised_lat/lon if actually available
seller_public_id
source_posted_at
first_seen_at
last_seen_at
availability
image_urls[]
raw_snapshot_refs[]
collector_version
extraction_warnings[]
```

Do not invent unknown values.

---

# 26. Greater Edinburgh filtering

Centralise geography configuration.

Example:

```toml
[search_area]
name = "Greater Edinburgh"
centre_lat = 55.9533
centre_lon = -3.1883
radius_miles = 25
```

Each source may implement it differently:

```text
Facebook: native Marketplace location/radius
Gumtree: native search location/radius where available
eBay: returned item-location post-filter plus source filtering
```

Do not discard a visually strong candidate merely because its textual suburb formatting is unusual once it was collected inside the configured search.

Do not crawl the whole UK in the MVP.

---

# 27. Listing archive behaviour

Every collected listing is archived **before visual matching**.

The historical archive is essential.

On a new case:

```text
case → all archived advertisements
```

On a new advertisement:

```text
advertisement → all active stolen cases
```

This symmetric behaviour is mandatory.

Never delete an advertisement merely because:

* it sold
* it disappeared
* it initially scored poorly
* there was no stolen case at collection time

Its later historical value is the point of the system.

Refresh active listings only as often as useful for detecting edits/removal.

Store new snapshots instead of replacing historical state.

---

# 28. Shop/buyer reverse checks

A message delivered to the configured `check` address creates a Check, not a StolenCase.

Process its photos through the same image pipeline.

Query:

```text
stolen-case FAISS index
```

not advertisement index.

Response states:

```text
NO_SIGNIFICANT_MATCH
POSSIBLE_MATCH
STRONG_VISUAL_MATCH
```

“No significant match” must explicitly mean only:

> No significant visual match was found among stolen bikes submitted to this service.

It must not imply ownership verification.

When a reverse check passes the owner-alert threshold, notify the original owner as well.

Do not automatically disclose the owner's email address to the checker.

---

# 29. Feedback loop

Parse replies against previous notification IDs/case threads.

Support:

```text
YES
NO
UNSURE
```

Store feedback as immutable events.

Effects:

**NO**

* suppress this listing for this case
* preserve its signals as a labelled hard negative

**YES**

* flag as confirmed-by-owner visual match
* preserve pair in evaluation dataset

**UNSURE**

* no suppression
* retain as ambiguous data

Do not automatically retrain models from feedback.

Accumulate real data first.

---

# 30. Notification policy

Favour recall but avoid flooding the owner.

Implement two channels of the same email system:

### Immediate

Only genuinely high-ranking newly discovered candidates.

### Digest

Lower-confidence candidates accumulated over a period.

Initial configurable caps:

```text
immediate candidates: 3–5
daily digest: up to 15–20 unseen listings
```

These are product limits, not ML thresholds.

Never send the same case/listing pair repeatedly unless:

* the listing changed materially, or
* administrator explicitly resets suppression

---

# 31. Snapshots and backups

Every few minutes or after a meaningful batch of completed work:

```text
SQLite online backup
→ hash
→ copy atomically to /workspace/bikematch/snapshots/
```

FAISS:

```text
write index locally
→ hash
→ copy snapshot plus generation manifest
```

Keep several generations.

Do not continuously write an active SQLite WAL over the Network Volume.

Periodically back up the critical `/workspace/bikematch` data to independent storage because RunPod explicitly recommends external backup for important data.

---

# 32. Logging

Use structured JSON logging.

Every relevant event should carry whichever identifiers apply:

```text
job_id
case_id
check_id
listing_id
source
email_id
image_id
collector_run_id
feature_version
index_generation
```

Never swallow exceptions in collectors.

Collector health needs metrics such as:

```text
run started
run finished
listings discovered
new listings
listing fetch successes/failures
images downloaded
parse failures
challenge detected
duration
```

Use Healthchecks.io or equivalent simple heartbeat monitoring.

No Grafana stack required initially.

---

# 33. Admin CLI

Implement Typer commands along these lines:

```text
bikematch doctor

bikematch mail poll
bikematch mail send-test

bikematch collector run ebay
bikematch collector run gumtree
bikematch collector run facebook
bikematch collector inspect <source> <id>

bikematch facebook login

bikematch case show <case>
bikematch case reprocess <case>

bikematch listing refresh <source> <id>

bikematch benchmark build
bikematch benchmark run
bikematch benchmark report

bikematch index rebuild
bikematch index verify

bikematch db rebuild
bikematch db verify

bikematch archive verify

bikematch jobs list-failed
bikematch jobs retry <id>

bikematch snapshot create
bikematch snapshot verify
```

`bikematch doctor` should check:

```text
GPU
CUDA
PyTorch
Network Volume
free disk space
SQLite working directory
model access/cache
IMAP
outbound email
eBay API
Playwright browser
Facebook profile state
FAISS import
archive write test
```

---

# 34. Testing

Use:

```text
pytest
pytest-asyncio
Ruff
Pyright or mypy
```

Tests must not require live marketplaces except explicitly marked live/contract tests.

Create recorded fixtures for:

```text
email MIME messages
eBay JSON
Gumtree pages
Facebook extracted listing representations
corrupt images
HEIC image
multi-bike image
missing listing
listing edit
```

## Mandatory recovery test

Create archive state, then delete:

```text
state.sqlite3
all FAISS files
```

Run reconstruction.

The rebuilt application must return the same cases/listings/features and equivalent retrieval results.

This is a release-blocking test.

---

# 35. Implementation order

Follow this order rather than implementing everything simultaneously.

## Phase 1: repository/runtime

Deliver:

```text
Dockerfile
uv project
package skeleton
configuration
logging
CLI
tests
```

Acceptance:

```text
GPU visible
torch works
Playwright launches
FAISS imports
pytest passes
```

## Phase 2: canonical archive

Implement:

```text
blob store
atomic manifests
events
integrity verifier
```

Acceptance:

* duplicate input does not duplicate blob
* simulated crash cannot leave a manifest half-written
* archive verify catches corruption

## Phase 3: local database/jobs

Implement:

```text
SQLite
SQLAlchemy
Alembic
jobs
archive → DB rebuild
```

Acceptance:

* delete database
* reconstruct successfully

## Phase 4: email intake

Implement:

```text
IMAP polling
raw .eml archive
image extraction
case/check routing
reply threading
```

Acceptance:

* image-only stolen report creates valid case
* same email fetched twice creates one case
* HEIC/JPEG attachments work
* follow-up photo attaches to correct case

## Phase 5: basic image processing

Implement:

```text
orientation
normalisation
hashes
thumbnail
full-image feature input
RT-DETR optional crop
```

Do not add SAM/OCR yet.

## Phase 6: retrieval benchmark

Implement DINOv3, DINOv2-register and SigLIP2 adapters.

Build the marketplace multi-image benchmark.

Produce a machine-readable and HTML/Markdown benchmark report.

**Do not choose the production embedding model before this phase finishes.**

## Phase 7: production feature pipeline

Freeze selected pipeline in:

```text
selected_pipeline.json
```

Implement durable feature persistence and FAISS.

Acceptance:

* known positive image is retrieved
* DB/index can be destroyed and recreated without inference

## Phase 8: LightGlue

Add ALIKED + LightGlue as measured reranker.

Rerun benchmark with and without it.

Keep it only if useful.

## Phase 9: match emails and feedback

Implement digest rendering, outbound transport and replies.

Test email visually on desktop and phone.

## Phase 10: eBay

Official API first.

Begin building a real Edinburgh archive.

## Phase 11: Gumtree

HTTP collector first, Playwright fallback.

## Phase 12: Facebook

Persistent Playwright profile and manual-login path.

Do this after the rest of the system works so Facebook fragility cannot block development.

## Phase 13: reverse check

Add buyer/shop route using same matching engine.

## Phase 14: optional signals

Only after looking at actual errors, evaluate:

```text
SAM 2.1
PaddleOCR
colour features
coarse component regions
VLM reranking
```

Do not implement them merely because previous research listed them.

---

# 36. Initial configuration

Create a TOML configuration roughly along these lines:

```toml
[paths]
persistent_root = "/workspace/bikematch"
working_root = "/var/lib/bikematch"

[email]
poll_seconds = 60
stolen_addresses = ["stolen@example.org"]
check_addresses = ["check@example.org"]
sender_address = "bikematch@example.org"

[search_area]
name = "Greater Edinburgh"
centre_lat = 55.9533
centre_lon = -3.1883
radius_miles = 25

[collectors.ebay]
enabled = true

[collectors.gumtree]
enabled = true

[collectors.facebook]
enabled = true

[matching]
retrieval_candidates_per_query = 100
rerank_listings = 30
immediate_email_max = 5
digest_email_max = 20

[features]
segmentation_enabled = false
ocr_enabled = false
vlm_enabled = false
```

Do not put credentials in this file.

---

# 37. Required secrets/environment

Support:

```text
IMAP_HOST
IMAP_PORT
IMAP_USERNAME
IMAP_PASSWORD

SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD

AWS_REGION
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
SES_FROM_ADDRESS

EBAY_CLIENT_ID
EBAY_CLIENT_SECRET

HF_TOKEN
```

SMTP and SES need not both be configured.

Do not store Facebook password in environment if manual persistent-profile authentication is being used.

---

# 38. Model cache

Persist downloaded models under:

```text
/workspace/bikematch/models/
```

Set relevant Hugging Face cache environment variables accordingly.

Pin:

```text
repository
revision
file hashes where practical
licence identifier
```

in a model registry.

The application must not silently switch model revisions after a restart.

---

# 39. Licensing corrections

Do not copy the research report's licence table.

Correct starting facts:

**DINOv2**

* code and weights Apache-2.0.

**DINOv3**

* code and weights under Meta's custom DINOv3 licence, not Apache; treat the licence as a project-level review item.

**SigLIP 2**

* selected official Google checkpoint is Apache-2.0.

**SAM 2**

* official model checkpoints and code are Apache-2.0.

**Ultralytics YOLO**

* AGPL-3.0 by default; proprietary/private use requires attention to Ultralytics' Enterprise terms. Avoid it as the default detector here.

**RT-DETR**

* selected PekingU checkpoint is Apache-2.0.

Do not label a licence from memory. Add a `THIRD_PARTY_NOTICES.md` assembled from actual upstream licence files.

---

# 40. Things explicitly not to build yet

Do not implement:

```text
public website
public search
user accounts
mobile app
facial recognition
seller reputation database
seller accusation scoring
serial-number dependency
proof-of-ownership verification
police integration
automated seller messaging
nationwide collection
fine-tuning
custom bicycle-component detector
distributed queue
multi-Pod database
Qdrant
PostgreSQL
SAM in mandatory path
VLM in mandatory path
```

The MVP succeeds if it reliably:

```text
receives photos by email
archives Edinburgh ads
finds visually plausible same-bike listings
shows a manageable candidate set
learns NO suppression from owner feedback
supports reverse checking
survives process/Pod replacement without losing its archive
```

---

# 41. Definition of done for first live pilot

Before enabling regular Facebook/Gumtree collection, demonstrate all of the following:

1. A photograph-only email creates a case and archives the original `.eml`.
2. Several historical advertisement images can be indexed.
3. A known same-bike photograph appears in retrieval results.
4. The benchmark compares DINOv3, DINOv2-register and SigLIP2.
5. The selected pipeline is recorded explicitly rather than hardcoded from assumption.
6. ALIKED/LightGlue has been measured rather than assumed useful.
7. A new advertisement is automatically checked against existing cases.
8. A new case automatically searches historical advertisements.
9. Candidate email renders correctly.
10. `NO 2` suppresses candidate 2 from future notifications.
11. A reverse `check@` email queries stolen cases successfully.
12. Removing the local DB and FAISS index and running rebuild restores operational state.
13. A broken marketplace parser generates an administrator-visible failure.
14. An expired Facebook session pauses Facebook collection without affecting eBay, Gumtree, email or matching.
15. All tests pass from the locked environment.

---

# 42. First instruction to Claude Code

Begin with repository/runtime, archive primitives and the reconstruction test.

Do **not** start by writing the Facebook scraper.

Before installing optional ML packages, create and test the core environment based on PyTorch 2.13.0/CUDA 12.6 and capture the resulting `uv.lock`.

Once the archive and working-state reconstruction are proven, implement email input and the benchmark harness.

The first meaningful technical milestone is not “three marketplaces are scraping”.

It is:

> Given different photographs of the same physical bicycle mixed among large numbers of other bicycle photographs, determine which current feature pipeline ranks the correct bike most consistently within the first 20 results, and persist enough information that this result can be reproduced exactly.

Everything else should be built around that measured result.

# Ingest Log

## [2026-04-08] bootstrap | wiki_test
- Created test knowledge base skeleton.
- Imported 4 uploaded original files into `raw/`.
- Imported 1 external reference markdown into `raw/`.
- Created initial index and seed topic pages for testing.

## [2026-04-08] ingest | 新一代视频会议系统建设方案模板
- Imported source 06 into `raw/`.
- Created source summary page for the solution template.
- Updated index to reflect the expanded source set and current topic pages.

## [2026-04-13] ingest | sources 07-17
- Imported 11 additional source documents into `raw/`.
- Generated section cards and document indexes for iteration, architecture, stability, security, and product-line materials.
- Added new topic pages for private cloud iteration and technology route comparison.
- Added source summary page for the newly imported batch.

## [2026-04-18] retrieval | version cleanup and workflow docs
- Unified the repository version label to `v2.5`.
- Added `docs/query-workflow.md` to document the actual query flow, required tools, and command-level examples.
- Added `docs/release-note-schema.md` to define recommended fields for release-note documents.
- Reworked `README.md` and `qmd_bridge/README.md` so they describe current scripts and usage order instead of only abstract principles.
- Kept the split between `solution` and `release_note` retrieval paths, with `release_note` using coarse-grained recall.

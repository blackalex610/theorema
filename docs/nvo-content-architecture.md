# NVO Content Architecture Plan

## Purpose

Move from file-based NVO reference materials to a scalable, queryable content system that supports:

1. fast retrieval,
2. controlled generation quality,
3. curriculum-aware filtering,
4. long-term growth in volume and complexity.

This plan keeps current behavior working while introducing a robust content platform incrementally.

## Why this change is needed

Current approach (large files and in-memory parsing) works for small datasets, but becomes weak as materials grow.

Main issues with file-first retrieval:

1. higher latency as files increase,
2. weak filtering precision by skill/topic/difficulty,
3. difficult deduplication and provenance tracking,
4. harder quality control and content governance,
5. no clear scaling path for personalized generation.

## Target end-state

Use a hybrid retrieval architecture:

1. PostgreSQL as source of truth for structured content and metadata,
2. pgvector (or separate vector store later) for semantic ranking,
3. deterministic filter-then-rank pipeline for generation context assembly,
4. ingestion and normalization pipeline for all new materials,
5. auditability from generated output back to source records.

## High-level architecture

### Content storage layer

1. relational schema for canonical problem records and taxonomy,
2. source documents and provenance metadata,
3. versioned updates instead of destructive overwrites.

### Retrieval layer

1. metadata filtering first (grade/module/topic/type/difficulty),
2. semantic ranking second (embedding similarity),
3. diversity and anti-duplication pass,
4. prompt context builder from top candidates.

### Generation layer

1. generation prompt references only selected candidates,
2. strict output contracts per NVO structure,
3. post-generation validation and scoring,
4. fallback behavior if candidate set is insufficient.

### Evaluation layer

1. item quality scoring,
2. retrieval quality metrics,
3. generation success/failure analytics,
4. feedback loop for future curation.

## Proposed data model (v1)

### tables: source_exams

1. id,
2. title,
3. year,
4. variant,
5. region,
6. source_type (official, synthetic, curated),
7. language,
8. raw_text,
9. metadata_json,
10. created_at,
11. updated_at.

### tables: topics

1. id,
2. grade,
3. name,
4. parent_topic_id (nullable),
5. taxonomy_version,
6. created_at.

### tables: skills

1. id,
2. code,
3. name,
4. description,
5. taxonomy_version.

### tables: problems

1. id,
2. source_exam_id,
3. external_ref (for example exam/number),
4. grade,
5. module,
6. problem_number,
7. statement,
8. answer_format (mcq, open, multipart_open),
9. options_json,
10. canonical_answer_json,
11. explanation,
12. difficulty,
13. topic_id,
14. subtype,
15. has_diagram,
16. diagram_type,
17. diagram_config_json,
18. quality_score,
19. is_active,
20. content_version,
21. created_at,
22. updated_at.

### tables: problem_skills (many-to-many)

1. problem_id,
2. skill_id,
3. weight.

### tables: problem_embeddings

1. problem_id,
2. embedding_vector,
3. embedding_model,
4. embedded_at.

### tables: generation_runs

1. id,
2. requested_profile_json,
3. selected_problem_ids_json,
4. prompt_hash,
5. model,
6. status,
7. output_json,
8. validation_report_json,
9. created_at.

## Retrieval algorithm (v1.5 target)

Given generation constraints (for example grade 7, module split, target difficulty mix):

1. apply hard filters in SQL:
   grade, module, topic/subtopic, answer format, difficulty bands, active flag.
2. fetch candidate pool (for example 200 to 800 items).
3. run semantic ranking against retrieval query intent using embeddings.
4. apply anti-duplication and diversity rules:
   topic spread, skill spread, source spread, lexical similarity threshold.
5. choose final K items by section template (Q1-Q23 slots).
6. build compact prompt context with source ids and strict output schema.

## Prompting and generation contracts

Generation prompt should include:

1. NVO structure rules (exact counts, module split, type constraints),
2. selected reference items only (not full corpus),
3. quality constraints (clarity, non-ambiguity, solvability),
4. formatting rules for math and diagrams,
5. output JSON schema and rejection criteria.

Post-generation validation should check:

1. schema validity,
2. question count and type distribution,
3. option integrity and answer consistency,
4. duplicate/near-duplicate detection,
5. language quality and banned pattern checks.

## Ingestion pipeline design

### step A: intake

1. accept raw document (txt/pdf/doc export),
2. persist source metadata,
3. assign ingestion job id.

### step B: parsing

1. segment into candidate problems,
2. detect number, type, module, options,
3. normalize math notation.

### step C: enrichment

1. classify topic/subtopic,
2. estimate difficulty,
3. infer skill tags,
4. optionally generate solution/explanation.

### step D: validation

1. required field completeness checks,
2. duplicate checks against existing corpus,
3. confidence scoring and manual review queue for low-confidence items.

### step E: indexing

1. write approved rows into problems,
2. generate embeddings,
3. update retrieval indexes.

## Quality governance

Use three quality gates:

1. ingestion gate: reject broken or ambiguous items,
2. retrieval gate: enforce diversity and policy constraints,
3. output gate: reject invalid generated exams.

Add periodic audits:

1. topic distribution balance,
2. difficulty calibration drift,
3. duplicate accumulation,
4. retrieval precision by query profile.

## Performance and scaling considerations

1. add indexes for common filters: grade, module, topic_id, difficulty, answer_format, is_active,
2. partial indexes for active content,
3. cache top candidate ids for frequent profiles,
4. asynchronous embedding generation via queue worker,
5. background reindex jobs for taxonomy updates.

## Security and data governance

1. role-based admin endpoints for ingestion and curation,
2. immutable audit trail for content edits,
3. provenance retention for every generated exam,
4. PII-free storage in problem content tables,
5. backup and recovery policy for corpus and run logs.

## Migration strategy from current system

### Phase 0: Planning and schema (1-2 days)

1. finalize taxonomy v1 (topics, subtopics, difficulty rubric),
2. create schema migration files,
3. define acceptance tests.

### Phase 1: Dual-read compatibility (2-4 days)

1. implement DB read service for problems,
2. keep current file-based generation as fallback,
3. add feature flag: use_db_retrieval.

### Phase 2: Backfill existing materials (2-5 days)

1. parse current JSON and full reference transcripts,
2. normalize into problem rows,
3. run QA report and fix low-confidence records.

### Phase 3: Retrieval v1 release (3-6 days)

1. metadata filter pipeline in production,
2. integrate retrieval output into NVO generation prompt builder,
3. keep file fallback for safety.

### Phase 4: Hybrid retrieval (3-7 days)

1. add embeddings and vector ranking,
2. add diversity reranker,
3. evaluate latency and retrieval precision.

### Phase 5: Full cutover (1-3 days)

1. switch default to DB retrieval,
2. keep fallback switch for rollback,
3. monitor generation success and quality metrics.

## Minimal implementation checklist

1. DB schema migrations committed,
2. ingestion CLI for batch import,
3. retrieval service with deterministic filters,
4. generation prompt builder accepts selected problem ids,
5. validation service for generated exam output,
6. metrics dashboard for retrieval and generation health,
7. rollback toggle documented.

## Suggested API surface (internal)

1. POST /content/sources/import
2. GET /content/problems/search
3. POST /content/problems/embeddings/rebuild
4. POST /nvo/retrieval/preview
5. POST /nvo/generate-from-retrieval
6. GET /nvo/generation-runs/{id}

## Risks and mitigations

1. Risk: noisy auto-tagging of topic/difficulty.
   Mitigation: confidence thresholds + manual review queue.
2. Risk: retrieval returns near-duplicate items.
   Mitigation: lexical + embedding dedupe and source diversity constraints.
3. Risk: latency spikes during embedding calls.
   Mitigation: offline embedding generation and cached candidate pools.
4. Risk: quality drift over time.
   Mitigation: periodic audits + score-based deactivation workflow.

## Next planning deliverables

1. final taxonomy document,
2. SQL migration draft,
3. ingestion mapping spec,
4. retrieval quality benchmark set,
5. rollout and rollback runbook.

## Practical recommendation

Start with Postgres metadata retrieval first, then add embeddings. This gives immediate control and performance gains with lower complexity, while preserving a clean path to semantic retrieval when corpus size grows.

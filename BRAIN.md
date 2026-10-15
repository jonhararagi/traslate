# NovelTrad Brain — Continuity and Recovery

This file is the durable project handoff. If a ChatGPT conversation is lost, read this file first, then README.md, docs/PROSA_Y_TRADUCCION_OFFLINE.md, docs/MODO_LOCAL_Y_MODO_PREMIUM.md, and the latest commits/PRs before changing code.

## Recovery command

When the user says "Eres el cerebro de NovelTrad":
1. Work only in https://github.com/jonhararagi/traslate unless the user explicitly changes scope.
2. Inspect the current `main` SHA, working branches, open PRs, latest CI runs, and repository tree. Do not assume this file's status notes are current.
3. Read this file and the project docs, then compare their statements with actual code and tests.
4. Continue from the highest-priority incomplete task below. Avoid asking the user to repeat information already stored here.
5. Report evidence with links/SHA/test results. Distinguish implemented, tested, merged, and released.
6. Do not claim a capability works until the implementation and relevant tests verify it. Update this file whenever architecture or project state materially changes.

## Product goal

NovelTrad is a local-first Windows reader and translation workspace for EPUB/PDF novels. Primary direction: English/Japanese/Korean source text to Spanish, offline-first, no paid API, safe originals, versioned translations, reliable backups, consistent per-novel terminology, and manual review before saving.

## User's hardware and resource policy

- PC: AMD Ryzen 5 5600G, 16 GB RAM.
- Prefer the deterministic local mode for routine glossary/phrase work. It must use negligible additional RAM and never load a neural model.
- Premium mode is a distinct **local neural model**, not a cloud subscription/API. It must be opt-in per action, never run automatically, avoid parallel model calls, use a conservative context/memory profile, and unload the model after use where supported.
- Never download model weights automatically. Explain model disk/RAM cost and require the user to install/configure it.
- Never call external translation APIs or silently upload book text. Only loopback/local inference is allowed unless the user explicitly changes the policy.
- The user does not want the neural mode running continuously. Default to Local.

## Permanent safety and data rules

- Keep imported originals immutable. Translation previews must not save automatically.
- Preserve version history and backup/restore protections.
- Do not auto-send book text to chat websites. The five manual assistance actions remain: (1) Proponer traducción al español, (2) Analizar contexto, personajes y relaciones, (3) Revisar continuidad sin inventar canon, (4) Revisar estilo y claridad, (5) Extraer términos candidatos para el glosario.
- Do not present deterministic substitutions as full translation.
- Novel-specific names, terms, and translations are not approved canon until supported by user-provided text or reliable source and explicitly reviewed. Distinguish verified, candidate, and user-approved terms.
- Do not invent character names, spellings, honorifics, plot facts, or terminology from thin secondary sources.

## First novel

Title: **I Became the Academy Villain's Daughter**. Alternative English title used by sources: **I Became the Daughter of the Academy's Villain**. Original Korean title: **아카데미 흑막의 딸이 되었다**. Protagonist name spelling shown in publisher/series listings: **Oknodie**. The in-world game title is reported as **Graduate from the Academy by Luck**. Treat title/name spellings as initial candidates to verify against the actual source edition and user-provided chapters; never silently rewrite them.

Novel profile: `data/novels/i_became_the_academy_villains_daughter.json`. Glossary starter terms must remain unapproved until checked against the actual edition. Build the per-novel glossary incrementally from imported chapters, tracking source form, Spanish target, entity type, context, source/evidence, approval status, and variant spellings.

## Modes

- **Modo local**: deterministic approved glossary/phrase rules and typography normalization; no neural inference, no network, minimal RAM. It cannot translate unknown sentences.
- **Modo premium**: optional local neural translation through a local runtime such as Ollama on loopback. No remote API. It is more RAM/CPU intensive and must be manually invoked. Use conservative request limits and unload after a call. If the local runtime/model is absent, show setup guidance; never silently fall back to cloud.
- Both modes must keep preview-only behavior; user manually transfers result to editor and saves.
- Never label Premium as ready until the runtime call is implemented and tested end-to-end. Document limitations and hardware cost honestly.

## Current known project state (verify before relying on it)

### Latest continuation — candidate glossary seeding (in progress on branch)

- Branch: `feat/academy-villain-glossary-seeding`.
- Added conservative matching of the imported filename against the first novel's display/alternate titles.
- Matching imports seed the book glossary from the profile's terminology candidates as `approved=0`, with provisional `preserve` rules and notes requiring verification against the imported edition.
- Unrelated book titles receive no candidates. The import response reports `unapproved_profile_candidates`.
- Added API tests for matching and non-matching titles. The test suite must still complete in GitHub Actions before this work is called verified.
- Updated the Local/Premium guide to document the behavior. This work is not merged yet; inspect the branch/PR/CI and then merge to main if checks pass.
- Important limitation: matching is based on the uploaded filename's title, not semantic recognition of the book. Use the exact novel title in the filename to seed candidates.

### Work added on main in this continuation (verify CI before calling it tested)

- Added this recovery file: `BRAIN.md`.
- Added the first novel candidate profile at `data/novels/i_became_the_academy_villains_daughter.json`; candidates are intentionally unapproved and must be verified against the user's exact imported edition.
- Added the Local/Premium selector to the reader UI. Local remains default and uses the deterministic rules engine.
- Added `POST /api/chapters/{chapter_id}/premium-translation-preview`: calls only `http://127.0.0.1:11434/api/generate`, default model `qwen2.5:3b` configurable via `NOVELTRAD_PREMIUM_MODEL`, 12,000-character cap, conservative context, and `keep_alive=0`. It does not save output. Model installation is manual; no cloud fallback.
- Added docs `docs/MODO_LOCAL_Y_MODO_PREMIUM.md` and tests for the UI, local preview behavior, and missing chapter.
- The implementation is committed directly to main; CI status for these latest commits must be inspected before calling it tested. Full-book batch translation, automatic chunking, and actual glossary extraction from imported chapters remain incomplete.

The last known main integration included:
- Local FastAPI/SQLite reader/editor for EPUB/PDF.
- Per-book glossary and versioned translation editor.
- Backup snapshots and scheduled backup CLI.
- Deterministic rule engine in `src/noveltrad/narrative_rules.py`.
- Existing deterministic preview endpoint `POST /api/chapters/{chapter_id}/offline-rules`.
- Existing manual narrative-assistance options listed above.
- The deterministic rules engine is not a general translator.
- Initial CI on the final PR tree was green on Windows and Ubuntu before the merge into main; do not claim a CI run on a particular merge SHA unless verified.

## Priority order

1. Verify this file and all documented behavior against the current repository and CI.
2. Run and repair CI for the Local/Premium selector and local model endpoint; test unavailable runtime, oversize chapters, timeout, and no-cloud/no-save guarantees.
3. Wire the novel-specific profile and candidate glossary into the app for user review without auto-approving or inventing canon.
4. Add tests for mode selection, model unavailable/timeout/oversize responses, privacy boundaries, and preview-only behavior.
5. Build chapter chunking, side-by-side review, glossary extraction suggestions, and consistency checks; never auto-approve generated terms.
6. Keep backups, recovery, import validation, original preservation, and translation history covered by regression tests.

## How to update this brain

At the end of each significant task, update status, commit/PR links, tested platforms and exact results. Do not replace a verified status with an assumption. This file is a handoff, not a substitute for inspecting the live repository.

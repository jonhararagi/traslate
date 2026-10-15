# NovelTrad Brain — Continuity and Recovery

This file is the durable project handoff. If a ChatGPT conversation is lost, read this file first, then README.md, docs/PROSA_Y_TRADUCCION_OFFLINE.md, docs/MODO_LOCAL_Y_MODO_PREMIUM.md, and the latest commits/PRs before changing code.

## Recovery command

When the user says "Eres el cerebro de NovelTrad":
- The user uses the word "memoria" to mean repository-stored project memory, not ChatGPT conversational memory. Treat `BRAIN.md` and the live repository as the durable source of truth.
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

### Latest continuation — candidate glossary seeding (merged to main)

- Branch: `feat/academy-villain-glossary-seeding`; PR [#5](https://github.com/jonhararagi/traslate/pull/5) merged to `main` in commit `38e00d66d136a23d393d50f2c4e59364080072fe`.
- Added conservative matching of the imported filename against the first novel's display/alternate titles.
- Matching imports seed the book glossary from the profile's terminology candidates as `approved=0`, with provisional `preserve` rules and notes requiring verification against the imported edition.
- Unrelated book titles receive no candidates. The import response reports `unapproved_profile_candidates`.
- Added API tests for matching and non-matching titles. GitHub Actions PR run [38732729383](https://github.com/jonhararagi/traslate/actions/runs/38732729383) passed on Ubuntu and Windows.
- Updated the Local/Premium guide to document the behavior. PR #5 is merged; confirm the current `main` SHA and CI before the next change.
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

1. Re-check current `main`, the latest CI runs, and this file before each continuation; the glossary-seeding PR #5 is merged and its PR and main-merge workflows passed on Ubuntu and Windows.
2. Premium negative-path tests were added for unavailable Ollama, timeout, oversized input, no cloud fallback, and no-save behavior in commit `eacbfbf2e6b752c799638f44b937f5f9966d534b`. Verify the resulting GitHub Actions run; malformed-response coverage remains to add.
3. Build chapter chunking and side-by-side review with explicit context carryover, retry controls, and per-fragment preview; never save automatically.
4. Add glossary extraction suggestions from imported chapters with evidence snippets and candidate status; never auto-approve names, titles, or translations.
5. Add consistency checks for protected names, honorifics, terms, and character spellings using the per-novel profile.
6. Keep backups, recovery, import validation, original preservation, and translation history covered by regression tests.

## How to update this brain

At the end of each significant task, update status, commit/PR links, tested platforms and exact results. Do not replace a verified status with an assumption. This file is a handoff, not a substitute for inspecting the live repository.


## Continuation — first Windows packaging path (2026-10-15)

- Branch: `feat/windows-first-release`; PR [#6](https://github.com/jonhararagi/traslate/pull/6) is open and unmerged.
- Added optional `build` extra with PyInstaller, a desktop launcher that opens the local UI in the default browser, a PowerShell build script, Windows CI packaging workflow, and release instructions in `docs/PRIMERA_ENTREGA_WINDOWS.md`.
- The Windows workflow is intended to run the full pytest suite before producing a portable `dist/NovelTrad/` artifact. The launcher binds only to `127.0.0.1:8765`; user data remains in `%LOCALAPPDATA%\\NovelTrad`. It does not bundle models or change the default Local mode.
- External implementation research: Argos Translate is a potential offline translation engine with Japanese, Korean, English, and Spanish listed among supported languages; package/model availability and quality must be validated per direction before adoption. PyInstaller supports bundling Python apps for Windows. References: https://github.com/argosopentech/argos-translate and https://pyinstaller.org/en/stable/operating-mode.html.
- Status distinction: packaging code is committed on this branch, but not yet validated by the new Windows workflow or a clean-machine manual test. Do not call the Windows app released until the artifact has been downloaded and smoke-tested. This branch does not complete batch translation, OCR, or contextual chunking.


## Continuation — first novel source and terminology pilot (2026-10-15)

- Added official/discovery source metadata and 18 unapproved terminology candidates to `data/novels/i_became_the_academy_villains_daughter.json` on `feat/windows-first-release` (PR #6). Current profile includes the Novelpia Korean original, official Tapas English comic adaptation, and a Novel Updates discovery listing for the English novel. Source distinctions and URLs are in `docs/PILOTO_OKNODIE_Y_TERMINOLOGIA_GAMER.md`.
- Added synthetic diagnostic cases in `data/benchmarks/academy_villain_context_cases.json` for Oknodie, farm/farming, level, steal/Steal, tsundere, build, drop, and min-maxing. These are invented test sentences, not excerpts or canon from the novel.
- Added `tests/test_academy_villain_profile.py` to verify official source metadata, unapproved status, and context-risk cases.
- Critical limitation: no full chapter has been downloaded or imported. The official Tapas English version is a comic adaptation, not prose EPUB/PDF; OCR is not implemented. Novelpia is the official Korean source and access may require account/paid chapters. Do not scrape or redistribute commercial chapters. Real translation-quality validation requires a user-authorized EPUB/PDF of the exact edition or an explicitly provided excerpt.
- No neural/offline engine has been run on a real chapter in this continuation. Do not claim the benchmark passed on CI until GitHub Actions results are inspected. The existing deterministic engine is not a full translator and global substitutions cannot safely resolve ambiguous words; candidates remain unapproved.

- Follow-up implementation: glossary mode `contextual` is now accepted by `TermRule` and passed through the offline preview API. Approved contextual terms are protected from global substitutions and produce a review warning with occurrence count; they are not silently replaced. Tests were added in `tests/test_narrative_rules.py`. This is a safety improvement, not full per-occurrence semantic disambiguation.

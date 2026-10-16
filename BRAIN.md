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
- Premium mode is intended to use a visible Chromium window signed into the user's own ChatGPT or Gemini account. NovelTrad generates the prompt and manages bounded chunks; it must not collect or store provider passwords, cookies, or tokens.
- The initial safe implementation should use explicit user-mediated prompt/result handoff. Browser automation is optional future work, must be visible and opt-in, and must stop at login, CAPTCHA, consent, rate limits, or unexpected pages.
- Ollama is not the account-based Premium mode. If retained, it must be labeled as a separate optional local-neural mode and must never run continuously or download model weights automatically.
- Do not silently transmit book text. The user must explicitly start each provider translation job and know which provider receives the selected text. Default to Local.

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
- **Modo premium (objetivo de producto)**: translation through a visible Chromium window signed into the user's ChatGPT or Gemini account. NovelTrad constructs the prompt from approved glossary rules, the novel's style guide, relevant continuity context, and a bounded source chunk. Initial delivery must support a transparent manual handoff; browser automation must not be assumed implemented.
- Ollama-backed inference currently exists in main under the old Premium label and is an architecture mismatch to migrate. It must either be moved to a separately named optional local-neural mode or removed after equivalent account-based flow is tested.
- Both modes must keep source text immutable, persist provisional chunk results, and require review before applying. Never label account-based Premium ready until its UI, prompt generation, handoff, queue recovery, privacy boundaries, and tests work end-to-end.

## Latest continuation — Chromium Premium first implementation (draft PR #14)

- Branch: `feat/chromium-account-premium`; PR [#14](https://github.com/jonhararagi/traslate/pull/14) remains draft/open/unmerged. `main` is not modified.
- Commit `753a0f48ea1fdfff1f375dbc05441eccb41caeab` adds the first functional chapter-level account handoff in `src/noveltrad/main.py`.
- UI: Premium provider selector (ChatGPT/Gemini), button to open a dedicated persistent browser profile, and per-fragment copy-prompt + paste-result fields. Editor transfer stays disabled until every fragment has a non-empty result.
- Browser launcher finds an already installed Chrome/Chromium/Edge and does not download a browser. It uses a provider-specific profile under NovelTrad's local data directory and starts with image loading disabled plus reduced background activity. The user signs in directly on the provider site. NovelTrad does not collect credentials or cookies and does not auto-submit source text.
- Prompts contain the approved glossary with rule hints, editorial style selection, source delimiters, bounded chunks, and a limited prior-source context excerpt. Source chapters remain unchanged; preview is not saved automatically.
- Limitations: focused tests and manual Windows validation are not yet confirmed. The persistent whole-book queue still uses the old Ollama endpoint and is not migrated. Do not describe Premium as release-ready until queue integration, tests, and Windows/translation-quality checks pass.
- GitHub Actions were triggered for commit `753a0f48ea1fdfff1f375dbc05441eccb41caeab`; check their final conclusions before the next status report.

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


## Continuation — Windows package CI verified and PR #6 merged (2026-10-15)

This section supersedes earlier statements above that PR #6 is open or that its Windows workflow is still pending.

- PR [#6](https://github.com/jonhararagi/traslate/pull/6) was squash-merged into `main`. Merge commit: `e3681e1b304f9440103577deec4d439e50f1d8da`.
- The branch had no divergence from `main` at comparison time: 24 commits ahead, 0 behind.
- On tested PR head `e9792510e7cdb61e7d78d3b3e3883d991d8db9ad`, GitHub Actions run [Windows Portable Build #11](https://github.com/jonhararagi/traslate/actions/runs/38758564092) completed successfully. Steps passed: install dependencies, pytest, PyInstaller portable build, artifact upload.
- GitHub Actions run [Tests #286](https://github.com/jonhararagi/traslate/actions/runs/38758563984) passed on both `windows-latest` and `ubuntu-latest`; Windows PowerShell maintenance-script validation passed on Windows.
- Artifact: `NovelTrad-Windows-x64`, 40,696,963 bytes, SHA-256 `f6d3b7578ab1766feac9dfb21350a79cd2c810f4b810e16a26271d26a7b2bca0`. Download it from [the Actions run](https://github.com/jonhararagi/traslate/actions/runs/38758564092). It expires on 2026-10-29; it is a temporary Actions artifact, not a permanent GitHub Release.
- This proves the CI-built portable folder was produced; it does **not** prove clean-machine manual startup/import/backup/restore/export or usability on the user's PC. Manual smoke test remains outstanding.
- The product is not a full automatic translator yet. Local mode is deterministic glossary/phrase processing, not neural sentence translation. Premium local inference is an optional preview path, not a validated full-book translation pipeline. Chunking, context carryover, side-by-side chapter review, OCR, and real-chapter benchmark remain incomplete.
- First-novel pilot: 18 unapproved candidate terms and synthetic diagnostics are present. Do not claim actual novel chapter translation or semantic disambiguation until an authorized excerpt/EPUB/PDF is imported and evaluated.
- Next priority: run a clean Windows smoke test using the artifact and record results; then implement chunked preview + side-by-side review with explicit carryover, retry controls, and no auto-save. Add malformed Ollama response tests and evidence-based glossary extraction afterward.


## Continuation — chunked chapter translation implementation (2026-10-15)

- Working branch: `feat/chunked-premium-translation`; not merged into `main` yet.
- Added `POST /api/chapters/{chapter_id}/premium-translation-preview/chunked`. It processes one chapter sequentially in bounded source chunks (default 3,500 chars; configurable 1,000–6,000), up to 200,000 source characters per chapter. It splits at paragraph/sentence boundaries where possible and passes the tail of the previous translated chunk as reference-only continuity context.
- Response includes each chunk's original and translated text, index and character counts, plus a combined preview. It is preview-only; it does not update `translated_text`, translation history, or the immutable original. If a chunk fails, the endpoint returns an explicit chunk index and publishes no partial saved translation.
- Reader UI now uses the chunked endpoint in Premium mode and displays editable original/translation pairs. Edits are combined into the preview; “Pasar al editor” remains explicit, and the user must still press “Guardar traducción”.
- Added `tests/test_chunked_translation.py` for chunk boundaries, preservation, sequential context carryover, and no-save behavior. These tests are authored but must not be called passing until GitHub Actions completes.
- Important limits: this is chapter-level sequential chunking, not a whole-book batch queue; there is no resume-from-failed-chunk button yet; translation quality still requires a user-provided authorized chapter and actual local Ollama model. Local mode remains deterministic glossary/rule processing, not general neural translation. Full-book queueing, retry/resume controls, evidence-based glossary extraction, OCR and real-chapter quality evaluation remain incomplete.
- Next: inspect PR CI, fix any failures, then test the package on clean Windows with Ollama installed manually and a user-authorized excerpt. Do not merge or release on the basis of authored tests alone.

## Continuation — chapter chunking merged and response validation hardening (2026-10-15)

- PR [#7](https://github.com/jonhararagi/traslate/pull/7) was squash-merged into `main` after GitHub Actions passed on both Ubuntu and Windows and the portable Windows package job passed. Merge commit: `3125f621eac83ec38b41a8817872f5410433d4da`.
- Verified CI runs: [Tests, Ubuntu + Windows](https://github.com/jonhararagi/traslate/actions/runs/38769066936) and [Windows portable build](https://github.com/jonhararagi/traslate/actions/runs/38769067357). These prove automated tests and packaging succeeded; they do not prove real-model translation quality or a clean-machine manual smoke test.
- Merged functionality: sequential chapter chunking (3,500 chars default, 1,000–6,000 configurable; max 200,000 source chars), reference-only previous translation context, editable original/translation pairs, and preview-only output. No automatic save.
- New hardening branch: `fix/premium-response-validation`. It converts valid JSON with an unexpected shape and empty model output into explicit HTTP 502 errors instead of leaking runtime exceptions; regression tests and documentation corrections are added. PR/CI status must be updated after Actions completes.
- Still incomplete: durable whole-book queue, restart-safe progress and retry/resume, actual authorized chapter benchmark, evidence-based glossary extraction, OCR, and clean Windows manual verification with Ollama installed by the user.
- Do not state that the app is a complete automatic translator. Modo local is rules/glossary only; Premium is local neural translation with human review and has not yet been benchmarked on the user's actual novel edition.



## Continuation — durable full-book translation queue (2026-10-15)

- PR [#8](https://github.com/jonhararagi/traslate/pull/8) was merged after both Ubuntu/Windows automated tests and the portable Windows build passed. Merge commit: `5c7151e8e08f7a590e674dc61360f8fda0b26ded`. CI: [Tests run 38769827775](https://github.com/jonhararagi/traslate/actions/runs/38769827775), [portable build run 38769827777](https://github.com/jonhararagi/traslate/actions/runs/38769827777).
- Current implementation branch: `feat/full-book-translation-queue`. It adds durable SQLite tables for jobs and chunks, snapshots the approved glossary when a queue is created, processes one chunk per explicit request, saves successful outputs immediately, pauses/retries failed work, and recovers in-flight chunks as pending after a process restart.
- Library UI includes preparing a book queue, start/resume, pause, retry-failed, progress counts, selecting/reading individual chunks, editing and explicitly marking each result reviewed, and applying all reviewed results to untranslated chapter rows. Applying is blocked until all chunks are completed/reviewed and refuses to overwrite chapter translations created by another operation.
- API surface: create/list jobs per book; get job progress; run-next, pause, resume, retry-failed; get/edit a chunk; apply a reviewed job. Queue creation does not call Ollama. Translation is initiated manually and remains local-only.
- Added `tests/test_translation_jobs.py` to cover queue persistence, chunk sequencing/context carryover, no-save-before-apply, mandatory review, retry after a provider failure, and recovery after a simulated shutdown. These tests must not be called passing until GitHub Actions completes.
- Remaining product validation: CI for this branch, clean-Windows manual smoke test with Ollama installed manually, and a user-authorized excerpt from the exact novel edition to evaluate omissions, repeated text, terminology and name preservation. OCR and evidence-based glossary candidate extraction remain separate unfinished features. Modo local remains deterministic rules rather than general translation.


## Continuation — whole-book queue merged (2026-10-15)

- PR [#9](https://github.com/jonhararagi/traslate/pull/9) was squash-merged into `main`. Merge commit: `4673d937d276a8a9d50e555fc2fe0ced8b0851c6`.
- Final tests on head `256db12b987657e9002a22f8794a35798bf0243f` passed in [the Ubuntu/Windows CI run](https://github.com/jonhararagi/traslate/actions/runs/38772146450). The portable Windows build on commit `78b771b38701e828804d0d9b4915a31772f57262` (contains all app code; later head commit only adds an extra test assertion) passed at [run 38772132835](https://github.com/jonhararagi/traslate/actions/runs/38772132835). Artifact ID: `11992740465`, name `NovelTrad-Windows-x64`, size 40,714,207 bytes, retained for 14 days.
- Queue implementation is now in `main`: persistent job/chunk state in SQLite, per-chunk progress and attempts, glossary snapshot at queue creation, local-only serial inference, resume after app restart, retry failed chunks only, side-by-side review, explicit apply after every chunk is reviewed, protection against overwriting chapter translations, immutable originals, and version history snapshot on apply.
- A newer push-triggered CI run for the merge commit was started: [run 38772528998](https://github.com/jonhararagi/traslate/actions/runs/38772528998). Refresh its status before treating the post-merge workflow as complete; pre-merge tests and the matching app-code portable build have passed.
- Still not fully validated: running the actual portable EXE on a clean Windows profile with user-installed Ollama; measuring omissions/repetitions/terminology against an authorized excerpt from the exact *I Became the Academy Villain's Daughter* edition; OCR for scanned PDFs/comics; evidence-based glossary candidate extraction. These are explicit quality/feature gaps, not CI failures.
- Do not call the product 100% complete until the clean-Windows manual smoke test and the authorized real-chapter quality benchmark are done. Modo local remains deterministic rules/glossary processing, not general translation.


## Continuation — evidence-based glossary candidate extraction (2026-10-15; PR #10 merged)

- PR [#10](https://github.com/jonhararagi/traslate/pull/10) was squash-merged into `main` at `4c8589dd21de71ec888f48cf9dccb15818105d69`.
- [Tests on Ubuntu and Windows](https://github.com/jonhararagi/traslate/actions/runs/38773399044) passed. [Windows portable build and upload](https://github.com/jonhararagi/traslate/actions/runs/38773399114) passed. Artifact ID `11992213276`, name `NovelTrad-Windows-x64`, 40,722,885 bytes.
- Adds SQLite `glossary_candidates` storage keyed by normalized term + book, with occurrence counts, up to three local evidence snippets, chapter/title references, candidate notes, pending/approved/ignored state and a linked glossary entry identifier.
- A local-only scan detects terms from `data/novels/i_became_the_academy_villains_daughter.json`, a conservative gamer/otaku vocabulary, and recurring title-case names/entities. Scan is limited to 25,000,000 source chars and 500 candidates per pass. It does not invoke a model or mutate source text.
- UI: `Buscar candidatos en el texto original`; inspect chapter snippets, edit preferred spelling, select preserve/protect/contextual/translate rule, then explicitly approve or ignore. Approval updates an existing unapproved seeded glossary entry when applicable; a scan never approves automatically. Rescans preserve candidate status.
- Fixes the profile resource path for PyInstaller onedir: try source-checkout data path, then the `_internal/data` path used by portable Windows package. Test helper verifies both path layouts.
- `tests/test_glossary_candidates.py` tests profile path resolution, evidence-backed detection of Oknodie/Steal skill/farm/tsundere, no model invocation, no auto-approval or source mutation, explicit approval, ignored-state persistence across re-scan, and duplicate approval protection.
- Candidate heuristics may have false positives and only read imported searchable text; OCR remains unsupported. Real-chapter quality and clean-Windows manual testing remain open.


## Continuation — translation quality review prompts (2026-10-15; PR #11 merged)

- PR [#11](https://github.com/jonhararagi/traslate/pull/11) was squash-merged into `main` at `11bf953c86520f10bd738edbdbb5e6b10cb7a855`.
- [Ubuntu and Windows tests](https://github.com/jonhararagi/traslate/actions/runs/38774466075) passed; [portable Windows build and artifact upload](https://github.com/jonhararagi/traslate/actions/runs/38774466093) passed on the exact application code before merge.
- Current Windows artifact ID: `11992279247`, `NovelTrad-Windows-x64`, 40,727,383 bytes. Verified ZIP SHA-256: `708a6a4e6a3461fc91bc81527f66faffc7c50545409dc6b39bbb14cb09fdea00`; it contains `NovelTrad.exe` and `_internal/data/novels/i_became_the_academy_villains_daughter.json`.
- Added migrated `translation_job_chunks.quality_warnings_json` with a schema migration for existing SQLite databases and lazy backfill for completed queue items created before the field existed.
- `_translation_quality_warnings` flags outputs that are empty/identical, suspiciously short/long, have severe paragraph-structure changes, contain common omission/model placeholders, or repeat long sentences beyond repetition seen in source. These are limited warnings, not a translation score, and never certify output correctness. Warnings are recomputed after manual review edits.
- Queue UI shows warning counts in the progress line and per-chunk warning detail in the review surface. Warning-free chunks still require explicit human review before application.
- Added `tests/test_translation_quality.py` for helper behavior, conservative repetition handling, end-to-end persistence and warning clearance after editing. Tests passed on Ubuntu and Windows.
- Real authorized-chapter quality benchmark and clean-Windows manual smoke test remain not performed. Do not claim 100% completion until those are actually tested.


## Continuation — mandatory glossary consistency checks (2026-10-15; PR #12 merged)

- PR [#12](https://github.com/jonhararagi/traslate/pull/12) merged at `adff3d19d5eeca9a970daac55806bed95155c364`.
- [Ubuntu/Windows test workflow](https://github.com/jonhararagi/traslate/actions/runs/38775368775) passed on exact PR head `e1db976a67c659588aa535ef0b2b5e05ee769427`; [Windows portable package build/upload](https://github.com/jonhararagi/traslate/actions/runs/38775368574) passed on the same app code before merge.
- Current build artifact ID `11994220267`, name `NovelTrad-Windows-x64`, size 40,727,974 bytes; SHA-256 `33820a1b715913c73de8293136a9707f3e81b8564bed78b0103e8297a21c92d1`. ZIP integrity checked; contains `NovelTrad.exe` and the bundled Oknodie terminology profile under `_internal/data/novels/`.
- Premium prompt now sends explicit instruction labels for approved `protect`, `preserve`, `translate`, and `contextual` rules. Persistent queue glossary snapshots contain the rule alongside source/preferred term.
- Quality warnings check whether a preferred form for a mandatory rule is present in output when its source term appears in the chunk. Missing `Oknodie`, `Steal skill`, or approved translations such as `farm => farmear` are flagged; `contextual` terms such as `tsundere` are not forced. Checks run after model output and after manual edits, but are literal/conservative and non-blocking.
- Tests cover missing mandatory terms, non-mandatory contextual terms, queue rule snapshots and prompt directives. Clean-Windows manual smoke test and real authorized-chapter translation benchmark remain outstanding.


## Architecture correction — account-based Chromium Premium (2026-10-16)

- User clarified that Premium must use a Chromium window signed into the user's own ChatGPT or Gemini account, with NovelTrad generating the translation prompt and rules. It is not Ollama and not an API key integration.
- Decision and acceptance criteria: [docs/PREMIUM_CHROMIUM_CHATGPT_GEMINI.md](docs/PREMIUM_CHROMIUM_CHATGPT_GEMINI.md).
- Current main still implements an Ollama endpoint under the Premium label. This is an explicit migration gap, not a completed feature. Do not claim the Chromium integration exists until implementation and end-to-end tests land.
- First implementation should favor visible, user-mediated prompt/result handoff over brittle silent DOM automation. Never store account credentials/cookies or bypass provider controls. Ollama can only remain as a separately named optional mode.

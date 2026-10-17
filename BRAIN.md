# NovelTrad Brain — Continuity and Recovery

## Initial terminology profile and evidence-gated approvals — 2026-10-17

PR #16 remains open and Draft. Authorized branch: `feat/offline-linguistic-narrative-core`. Do not merge or write to `main`. Main SHA remains `6ebca3e06565456d473a44b1d62e14012531cde8`.

- Initial implementation SHA `aea36be4c1dcec544422e977693eb0f820c8066f` reported three test failures; follow-up `4b2cca22e05595c92b7b89a80204931c932f69dd` fixed those and exposed one remaining legacy wording assertion. This follow-up explicitly marks a starter term as not approved by the user and adds a regression test preventing removal of profile provenance while the candidate is pending. CI must pass on this newest SHA before the phase is technically verified.
- The first-novel profile carries 19 unapproved candidates, including `lvl`, each with proposed rule, evidence class, evidence status, chapter-evidence requirement, and a human-review checklist. The display title is metadata, not a glossary term.
- Provisional rule suggestions: `Oknodie` → `protect`; `Graduate from the Academy by Luck` and `tsundere` → `preserve`; context-sensitive terms such as `farm`, `farmed`, `level`, `steal`, `Steal skill`, and `lvl` → `contextual`. All remain unapproved.
- The candidate API exposes suggested target/rule and evidence origin. The review UI pre-fills suggestions but states they are not proof of meaning. Approval requires a nonempty literal excerpt collected from the imported chapter. The general edit endpoint blocks directly approving a seeded profile entry until the evidence-backed candidate review has been approved.
- Documentation: `docs/PERFIL_TERMINOLOGICO_INICIAL.md`. Tests cover profile metadata and review requirements, UI prefill, evidence-gated approval, and source text preservation.
- The novel's actual chapter text has not been supplied for this phase. No proposed target or term sense is claimed verified against the exact edition. Scanning a user-authorized import and human approval remain necessary.
- Windows portable build and full cross-platform tests must complete successfully on the follow-up SHA before calling this phase technically verified.

## User-requested queue controls and prompt options — 2026-10-16

PR #16 remains open and Draft; work only on `feat/offline-linguistic-narrative-core`. Do not change `main` or merge the PR.

### Implementation
- Code and focused tests were committed on implementation SHA `5909d619fdff37dbdfe25cbfb699164676ba3c0f`; later commits add README/documentation and this continuity note.
- Queue prompt options: `faithful_natural`, `gamer_terms`, `fluent_spanish`, `literal_review`.
- Optional user instruction is validated to a maximum of 2,000 characters and is included only in the next manually copied prompt. It does not modify the original, glossary, or canon.
- Quick action selector: `Seguir` requests the next prompt/resumes a paused job; `Parar` pauses without deleting saved progress; `Enviar` executes the selected action within NovelTrad, with the send-response choice saving the pasted response as unreviewed.
- No prompt is automatically submitted to ChatGPT or Gemini. Provider use remains visible/manual.
- Tests added in `tests/test_translation_jobs.py` and `tests/test_frontend.py` cover prompt style/custom instruction, rejection of unknown styles before reserving a chunk, and the controls in the HTML.
- User documentation: `docs/OPCIONES_TRADUCCION_Y_CONTROLES_RAPIDOS.md`.
- Implementation SHA CI run IDs: Tests `38983810048`; Windows Portable Build `38983810012`. Ubuntu full tests were observed successful while Windows jobs were still running at the time of the check. Re-check the final branch head's workflows before reporting verified status; do not transfer CI results between SHAs.


## PR #16 close-out status — 2026-10-16 (active; supersedes prior pending notes)

PR: https://github.com/jonhararagi/traslate/pull/16. Keep open and draft; do not merge or close.
Authorized branch: `feat/offline-linguistic-narrative-core`. Main SHA verified at inspection: `6ebca3e06565456d473a44b1d62e14012531cde8`; no changes were made to main.

### Verified code SHA and existing CI evidence

The alias-canonicalization implementation is verified on code SHA `545bd10c514c9ce171a66b85387f06b365220d6a`. This SHA is the code/evidence SHA; any later commit that only updates this file or workflow configuration must not inherit its CI result.

- Tests push: https://github.com/jonhararagi/traslate/actions/runs/38942571156
- Tests PR (Ubuntu and Windows): https://github.com/jonhararagi/traslate/actions/runs/38942576889 — both jobs succeeded; focused linguistic-analysis step and full pytest suite succeeded on both platforms. Windows PowerShell maintenance-script validation also succeeded.
- Windows Portable Build: https://github.com/jonhararagi/traslate/actions/runs/38942576875 — dependency installation, automated tests, PyInstaller build, packaged executable smoke test and artifact upload all succeeded.
- Packaged smoke test: `NovelTrad.exe` started and `/api/health` returned `status=ok`, `mode=local-first`. This does not prove manual use on the user's PC or real translation quality.
- Artifact: `NovelTrad-Windows-x64`; artifact ID `12063248589`; size `40742729` bytes; GitHub Actions digest `sha256:c73d3e0b015e314415a4f52addab6f407cc4f3cf1e57bfdc888d38d290c9a917`; 183 ZIP entries were checked and ZIP integrity passed. Contents included `NovelTrad.exe` and application data. Run metadata identifies head SHA `545bd10c514c9ce171a66b85387f06b365220d6a`. Artifact expires 2026-10-30T17:50:57Z.
- Non-blocking warnings: `StarletteDeprecationWarning` concerning httpx/Starlette TestClient and action/runtime deprecations (Node.js 20, `punycode`, `url.parse()`). These did not fail the jobs. No independent lint/type-check is configured.

### Documentation and CI filter close-out

This section records the verified evidence above and supersedes older pending statements about that same SHA. Historical sections below remain archival and must be read as historical where they conflict with this section.

### Verification of the authorized branch head `3550bede1028f3dc93a9d10f9dc7adc526028edd`

- Commit `3550bede1028f3dc93a9d10f9dc7adc526028edd` changes only `.github/workflows/windows-build.yml`, adding `BRAIN.md` to `pull_request.paths`; existing path filters and build steps are retained. The current workflow file also includes `BRAIN.md` in `push.paths`.
- Tests workflow run 471: https://github.com/jonhararagi/traslate/actions/runs/38951023226 — Ubuntu and Windows succeeded. Focused tests: `9 passed` on each platform. Full suite: Ubuntu `114 passed, 1 warning in 7.37s`; Windows `114 passed, 1 warning in 26.01s`. Windows PowerShell maintenance-script validation succeeded; it was skipped on Ubuntu as expected.
- Windows Portable Build run 72: https://github.com/jonhararagi/traslate/actions/runs/38951023166 — dependency installation, full automated suite (`114 passed, 1 warning in 28.34s`), PyInstaller build, executable smoke test and artifact upload succeeded. Smoke test confirmed `NovelTrad.exe` started and `/api/health` returned `status=ok`, `mode=local-first`.
- Artifact for exact head SHA `3550bede1028f3dc93a9d10f9dc7adc526028edd`: `NovelTrad-Windows-x64`, ID `12068377616`, size `40742756` bytes, GitHub digest `sha256:d95649e291a77e5e0fac507ab8c5603405ca82f3b22ab769012899b921d34267`, expires `2026-10-30T18:56:44Z`. Downloaded the artifact and independently confirmed the SHA-256 and byte size. ZIP validation passed with 183 entries and no corrupt entry; contents include `NovelTrad.exe`, `_internal/data/benchmarks/academy_villain_context_cases.json`, and `_internal/data/novels/i_became_the_academy_villains_daughter.json`.
- Non-blocking warnings: Starlette/httpx TestClient deprecation; PyMuPDF `fitz` API deprecation; PyInstaller hidden import `tzdata` not found; GitHub Actions Node.js 20, `punycode`, and `url.parse()` deprecation notices. They did not fail the workflows. No independent lint/type-check is configured.

The evidence above applies to head SHA `3550bede1028f3dc93a9d10f9dc7adc526028edd`, not to `545bd10c514c9ce171a66b85387f06b365220d6a` or to any later commit. This documentation update is intended to be the final continuity edit for this phase; after it is committed, verify CI and the portable artifact on the resulting exact SHA, report those results externally, and do not create another documentation-only commit merely to record that run. Manual Windows use and evaluation of a real, user-authorized translation excerpt remain PENDING. Do not claim translation quality has been verified.

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

## Active implementation status — 2026-10-16 (supersedes older status notes below)

- PR #14 was merged into main with squash merge commit eff2c628d2af98fe3db9c9d18a6bf239161755bf. Main now contains the account-based Chromium Premium chapter flow and the migrated persistent whole-book queue.
- Product constraint: Local mode remains deterministic and lightweight. Account-based Premium uses the user's own ChatGPT/Gemini account in a visible, persistent Chromium-family profile. NovelTrad must not auto-submit source text or read/store provider credentials/cookies.
- The persistent whole-book queue stores the selected provider; reserves one chunk at a time; generates a bounded prompt; and persists manually pasted output as completed but unreviewed. Review and apply remain separate; apply requires every chunk completed and reviewed.
- Queue schema migration adds a provider column with chatgpt default for existing databases. Startup recovery returns interrupted running chunks to pending and pauses their job. Pause/resume/retry/restart behavior is covered by SQLite-backed tests.
- Pre-close-out `main` SHA `ca7eadf7c1847a64d95997c0ad98f6e062ca45d0` passed [Ubuntu/Windows tests](https://github.com/jonhararagi/traslate/actions/runs/38896672388) and [portable build + packaged smoke test](https://github.com/jonhararagi/traslate/actions/runs/38896672374), but its ZIP predates the provider-isolation fix. Do not treat that older binary as the latest package.
- This is CI evidence, not a manual test on the user's PC. Actual sign-in and a quality review using an authorized excerpt remain pending. Chromium consumes RAM; image blocking does not guarantee a fixed saving.
- PR [#15](https://github.com/jonhararagi/traslate/pull/15) merged as `b4eec78a956614ef318f2ebc3c1235b784d4fa03`. It makes `/run-next` Ollama-only (an explicit API provider), rejects ChatGPT/Gemini jobs before local inference, and rejects manual prompt/submission endpoints for Ollama jobs. The normal UI exposes only ChatGPT/Gemini. PR tests passed on Ubuntu/Windows in [run 38903477554](https://github.com/jonhararagi/traslate/actions/runs/38903477554); the portable build and packaged smoke test passed in [run 38903477674](https://github.com/jonhararagi/traslate/actions/runs/38903477674). Post-merge checks also passed on `b4eec78` in [run 38903735293](https://github.com/jonhararagi/traslate/actions/runs/38903735293) and [run 38903735461](https://github.com/jonhararagi/traslate/actions/runs/38903735461).
- The continuation sections below this current verified-state section are an archival changelog; old statements about PRs being open, features unimplemented, or CI pending are superseded by this active status.

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
- The legacy chapter-preview endpoint still calls Ollama on loopback, and `/api/translation-jobs/{job_id}/run-next` is a legacy local-neural route. It must never process a ChatGPT/Gemini job. The provider-isolation follow-up makes Ollama an explicit API-only `provider: "ollama"` choice and rejects crossing between Ollama and manual account endpoints; do not present it as account Premium or expose it in the normal UI.
- Both modes must keep source text immutable, persist provisional chunk results, and require review before applying. Never label account-based Premium ready until its UI, prompt generation, handoff, queue recovery, privacy boundaries, and tests work end-to-end.

## Historical note — Chromium Premium implementation (PR #14, merged 2026-10-16)

PR #14 delivered the visible persistent Chromium profile, manual ChatGPT/Gemini prompt/response handoff for chapter previews, and the persistent whole-book queue. It merged as `eff2c628d2af98fe3db9c9d18a6bf239161755bf`. Its initial branch SHA and pre-merge test status are historical; use the active implementation status above and the audit document, not the initial draft notes below.

## Current verified project state — branch audit baseline 2026-10-16

- Original audit baseline: `ca7eadf7c1847a64d95997c0ad98f6e062ca45d0`; the provider-isolation close-out was then merged by PR #15 as `b4eec78a956614ef318f2ebc3c1235b784d4fa03`. PRs #1–#15 are now closed and merged. The audit maps the original 14 feature branches plus the close-out branch in [docs/AUDITORIA_RAMAS_Y_PENDIENTES.md](docs/AUDITORIA_RAMAS_Y_PENDIENTES.md).
- Integrated capabilities include reader/library; EPUB/text-PDF import; persistent local storage; immutable source and versioned translations; on-demand and scheduled recoverable backups; deterministic offline rules; the Oknodie novel profile and unapproved terminology candidates; evidence-backed glossary extraction; heuristic quality warnings; glossary consistency warnings; the Windows portable build and packaged startup smoke test; and the visible Chromium ChatGPT/Gemini handoff plus persistent queue.
- CI on the baseline SHA succeeded: [Ubuntu + Windows tests](https://github.com/jonhararagi/traslate/actions/runs/38896672388) and [Windows portable build + packaged smoke test](https://github.com/jonhararagi/traslate/actions/runs/38896672374). Artifact: `NovelTrad-Windows-x64`, SHA-256 `695d5c45bbc34d7a8437fa28b8076329635de086ab7a5ac88fb0095522b98633`.
- Provider safety follow-up in `fix/provider-isolation-and-project-closeout`: prevent the Ollama `run-next` route from processing ChatGPT/Gemini jobs, and prevent manual prompt/submission endpoints from handling an explicitly Ollama job. Tests and documentation are changed on that branch; do not consider them integrated until its PR is merged and post-merge CI passes.
- Older feature branches remain as provenance, not as release candidates. The PRs were squash-merged and branches have since diverged. Do not merge old branch heads wholesale or delete them merely to make the branch list look clean.

## Priority order

1. Perform the user-side Windows check of the final package: sign in directly to ChatGPT/Gemini, test a chapter preview and a short persistent queue, restart, pause/resume/retry, review-before-apply and EPUB export. CI cannot validate the user's personal login or actual translation quality.
2. Evaluate an authorized excerpt from the exact *I Became the Academy Villain's Daughter* edition. Measure omissions, repetitions, paragraph drift and consistency of Oknodie and context-sensitive terms such as `farm`, `level`, `Steal`, and `tsundere`.
3. Add OCR only as a separately tested feature for scanned PDFs/comic pages; until then, scanned PDFs remain unsupported.
4. Retain regression coverage for backups/restore, source immutability, import security, translation history, frontend syntax, glossary evidence/approval, queue recovery, provider isolation and EPUB export. Manually validate reader accessibility and complex EPUB navigation.
5. Treat Argos Translate or any local neural engine as a separate optional future experiment. Do not add model downloads or continuous inference to default Local mode; benchmark memory and translation quality by direction first.

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


## Continuación offline lingüística — 2026-10-16

- Rama `feat/offline-linguistic-narrative-core`, creada desde `6ebca3e06565456d473a44b1d62e14012531cde8`; `main` no fue modificado.
- Añadido `src/noveltrad/linguistic_analysis.py`: offsets de tokens/oraciones, etiquetas POS heurísticas, detección de alias configurados y chequeo de valores incompatibles solo entre hechos confirmados con procedencia.
- Añadidos `tests/test_linguistic_analysis.py` y `docs/ANALIZADOR_LINGUISTICO_LOCAL.md`.
- Límite explícito: esta es infraestructura determinista, no traducción general, resolución de correferencias ni razonamiento narrativo completo. No extrae canon automáticamente.
- Pendiente de verificación: ejecutar toda la suite, comprobar CI y build/smoke test de Windows en la rama. No integrar si hay fallos.

## Protocolo de dirección, ejecución y continuidad (2026-10-16)

### Roles obligatorios
- **CEREBRO:** define fases, alcance, prioridades y criterios verificables antes de ejecutar; revisa evidencia y decide estado. No declara una tarea terminada por la existencia de archivos, fichas, commits o PR.
- **BOT OBRERO:** inspecciona el repositorio real, trabaja solo en una rama autorizada, implementa, ejecuta pruebas y registra cambios, resultados, errores y bloqueos en GitHub. Nunca declara una prueba pasada sin resultado comprobable.
- **REGISTRO DE CONTINUIDAD:** este BRAIN.md debe permitir retomar el trabajo desde otro chat. Registrar rama, SHA, enlaces, estado, pruebas reales, limitaciones y siguiente acción concreta.

### Estados de trabajo
- PENDIENTE: sin implementación verificada.
- EN CURSO: trabajo iniciado, falta ejecución o comprobación.
- IMPLEMENTADA: existe código, aún sin demostrar todos los criterios.
- VERIFICADA: criterios de aceptación cumplidos y evidencia reproducible disponible.
- INTEGRADA: cambio verificado incorporado en la rama objetivo autorizada.
- BLOQUEADA: impedimento concreto documentado con evidencia y próxima acción.

No confundir CI verde con calidad lingüística, ni build portable exitoso con prueba manual en el PC del usuario. Si una prueba manual o con texto autorizado no se realizó, mantenerla pendiente. No hacer merge en main sin autorización explícita.

### Incidencia de continuidad — PR #16
- PR: https://github.com/jonhararagi/traslate/pull/16
- Rama: feat/offline-linguistic-narrative-core
- SHA inspeccionado: 34a4525b66553f4bcbfab0f6e978a3c3f5b53d07
- Workflow Tests: https://github.com/jonhararagi/traslate/actions/runs/38932299149 — conclusión FAILURE en Ubuntu y Windows, paso «Run tests».
- Workflow Windows Portable Build: https://github.com/jonhararagi/traslate/actions/runs/38932299159 — conclusión FAILURE, paso «Run automated tests».
- Estado correcto: IMPLEMENTADA, NO VERIFICADA; no integrar ni hacer merge.
- Siguiente acción obligatoria: recuperar logs de los jobs fallidos, identificar error raíz, corregir en la misma rama autorizada, volver a ejecutar tests y build, revisar todos los checks sobre el nuevo SHA y actualizar este registro. No inferir causa antes de leer logs.

### Seguimiento de incidencia PR #16 — corrección aplicada, pendiente de CI
- Se inspeccionaron los logs de los tres jobs fallidos (Ubuntu tests, Windows tests y Windows portable build).
- Causa visible en los tests: las expresiones regulares estaban escritas con escapes duplicados, provocando que el punto final se separara como token independiente y que la detección heurística de pronombres no se activara.
- Corrección aplicada en `src/noveltrad/linguistic_analysis.py` en commit `69eaf067379be0035e3cc30baf6e05e358eabbe2`: normalización de escapes de regex y ajuste del nombre canónico para que derive del primer alias configurado, no del alias coincidente.
- Estado actual: CORRECCIÓN APLICADA, VERIFICACIÓN PENDIENTE. GitHub Actions debe completar sobre el nuevo SHA antes de evaluar si el problema quedó resuelto. No declarar la tarea verificada hasta revisar tests Ubuntu/Windows y build portable.



## PR #16 — seguimiento técnico y verificación en curso (2026-10-16; actualización)

Esta sección supersede el estado anterior de la incidencia de PR #16. No declara la fase verificada.

- PR: https://github.com/jonhararagi/traslate/pull/16 (abierto, draft, sin merge).
- Rama autorizada: `feat/offline-linguistic-narrative-core`.
- `main` inspeccionado: `6ebca3e06565456d473a44b1d62e14012531cde8`; no se escribió en `main`.
- Head previo con CI verde: `75c474515d0656a81c04c7896740d680a595cc49`. En ese SHA, Tests #446 pasó en Ubuntu y Windows (https://github.com/jonhararagi/traslate/actions/runs/38933909432) y Windows Portable Build #60 pasó en pruebas, build, smoke test y subida del artefacto (https://github.com/jonhararagi/traslate/actions/runs/38933909046). Artefacto: `NovelTrad-Windows-x64`, ID `12059929086`, 40,742,001 bytes, SHA-256 `7f603a81b7b4689a95dd91f85311d3b3791e5d57d0293c3ee6db210063d5a7c2`, con expiración 2026-10-30. Este artefacto corresponde al SHA anterior, no al código defensivo añadido después.
- Logs de las ejecuciones fallidas originales consultados: Tests Ubuntu y Windows fallaban en `test_token_offsets_round_trip_to_exact_source` porque el punto final quedaba separado y en `test_unknown_name_and_pronouns_are_marked_as_heuristics` porque la advertencia no se activaba. El Windows portable build fallaba en `Run automated tests` por los mismos dos fallos. Evidencia: https://github.com/jonhararagi/traslate/actions/runs/38932299149 y https://github.com/jonhararagi/traslate/actions/runs/38932299159.
- Cambios posteriores al SHA verde: `src/noveltrad/linguistic_analysis.py` valida tipos y valores de `NarrativeFact`, valida el mapping y las entradas de alias, estabiliza la prioridad de alias mediante ordenación explícita y rechaza elementos inválidos en `check_narrative_facts`. `tests/test_linguistic_analysis.py` añade pruebas de alias que solo difieren en mayúsculas/minúsculas y de entradas inválidas.
- SHA de código más reciente inspeccionado antes de esta actualización documental: `11a480e72d311be589ce7a0bb7b5bd52ded47dbf`.
- CI sobre ese SHA estaba en curso al actualizar este registro: Tests push https://github.com/jonhararagi/traslate/actions/runs/38939487116; Tests PR https://github.com/jonhararagi/traslate/actions/runs/38939494289; Windows Portable Build https://github.com/jonhararagi/traslate/actions/runs/38939494381. No registrar esos resultados como pasados hasta que concluyan. La actualización de este archivo producirá un nuevo SHA y requerirá revisar los checks asociados al SHA final.
- Estilo/análisis estático: `pyproject.toml` configura pytest, pero no define una herramienta de lint o type-check independiente. No afirmar que se ejecutó una herramienta que no está configurada.
- Estado por criterios: reparación original de regex — IMPLEMENTADA; tests específicos nuevos — EN CURSO; suite completa en SHA final — EN CURSO; CI Ubuntu/Windows en SHA final — EN CURSO; build y smoke test del paquete en SHA final — EN CURSO; inspección directa del contenido del ZIP del SHA final — PENDIENTE; alcance y limitaciones documentados — IMPLEMENTADA; PR verificado — PENDIENTE.
- Próxima acción obligatoria: esperar las ejecuciones del SHA final de código y del SHA documental más reciente; inspeccionar los resultados completos de Ubuntu, Windows y build portable, confirmar el smoke test y revisar los recursos del artefacto. Si cualquier control falla, leer logs, corregir en esta rama y repetir. Mantener el PR como draft y no fusionar.



## PR #16 — canonicalización determinista de alias no ordenados (2026-10-16)

Esta sección actualiza la incidencia de nombre canónico no determinista y supersede el estado pendiente del mismo seguimiento. Conserva las secciones históricas anteriores.

- PR: https://github.com/jonhararagi/traslate/pull/16 — permanece abierto, draft y sin merge.
- Rama autorizada: `feat/offline-linguistic-narrative-core`.
- SHA inicial comprobado antes de modificar: `56e0d612a255621b14cd326b3f2a52238b482d2d`.
- SHA de `main` comprobado: `6ebca3e06565456d473a44b1d62e14012531cde8`. No se escribió en `main`.
- SHA con corrección, tests, orden de CI y resultados completos de esta ronda: `35202b0b269fd99117d30e764e5a4deeeb3166c4`.
- Este registro se está actualizando después de comprobar ese SHA. El commit documental resultante tendrá un nuevo SHA; deben consultarse nuevamente los workflows para dicho SHA antes de cerrar el PR. Este requisito está separado explícitamente para no atribuir resultados de un commit anterior al nuevo.

### Causa y corrección
- Causa raíz: `analyze_text()` convertía todas las colecciones de alias en tuplas y tomaba `alias_names[0]`. Para `set` y `frozenset`, el primer elemento de iteración no expresa prioridad declarada y puede cambiar con el orden de construcción/disposición interna del conjunto.
- En `src/noveltrad/linguistic_analysis.py`, `list`, `tuple` y otros iterables ordenados conservan el primer alias no vacío declarado. `set` y `frozenset` usan el orden estable explícito `(alias.casefold(), alias)`. Se mantienen validación, offsets, matching de alias y prioridad para los más largos.
- `tests/test_linguistic_analysis.py` conserva la prueba de aliases que solo difieren por mayúsculas/minúsculas y añade un test de construcción sensible al orden para `set` y `frozenset`. El test encuentra valores con orden de iteración inicial distinto entre permutaciones, para demostrar que el canónico no depende de ese orden.
- `docs/ANALIZADOR_LINGUISTICO_LOCAL.md` documenta el contrato.
- `.github/workflows/tests.yml` ahora ejecuta primero `python -m pytest -q tests/test_linguistic_analysis.py` y después `python -m pytest -q`, tanto en Ubuntu como en Windows.

### CI verificado sobre SHA `35202b0b269fd99117d30e764e5a4deeeb3166c4`
- Tests PR: https://github.com/jonhararagi/traslate/actions/runs/38942151241 — éxito en Ubuntu y Windows.
- Tests push: https://github.com/jonhararagi/traslate/actions/runs/38942146498 — éxito en Ubuntu y Windows.
- Ubuntu: tests específicos `9 passed in 0.03s`; suite completa `114 passed, 1 warning in 7.68s`.
- Windows: tests específicos `9 passed in 0.04s`; suite completa `114 passed, 1 warning in 39.23s`. Sintaxis PowerShell validada para los tres scripts de mantenimiento: éxito.
- Windows Portable Build: https://github.com/jonhararagi/traslate/actions/runs/38942151357 — éxito. Instalación de dependencias, suite automatizada, PyInstaller, smoke test y subida del artefacto completados.
- Smoke test comprobó que el ejecutable empaquetado arrancó y `/api/health` devolvió `status=ok` y `mode=local-first`. No equivale a una prueba manual en el PC del usuario ni valida una traducción real.

### Artefacto inspeccionado para el SHA `35202b0b269fd99117d30e764e5a4deeeb3166c4`
- Nombre: `NovelTrad-Windows-x64`.
- ID: `12063423183`; workflow run: `38942151357`.
- Tamaño: `40,741,990` bytes.
- SHA-256 confirmado independientemente con `sha256sum` y coincidente con el digest de GitHub Actions: `0116ffb81d05e8d244aa73f7faecaf2f94c413d20723caac717c72c4131b9426`.
- ZIP descargado y validado: `unzip -t` terminó con “No errors detected in compressed data”. Contiene 183 entradas: `NovelTrad.exe` (7,930,263 bytes), 53 DLL, 32 módulos `.pyd`, `_internal/base_library.zip` y datos empaquetados `_internal/data/benchmarks/academy_villain_context_cases.json` y `_internal/data/novels/i_became_the_academy_villains_daughter.json`, además de módulos y recursos internos de Python/uvicorn/PyMuPDF. El artefacto está disponible hasta `2026-10-30T17:47:02Z`.
- Este artefacto corresponde al SHA indicado arriba; no atribuirlo a un SHA posterior sin comprobar el artefacto de su ejecución.

### Advertencias y límites
- En Ubuntu y Windows: `StarletteDeprecationWarning` — uso de `httpx` con `starlette.testclient`; pytest siguió exitosamente.
- En logs de acciones: avisos de deprecación de Node.js 20 para `actions/checkout@v4`, `actions/setup-python@v5` y `actions/upload-artifact@v4` al ser forzadas a Node.js 24; también `DEP0040` (`punycode`) y `DEP0169` (`url.parse()`). No bloquearon CI.
- `pyproject.toml` no configura un lint ni un type-check independientes; no declarar esas comprobaciones.
- El analizador sigue siendo infraestructura determinista offline, no un traductor completo integrado. No resuelve correferencias generales ni extrae canon automáticamente.

### Estado por criterio para el SHA verificado
- Regla determinista de nombre canónico y compatibilidad con alias ordenados/case-variants: IMPLEMENTADA y VERIFICADA.
- Pruebas específicas antes de suite completa: VERIFICADAS en Ubuntu y Windows.
- Suite completa: VERIFICADA en Ubuntu y Windows.
- Windows Portable Build, smoke test y upload: VERIFICADOS.
- Inspección del ZIP, contenido y digest: VERIFICADA para el SHA indicado.
- Rama `main` intacta, PR abierto y draft: comprobado antes de esta actualización; volver a comprobar después.
- SHA de esta actualización documental y sus workflows: PENDIENTE hasta que terminen las ejecuciones nuevas; no declarar verificada la rama actual usando solamente la evidencia de `35202b0b269fd99117d30e764e5a4deeeb3166c4`.

### Próxima acción concreta
Inspeccionar el nuevo SHA de la rama creado por este registro. Confirmar de nuevo Tests (pasos enfocado y completo en Ubuntu/Windows) y Windows Portable Build; descargar, medir y examinar el artefacto de ese SHA. Mantener el PR en draft y no fusionar ni cerrar.



## Lector NovelTrad — navegación persistente por páginas (2026-10-16)

### Alcance implementado en la rama autorizada

- PR #16: https://github.com/jonhararagi/traslate/pull/16. Rama `feat/offline-linguistic-narrative-core`; mantener abierto, draft y sin merge. Base `main` inspeccionada: `6ebca3e06565456d473a44b1d62e14012531cde8`. No modificar `main`.
- Añadido `src/noveltrad/reader_pages.py`: división determinista de texto original en páginas virtuales de hasta 2400 caracteres nominales, priorizando límites de párrafo, línea y palabra; reensamblado exacto; hash SHA-256 por página; adaptación determinista de traducciones de capítulo preexistentes al número de páginas; conservación del espacio/salto original al final de cada página traducida.
- `src/noveltrad/main.py`: progreso en `books.current_location` ahora incluye capítulo actual, página actual, total de páginas y mapa de última página por capítulo. Se guardan páginas al navegar y al salir con `fetch(..., keepalive: true)`; el usuario vuelve a la última página visitada cuando abre el libro.
- API agregada: `GET /api/chapters/{chapter_id}/reader-pages` y `PUT /api/chapters/{chapter_id}/reader-pages/translations`. Las traducciones por página se guardan en SQLite en `chapter_page_translations`, asociadas al hash del texto original. La escritura valida que no se haya modificado el original ni falte/reordene una página; se sincroniza la traducción completa del capítulo y se conserva el sistema de versiones existente.
- UI agregada: Anterior/Siguiente por página y entre capítulos; indicador de página/capítulo; selector de capítulo; ventana ampliada con zoom; panel de traducción por página. Anterior se deshabilita en el comienzo del libro y Siguiente al final.
- El panel ChatGPT/Gemini hace explícita la limitación del proveedor: genera el prompt, permite copiarlo, abrir el proveedor y pegar/guardar manualmente la respuesta. No envía el texto ni recupera automáticamente la respuesta desde la web. No describir esta modalidad como traducción automática.
- Al guardar traducciones por página, se restablece el sufijo de espacio y saltos de línea del original para evitar palabras o párrafos pegados. Al cambiar texto del original, los hashes antiguos no se usan como si correspondieran a la nueva página; la API rechaza guardar un lote obsoleto.
- Pruebas añadidas/actualizadas: `tests/test_reader_pages.py`, `tests/test_app.py`, `tests/test_frontend.py`. Cubren segmentación repetible, reconstrucción exacta, límites de página, espacios de frontera, persistencia del progreso, persistencia de traducción asociada al hash, rechazo de texto desactualizado y presencia de los controles UI.

### SHA y verificación

- Commits de implementación: `598d1e296f6332d7b5dbda393efb4d7df0d84d47` (segmentación), `24da5159ec8d941ee7b4949676842a3817720189` (tests de segmentación), `d38bbf02d57dcd4d2bb9a04d9754922ec984a869` (API y UI del lector), `33ccf8cc2c1b1c46f988e1c2e5878aa19e2c5739` (tests API), `3bcae8b7440e819a1ac0a151c7b52cb2404d919d` (test UI), `e77d6f17761d87aee82fe2680533275c2e347e43` (preservación de fronteras), `bae175e30213c7b33ee0ff8e1c81ba29a477f26d` y `1cc61951992245ba84394264413d451209266f95` (tests de fronteras), `42eaa839069d638378cb24914c39800dec4e77dd` (página de salida y frontera), `64082aff6823030fa95f023aa6072faacff0c643` (progreso `keepalive` y aviso para traducción sin guardar).
- Primera ejecución de CI en SHA `3bcae8b7440e819a1ac0a151c7b52cb2404d919d` encontró solamente una aserción de test con texto esperado en mayúsculas diferente del aviso real; el job reportó `124 passed, 1 failed` en Ubuntu y Windows. Se corrigió la aserción.
- En el SHA `64082aff6823030fa95f023aa6072faacff0c643`, el workflow push Tests (Ubuntu) completó correctamente; los jobs de Windows, el workflow Tests del PR y Windows Portable Build todavía estaban en curso al escribir este registro. No atribuir esos resultados al SHA documental siguiente.
- **Pendiente obligatorio:** revisar Tests en Ubuntu y Windows y Windows Portable Build en el SHA final que resulte de esta actualización. Si falla un job, leer su log, corregir en esta rama y repetir CI.
- **Pendiente de usuario:** prueba manual en Windows real y prueba visual end-to-end no realizadas. Tampoco se ha probado traducción real de capítulo completo. CI verde no certifica calidad de traducción ni la experiencia en el PC del usuario.


### Continuación tras la primera verificación de CI — restauración de versiones

- Después del registro anterior se endureció el guardado al salir y la protección contra respuestas pegadas sin guardar en `64082aff6823030fa95f023aa6072faacff0c643`.
- Se detectó un caso de consistencia de la nueva paginación: restaurar una versión de capítulo no debe dejar activas las traducciones sobrescritas por página de una versión posterior. La corrección `f5b5709e756d47553b921fcbd433d7e82637b052` elimina esas sobrescrituras al restaurar el capítulo y actualiza la vista paginada al terminar la operación.
- `4012e421bb94e820cf316c354fead583e4a46864` añade prueba de regresión: guardar traducción por página, restaurar la versión anterior del capítulo y comprobar que el lector vuelve a mostrar la versión restaurada y no el override obsoleto.
- El SHA actual de código después de esa corrección era `4012e421bb94e820cf316c354fead583e4a46864`; este documento todavía no contiene el SHA final de la última actualización. Revalidar la suite de Ubuntu/Windows y el paquete Windows sobre el SHA que resulte de esta actualización documental. No cerrar como verificado hasta que todos los jobs estén completos y verdes.


### Dictamen de verificación de navegación — resultados confirmados (2026-10-16)

Este registro resuelve los pendientes de CI anotados arriba para el SHA final de código `0a41105beccca9817a83486c36f0bb1232c25386`:

- Workflow **Tests** del PR: https://github.com/jonhararagi/traslate/actions/runs/38964986145 — éxito. `Tests (ubuntu-latest)` y `Tests (windows-latest)` completados con conclusión `success`, incluida la suite completa.
- Workflow **Windows Portable Build**: https://github.com/jonhararagi/traslate/actions/runs/38964986129 — éxito. Pruebas automatizadas, compilación del portable, smoke test del ejecutable y subida del artefacto completados con conclusión `success`.
- Artefacto generado: `NovelTrad-Windows-x64`, ID `12074402763`, 40,753,642 bytes, no expirado al momento de la comprobación.
- El PR #16 continúa abierto, en estado Draft y sin fusionar. La rama base sigue siendo `main`. SHA de `main` verificado sin cambios: `6ebca3e06565456d473a44b1d62e14012531cde8`.
- La implementación queda **verificada por CI** para tests de Ubuntu/Windows y empaquetado Windows. Esto no equivale a una prueba visual/end-to-end manual en el PC del usuario ni a una validación de calidad lingüística de una traducción real; esos puntos siguen pendientes.
- Este registro es un commit documental adicional. Por disciplina de evidencia, volver a comprobar tests y paquete en el SHA que resulte de este commit antes de tratar dicho SHA documental como final. No modificar `main`, no quitar el estado Draft y no fusionar.

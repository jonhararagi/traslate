# Premium mode through a signed-in Chromium session

## Decision

NovelTrad Premium is intended to use a dedicated Chromium window in which the user signs in to ChatGPT or Gemini with their own account. NovelTrad prepares a translation prompt from the selected source chunk, the novel's style rules, and the approved glossary. The selected provider website performs the translation in that signed-in session.

This replaces the earlier product assumption that Premium means a local Ollama model. The deterministic Local mode remains the low-resource default. Ollama may be retained only as a separately named optional local-model integration, never mislabeled as the account-based Premium mode.

## Safe interaction model

1. The user explicitly selects ChatGPT or Gemini and starts a translation action.
2. NovelTrad splits source text into bounded chunks, preserving paragraph boundaries where possible, and prepares a prompt for each chunk.
3. NovelTrad opens or focuses a dedicated Chromium profile/window for the chosen provider. The user signs in directly on the provider's own website; NovelTrad never asks for or stores account passwords, session cookies, or authentication tokens.
4. The first implementation must use a user-visible handoff: copy the prepared prompt and let the user submit it in the provider UI, then paste/import the returned translation. Do not silently upload book text.
5. If browser automation is later added, it must operate only on the user's visible, authenticated browser session, require explicit opt-in, show the text before submission, and stop for login, CAPTCHA, consent, rate-limit, or unexpected-page states. Never bypass access controls or attempt to conceal automation.
6. Store each returned chunk as a provisional translation in NovelTrad's existing persistent queue. Preserve source text, approved glossary snapshot, prompt version, provider, timestamps, and result. Require human review before applying translations or exporting.
7. Do not claim a provider-specific integration works until it has end-to-end tests. Provider page structure, account features, usage limits, and terms can change; show a clear error and provide manual copy/paste fallback.

## Prompt contract

The program-generated prompt must:
- Translate into Spanish without summarizing, omitting, adding facts, or repeating the source.
- Preserve paragraph and dialogue structure when feasible.
- Apply approved protect, preserve, and translate glossary rules; treat contextual rules as context-sensitive, not mandatory replacements.
- Include the novel-specific style guide and only verified continuity notes that are relevant to the current chunk.
- Separate source text from instructions with clear delimiters and tell the model to treat source text as data, not instructions.
- Include a short preceding-chunk continuity summary when available, not the full novel or an unbounded history.
- Request only the translated passage as output, with no preamble or commentary.
- Never present heuristic warnings as proof of translation correctness.

## Resource and privacy constraints

- Keep Local as the default and use no neural model for deterministic glossary operations.
- Do not download model weights or require Ollama for account-based Premium.
- Keep NovelTrad bound to 127.0.0.1; do not expose the local service to the network.
- Do not silently transmit text. The user must initiate each batch and know which provider receives the text.
- Do not scrape provider content outside the active user-directed translation workflow, access private APIs, or store credentials/cookies in NovelTrad's database.
- Chunk processing must be sequential by default, resumable, bounded, and reviewable. Respect provider limits and stop rather than retrying aggressively after rate limits.

## Acceptance criteria for implementation

- [ ] UI offers Local and Premium (ChatGPT / Gemini) as distinct modes and explains that Premium uses the user's signed-in provider account.
- [ ] Selecting a provider opens/focuses a dedicated Chromium profile and never asks NovelTrad to collect credentials.
- [ ] Prompt generation is deterministic and covered by tests for glossary rules, contextual terms, source delimiters, style instructions, and chunk context.
- [ ] Manual handoff works without browser automation: copy prompt, paste result, validate non-empty output, review, and save as a provisional chunk.
- [ ] Whole-book queue uses sequential bounded chunks, persists progress and failures, resumes after restart, and never overwrites source text.
- [ ] ChatGPT/Gemini selection is explicit for every job; provider errors, sign-in requirements, usage limits, and malformed responses produce actionable messages.
- [ ] No account password, cookie, token, or provider page content beyond the user's requested translation is persisted.
- [ ] Tests cover missing browser/profile, no active login, empty/malformed output, provider unavailable, chunk retry/restart, mandatory review, and original-text immutability.
- [ ] Clean-Windows manual testing and a quality benchmark on a user-authorized excerpt are completed before calling Premium release-ready.

## Status

This document records the intended architecture and acceptance criteria. It does not claim the Chromium integration is implemented. The current main branch still contains an Ollama-backed endpoint under the old Premium label; that code and its UI must be migrated and tested before this decision is considered implemented.

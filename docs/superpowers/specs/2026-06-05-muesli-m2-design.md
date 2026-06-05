# Muesli M2 — Settings, Cloud LLM UI, Markdown Export & Template Editor

> Design spec — 2026-06-05. Approved by Michael during brainstorming.
> Builds on M1 ([2026-06-03-muesli-design.md](2026-06-03-muesli-design.md)), which is complete and merged to `main`.

## Context

M1 shipped the core pipeline: record → transcribe (faster-whisper) → enhance
(Ollama + template) → search, in a pywebview desktop window. M2 turns latent and
stubbed capabilities into real, in-app features:

- a **Settings screen** (Whisper model/device, Ollama model/host, backend toggle);
- an **in-app cloud LLM UI** (enter/switch an OpenAI or Anthropic key, pick a
  model, test the connection);
- **markdown export** (download a meeting's enhanced notes as a `.md` file);
- a **working template editor** (create / edit / delete / duplicate, with a
  prompt preview);
- **formatted markdown rendering** of enhanced notes.

### What the codebase already provides (and what's missing)

Grounding the scope in the *merged* code, not the M1 plan:

- **Settings persistence is unbuilt.** A `settings` table and
  `get_setting`/`set_setting` exist in `storage/db.py`, but nothing uses them.
  `create_app` constructs `Settings()` from hardcoded defaults; there are no
  `/settings` endpoints and no Settings page.
- **The cloud backend is half-wired.** `CloudBackend` only implements OpenAI;
  Anthropic raises `ValueError`. The model is hardcoded `gpt-4o-mini` and the key
  isn't persisted anywhere.
- **The template editor doesn't exist.** `ui/src/pages/Templates.tsx` is a
  read-only list, even though `POST`/`PUT`/`DELETE /templates` already work.
- **Enhanced notes render as raw text** in a `<pre>` block in
  `MeetingDetail.tsx` — not formatted markdown.

M2 is therefore almost entirely **additive**: no schema migration (the `settings`
table already exists), and the existing engine/UI boundary and call-time settings
reads make the runtime wiring cheap.

### Confirmed decisions (from brainstorming)

- **Cloud API key storage:** typed **in the app**, stored in the **OS keyring**
  (Windows Credential Manager) via the `keyring` library — **never** written to
  the DB in plaintext. Non-secret settings persist in the `settings` table.
- **Cloud config UX:** backend toggle (Ollama ↔ Cloud), provider dropdown
  (OpenAI / Anthropic), an **editable** model dropdown (curated current model ids
  per provider), and a **Test connection** button that makes one cheap live call.
  Anthropic is properly wired (it currently throws).
- **Markdown export:** a backend-assembled `.md` containing a **title/date header
  + the enhanced notes**, delivered as a browser download. Backend-assembled so
  the logic is unit-testable and the UI↔engine HTTP boundary stays intact.
- **Template editor:** full **CRUD + duplicate + prompt preview**. Default
  templates are fully editable.
- **Markdown rendering:** the Enhanced tab renders **formatted markdown**
  (`react-markdown`). My Notes / Transcript stay plain text — they aren't markdown.
- **Settings runtime flow:** **persist + mutate the live object.** On startup,
  load the `settings` table over the defaults. `PUT /settings` writes non-secret
  fields to the DB and mutates the in-memory `Settings` object in place; the key
  goes to keyring. Because transcribe/enhance read settings at **call-time**,
  changes take effect on the next action with no rebuild.

**Cost note:** the only feature that can cost money is the optional cloud LLM,
which remains off by default. `keyring` and `react-markdown` are free/open-source.

## Architecture

M2 adds two small engine modules and changes four files; the UI gains a Settings
page and rebuilds the Templates page. The `api`-imports-only-downward rule holds:
nothing in `storage/`, `enhance/`, `config`, `secrets`, or `settings_store`
imports from `api/` or `ui/`.

```
engine/muesli_engine/
  secrets.py            # NEW: keyring wrapper (get/set/delete API key per provider)
  settings_store.py     # NEW: load_settings(db) / save_settings(db, live, partial)
  config.py             # CHANGED: add cloud_model field
  enhance/llm.py        # CHANGED: Anthropic path, configurable model, key from secrets,
                        #          validate_cloud() connection test
  app.py                # CHANGED: seed ctx.settings via load_settings(db)
  api/routes.py         # CHANGED: /settings, /settings/test-cloud, /ollama/models,
                        #          /templates/preview, /meetings/{id}/export
ui/src/
  pages/Settings.tsx    # NEW: settings screen
  pages/Templates.tsx   # REBUILT: CRUD + duplicate + preview
  pages/MeetingDetail.tsx # CHANGED: export button + react-markdown render
  api/client.ts         # CHANGED: settings/template/export/preview methods
  App.tsx               # CHANGED: Settings nav link + route
```

### Components

1. **Secrets wrapper** (`secrets.py`, `keyring`) — isolates all keyring access
   behind `get_api_key(provider)`, `set_api_key(provider, key)`,
   `delete_api_key(provider)` using service name `"muesli"` and username =
   provider (`"openai"` / `"anthropic"`). Isolation lets tests monkeypatch it and
   lets keyring failures surface as one clear error. **Keyring-only** — no silent
   plaintext fallback.

2. **Settings store** (`settings_store.py`) — bridges `storage` + `config`:
   - `load_settings(db) -> Settings`: start from `Settings()` defaults, overlay
     any non-secret values present in the `settings` table, return the merged
     `Settings`. Does **not** touch keyring (the key is fetched at backend-build
     time).
   - `save_settings(db, live_settings, partial) -> Settings`: validate and write
     non-secret fields to the `settings` table, mutate `live_settings` in place,
     return it. **The API key is never written here.**

3. **Cloud backends** (`enhance/llm.py`) —
   - `CloudBackend` gains a working **Anthropic** path (`POST
     https://api.anthropic.com/v1/messages`, headers `x-api-key` +
     `anthropic-version: 2023-06-01`, body `{model, max_tokens, messages}`,
     parse `content[0].text`) alongside the existing OpenAI path, and uses the
     configured `settings.cloud_model`.
   - `get_backend(settings, client=None)`: for the cloud backend, fetch the key
     via `secrets.get_api_key(settings.cloud_provider)` (falling back to an
     injected `settings.cloud_api_key` for tests); raise a clear error if no key
     is set. Build `CloudBackend(provider, key, model=resolved_cloud_model)`.
   - `validate_cloud(provider, key, model) -> (ok: bool, message: str)`: makes one
     cheap `max_tokens=1` call and returns success or a human-readable error
     (e.g. `401 invalid key`). Never raises to the caller.

4. **Export assembly** (in `api/routes.py` or a small helper) —
   `assemble_export_markdown(meeting) -> str`: a title/date header followed by the
   enhanced notes (or an `_(not yet enhanced)_` placeholder if empty). Filename =
   `slug(title)-YYYY-MM-DD.md`. Pure function → unit-tested.

5. **Settings/runtime wiring** (`app.py`) — `create_app` seeds `ctx.settings`
   from `load_settings(db)` instead of a raw `Settings()`. `EngineContext` exposes
   the live settings object that `transcribe_fn` and the enhance closure already
   read at call-time, so a `PUT /settings` mutation is picked up on the next
   action with no rebuild.

## API surface (new / changed)

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/settings` | Returns all non-secret settings **plus** `cloud_key_present: {openai: bool, anthropic: bool}`. **Never returns the key value.** |
| `PUT` | `/settings` | Accepts a partial non-secret settings payload **and** an optional `cloud_api_key` (+ provider). Non-secret fields → DB + live object; key → **keyring** (never DB). Returns the `GET`-style payload. |
| `POST` | `/settings/test-cloud` | Body `{provider, model, key?}` → runs `validate_cloud` (using the supplied key, or the stored one if omitted) → `{ok, message}`. Lets you test before saving. |
| `GET` | `/ollama/models` | Best-effort `ollama.list()` of installed model names for the dropdown; returns `[]` if Ollama is unreachable. |
| `POST` | `/templates/preview` | Body `{prompt, rough_notes?, transcript?}` → returns `{prompt}` built by the engine's `build_prompt` (sample text substituted when fields omitted). |
| `GET` | `/meetings/{id}/export` | Returns assembled markdown, `Content-Type: text/markdown`, `Content-Disposition: attachment; filename="<slug>-<date>.md"`. |

Template CRUD (`GET`/`POST`/`PUT`/`DELETE /templates`) already exists — **Duplicate**
is a client-side create of a copied template (`name + " (copy)"`), no new endpoint.

### `config.Settings` change

Add `cloud_model: str | None = None` (resolved to a provider-appropriate default
when unset). `cloud_api_key` remains **only** as a test-injection seam and is never
persisted. Curated, editable per-provider model lists live in the UI; the exact
default ids are finalized in the implementation plan (they're configurable, so a
stale default is harmless).

## Frontend

- **Settings page** (`/settings`, added to nav) — grouped sections:
  - *Transcription*: Whisper model (static dropdown), device (`auto`/`cuda`/`cpu`).
  - *Enhancement*: backend toggle (Ollama ↔ Cloud).
  - *Ollama*: model dropdown (populated from `/ollama/models`, free-text
    fallback), host.
  - *Cloud*: provider (OpenAI/Anthropic), editable model dropdown, API key field
    (password input, write-only), **Test connection** button + result line, and a
    "key set ✓ / not set" indicator per provider.
  - A single **Save** (`PUT /settings`).
- **Templates page (rebuilt)** — list with per-row **Edit / Duplicate / Delete**,
  a **New template** form (name + prompt textarea), and a **Preview** action that
  shows the assembled prompt returned by `/templates/preview`.
- **MeetingDetail** — an **Export .md** button that downloads
  `/meetings/{id}/export`, and the Enhanced tab rendered with **react-markdown**
  (which escapes raw HTML by default → no injection surface). My Notes / Transcript
  stay plain text.
- **client.ts** — add `getSettings`, `saveSettings`, `testCloud`,
  `listOllamaModels`, `previewTemplate`, `createTemplate`, `updateTemplate`,
  `deleteTemplate`, and an `exportUrl(id)` helper.

## Data flow (settings change)

User edits Settings → **Save** → `PUT /settings` → non-secret fields written to the
`settings` table and mutated on the live `ctx.settings`; an entered key → keyring.
The next **Transcribe** / **Enhance** reads the updated `ctx.settings` at
call-time:

- Whisper's `(model, device, compute_type)` cache key naturally reloads the model
  if it changed.
- `get_backend` selects the active backend and, for cloud, pulls the key from
  keyring and uses `cloud_model`.

No context rebuild, no restart.

## Error handling

- **Cloud enhance with no key** → `422` with a clear message: *"No API key set for
  {provider}; add one in Settings."*
- **Test connection failure** → `{ok: false, message}` (e.g. invalid key / network
  error), never an exception.
- **Keyring unavailable** → `PUT /settings` fails with one explicit *"secure
  storage unavailable"* error (keyring-only by decision; no silent plaintext
  fallback).
- **`/ollama/models` when Ollama is down** → `[]`; the UI falls back to a free-text
  model field.
- **Export before enhancement** → still returns the header with an
  `_(not yet enhanced)_` body placeholder.

## Verification

**Unit (pytest), TDD per M1:**
- `settings_store`: `load_settings` overlays DB values over defaults;
  `save_settings` writes only non-secret fields and mutates the live object; the
  key never lands in the `settings` table.
- `secrets`: get/set/delete roundtrip via a monkeypatched keyring;
  `get_backend` pulls the cloud key from `secrets`.
- `llm`: `CloudBackend` Anthropic request shape + response parse (fake client);
  configured model is used; missing-key raises a clear error;
  `validate_cloud` returns ok / human-readable failure.
- export: `assemble_export_markdown` produces header + enhanced notes; filename
  slug is correct; empty-enhanced placeholder.
- `/templates/preview`: returns the assembled prompt containing the template +
  sample notes/transcript.
- API: `/settings` `GET`/`PUT` roundtrip (key excluded from `GET`,
  `cloud_key_present` reflects a monkeypatched keyring); `/settings/test-cloud`
  with a stubbed validator; `/ollama/models` returns `[]` on failure; export
  endpoint sets the attachment headers.

**Manual (matching M1):** open Settings, switch Whisper/Ollama models and confirm
the next action uses them; enter a cloud key, Test connection (✓), toggle to Cloud,
Enhance a meeting via the cloud model; create/edit/duplicate a template and preview
its prompt; export a meeting and open the `.md`; confirm the Enhanced tab renders
formatted markdown.

## Out of scope (M3+)

Per-meeting backend override; streaming / live enhance; encrypting non-secret
settings; PDF/DOCX export; multi-key management UI; markdown rendering of
transcripts; packaged installer.

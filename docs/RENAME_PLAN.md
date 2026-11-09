# Rename plan: DevChat → 3ie Evidence Assistant

**Status (7 November 2026):** steps 1, 2, 5 and 7 done; step 3 dropped; 4, 6 (domain) and 8–9 open.
**Scope agreed:** everything, including infrastructure

| Step | State |
| ---- | ----- |
| 1. Code on branch `rename/evidence-assistant` | Done, not merged. Tests 51 passed / 2 skipped, no new lint findings, frontend type-check clean |
| 2. GitHub repo rename | Done. `lsempe77/dev_chat` now redirects to `lsempe77/3ie-evidence-assistant` |
| 3. Qdrant alias | **Dropped (7 Nov 2026):** Qdrant is being removed. See [SUPABASE_CONSOLIDATION_PLAN.md](SUPABASE_CONSOLIDATION_PLAN.md) |
| 4. New R2 bucket | On hold until the consolidation plan's Phase 6 decision (R2 → Supabase Storage) |
| 5. New Modal app | Done (7 Nov 2026): `evidence-assistant-mineru` deployed; old `devchat-mineru` still deployed until decommission |
| 6. Railway | Variables point at the new Supabase project. Service domain `3iechat.up.railway.app` unchanged (not user-facing) |
| 7. Vercel and Supabase auth | Done (7 Nov 2026): `3ie-evidence-assistant.vercel.app`; old address redirects (308); Supabase auth URLs set |
| 8. Decommission | Not started |
| 9. Local folder | Not started |

Step 1 left `docker-compose.yml` unchanged (local-only service, container and network names), because the
file is outside the editing permissions used for this work.

This plan renames the product, the repository, the code and the cloud resources. Each step lists how to undo
it. Steps that touch production run in the order below, so the live app keeps working at every point.

---

## 1. Names

| Kind | Old | New |
| ---- | --- | --- |
| Display name | DevChat | 3ie Evidence Assistant |
| GitHub repo | `lsempe77/dev_chat` | `lsempe77/3ie-evidence-assistant` |
| Python package (`pyproject.toml`) | `devchat-v2-sota` | `evidence-assistant` |
| Node root package (`package.json`) | `dev-chat-root` | `evidence-assistant-root` |
| Python identifiers | `DevChatAgent`, `devchat_agent.py`, `DevChatResponse`, `DevChatAgentFactory` | `EvidenceAssistantAgent`, `evidence_assistant_agent.py`, `EvidenceAssistantResponse`, `EvidenceAssistantAgentFactory` |
| R2 bucket | `devchat-pdfs` | `3ie-evidence-assistant` |
| Modal app | `devchat-mineru` | `evidence-assistant-mineru` |
| Modal web endpoint | `lsempe77--devchat-mineru-trigger-processing.modal.run` | `lsempe77--evidence-assistant-mineru-trigger-processing.modal.run` |
| Qdrant main collection | `devchat_v2_contextual` (code default) or `devchat_v2_enhanced` (Modal) | alias `evidence_assistant` pointing at the live collection |
| Qdrant MonkeyOCR collection | `devchat_monkeyocr` | `evidence_assistant_monkeyocr` (or drop, see Roadmap) |
| Railway service URL | `3iechat.up.railway.app` | new service domain, for example `3ie-evidence-assistant.up.railway.app` |
| Vercel URL | `dev-chat-frontend.vercel.app` | `3ie-evidence-assistant.vercel.app` (if free) |
| Health check service name | `devchat-api` | `evidence-assistant-api` |
| Browser storage key | `devchat_admin_session` | `evidence_assistant_admin_session` (admins sign in once more) |
| Export file prefix | `devchat_export_` | `evidence_assistant_export_` |
| Local folder | `Gen AI tools/apps/devchat` | `Gen AI tools/apps/evidence-assistant` (last, optional) |

Python names cannot start with a digit, so code identifiers drop the `3ie` prefix.

---

## 2. Defects found while mapping the names

Fix these during step 3, because the rename touches the same lines:

- `R2_BUCKET_NAME` falls back to `"devchat-pdfs"` in about 25 places, but to `"devchat-docs"` in
  `api/routes/rags.py:3232`. Replace every fallback with one setting in `src/config/settings.py`.
- The default Qdrant collection is `devchat_v2_contextual` in `src/config/settings.py:80` and
  `devchat_v2_enhanced` in `infrastructure/modal_lib/config.py:21`. Confirm which one production uses
  (`QDRANT_COLLECTION_NAME` in the Railway and Modal environments) before creating the alias.
- The Modal endpoint URL is hard-coded in `api/routes/dependencies.py:385`, and the Railway URL is a fallback in
  `infrastructure/modal_lib/processing.py:173` and `:863`. Move both to environment variables.
- The admin UI hard-codes the bucket name as display text (`SettingsTab.tsx`, `AdminContext.tsx`,
  `RagSettingsTab.tsx`). Read it from the status API instead.

---

## 3. Steps

Each step lists **do**, **check** and **undo**. Stop at any failed check.

### Step 1. Prepare the code on a branch (no production effect)

- **Do:** on branch `rename/evidence-assistant`, make every infrastructure name come from settings or the
  environment (section 2), then rename display strings, docs, package names and Python identifiers. Keep the
  *values* of infrastructure names unchanged for now.
- **Check:** `ruff check .`, `pytest`, `npm run build` in `frontend/`. Grep for `devchat`/`DevChat` and confirm
  only infrastructure values and history files (CHANGELOG, archive) remain.
- **Undo:** delete the branch.

### Step 2. Rename the GitHub repository

- **Do:** `gh repo rename 3ie-evidence-assistant -R lsempe77/dev_chat`, then
  `git remote set-url origin https://github.com/lsempe77/3ie-evidence-assistant.git`.
- **Check:** GitHub redirects the old URL. Vercel and Railway Git integrations still trigger a deploy on push.
- **Undo:** rename back. Redirects from the old name stop working if a new repo takes the old name.

### Step 3. Qdrant alias (zero-copy)

- **Do:** create alias `evidence_assistant` → the live collection. Set `QDRANT_COLLECTION_NAME=evidence_assistant`
  in Railway and in the Modal secret.
- **Check:** a chat query returns the same sources as before. Indexing a test PDF writes to the aliased collection.
- **Undo:** set the variable back to the old collection name. Delete the alias.

### Step 4. New R2 bucket

R2 buckets cannot be renamed.

- **Do:** create bucket `3ie-evidence-assistant`. Copy every object from `devchat-pdfs` (for example
  `rclone copy` with R2 remotes, or the Cloudflare dashboard's object migration). Pause uploads during the copy.
- **Check:** object counts and total sizes match per prefix (`input-pdfs/`, `outputs/`, `rags/`).
- **Cost:** R2 charges no egress. Copying writes one Class A operation per object, which costs cents at this volume.
- **Undo:** keep using the old bucket. The old bucket stays untouched until step 8.

### Step 5. New Modal app

- **Do:** activate profile `lsempe77`, set `app = modal.App("evidence-assistant-mineru")`, point the R2 secret at
  the new bucket, `python -m modal deploy infrastructure/modal_mineru.py`. Set the new endpoint URL in Railway.
- **Check:** process one PDF end to end through the new app.
- **Undo:** point Railway back at the old endpoint. The old app keeps running until step 8.

### Step 6. Railway

- **Do:** rename the service, add the new service domain, set `R2_BUCKET_NAME=3ie-evidence-assistant`, and add the
  new Vercel origin to the CORS allow list. Keep the old domain attached.
- **Check:** `/health` on the new domain returns `evidence-assistant-api`.
- **Undo:** revert the variables. The old domain still works.

### Step 7. Vercel and Supabase auth

- **Do:** rename the Vercel project, add the new domain, point the API base URL variable at the new Railway domain.
  In Supabase Auth, set the new Site URL and add the new domain to the redirect allow list, **keeping the old
  entries**.
- **Check:** sign in, upload, chat and the admin panel all work on the new domain. Sign-in still works on the old one.
- **Undo:** revert the variables and auth URLs.

### Step 8. Decommission (needs explicit approval per item)

After two weeks without errors on the new names:

- Redirect `dev-chat-frontend.vercel.app` to the new domain.
- Remove the old Railway domain and the old Modal app.
- Delete the old R2 bucket **only** after a final count comparison and with the owner's written go-ahead.
- Remove the old Supabase redirect entries.

### Step 9. Local folder (optional)

Renaming `apps/devchat` breaks references outside this repo: the workbench `CLAUDE.md`, `pipelines/TVET/MEMORY.md`,
editor workspaces and agent memory paths. Do it last, in one sitting, and update those references at the same time.

---

## 4. Not renamed

- Git history, `CHANGELOG.md` entries and files under `archive/` keep the old name as historical record.
- The Langfuse project can keep its name. Rename it in the Langfuse UI if wanted, since traces are keyed by API key.

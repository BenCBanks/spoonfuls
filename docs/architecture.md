# Architecture

How Spoonfuls is built and the rules that keep people's recipe collections safe. Read before any data, import,
sharing or privacy change. Changes to these rules need the lead's approval in the issue first.

## Stack

| Part | Choice | Why |
|---|---|---|
| Server | Python 3.12, FastAPI, uvicorn, psycopg 3 (pool) | Small, fast, well understood; proven in a sibling app |
| Database | PostgreSQL 17 with row-level security (RLS) | Privacy enforced in the database, not just in code; full-text + trigram search built in |
| Phone/web app | Plain JavaScript ES modules in `app/static/`, no build step | Fast to load, nothing to compile, easy to review |
| iPhone app | Capacitor shell around `app/static/` + a native **Share extension** | The share sheet is the fastest way to save from Safari, TikTok and Instagram |
| Public pages | Server-rendered HTML for `/@handle`, cookbooks and recipes | Fast, crawlable link previews; readable without an account or JavaScript |
| Packaging | One Docker image + `docker-compose.yml` (app + Postgres) | Same shape for the beta server and later cloud hosting |

## Layout (target)

| Path | What | Lane |
|---|---|---|
| `app/main.py`, `app/db.py`, `app/auth.py` | Wiring, migrations, sessions/accounts | `spoon-core` |
| `app/api_recipes.py`, `app/api_cookbooks.py`, `app/importer/`, `app/search.py` | Recipes, cookbooks, imports, search | `spoon-recipes` |
| `app/api_social.py`, `app/api_public.py`, `app/publish.py` | Profiles, follows, Following tab, sharing, family membership, public pages | `spoon-social` |
| `app/api_plan.py`, `app/groceries.py`, `app/nutrition.py` | Meal plan, grocery list, nutrition | `spoon-plan` |
| `app/static/` | `app.js` shell/router (`spoon-core`); `recipes.js`, `cook.js`, `social.js`, `plan.js` per lane; `style.css` sections per lane | per file |
| `mobile/` | Capacitor iOS app and Share extension | `spoon-ios` |
| `site/` | Marketing website | `spoon-site` |
| `dev/` | Fictional demo data, tests, screenshots | per area |

## Data model (first version)

All personal tables carry `user_id` (owner) or are reached through a cookbook membership. IDs are UUIDs, so share links
can't be guessed or counted.

- `users`, `sessions`, `profiles` (`handle` unique, case-insensitive; `visibility` public | private).
- `recipes`: `owner_id`, `kind` (original | saved | link), `title`, `summary`, `yield_text`, `servings`, `prep/cook/total_minutes`,
  `ingredients` (JSON list of sections → lines: `raw` text + parsed `qty`, `unit`, `item`, `note`), `steps` (JSON sections → text),
  `tags`, `source_url`, `source_name`, `source_author`, `forked_from` (recipe id), `nutrition` (JSON with a `source`), `cover_media_id`,
  `deleted_at` (30-day trash), `updated_at`, `version`.
- `recipe_revisions`: a full snapshot on every saved edit (who, when, what). Restore = save an old snapshot as a new version.
- `recipe_notes`, `cooked_log` (date, rating, note, photo), `favourites`.
- `cookbooks` (`owner_id`, title, cover, description, `visibility` private | unlisted | public, `slug`), `cookbook_recipes` (ordering),
  `cookbook_members` (`role` owner | editor | viewer), `invites` (single-use, expiring, revocable).
- `follows` (`follower_id`, `followee_id`, `status` active | requested), `blocks`, `reports`.
- `publications`: the **public representation** of a recipe or cookbook (see Public pages).
- `imports`: one row per save attempt (source, state, reason, draft JSON, AI usage). `media` (owner, kind, sizes, visibility).
- `meal_plan_entries`, `grocery_items` (aisle, checked, source recipe/entry, merged quantity).
- `ai_usage` (per user per month) and a global monthly budget setting.

## Privacy and permission rules

1. Every endpoint resolves `current_user` and reads/writes only rows that user owns or reaches through a membership.
   No endpoint takes a user ID from the client to decide access.
2. Every personal table has RLS enabled. Owner tables use an `own_rows` policy; cookbook-shared tables use a policy that
   checks `cookbook_members`. Tests create two or three fictional accounts plus a revoked member and try every object
   route as each one.
3. **Private by default.** New recipes and cookbooks are private. Making something public is an explicit action with a preview.
4. **Public readers never see the private record.** They get a `publications` row: a deliberate, minimal copy that excludes
   private notes, cooking history, meal plans, grocery lists, account details and unpublished photos. Unpublishing deletes it.
5. Private notes and cooking history are never shared, even inside family cookbooks, unless the user marks a note as shared.
6. Blocks apply everywhere: profile, cookbooks, Following tab, search and follow requests.
7. Sign-out clears local drafts and caches on that device after confirming nothing is unsynced.

## Saving and importing

Every save creates an `imports` row first, so nothing is lost even if the app closes or the network drops. The Share
extension writes the shared URL/text/image into the app group and the app sends it on the next launch.

| Source | How | Cost | Result |
|---|---|---|---|
| Recipe website | Safe fetch (public HTTPS only, size/time/redirect limits, no private addresses) → schema.org `Recipe` JSON-LD → microdata fallback | Free | Imported or Partly imported, reviewed before saving |
| Social post (TikTok, Instagram, YouTube, Pinterest) | Official oEmbed/OpenGraph metadata only (title, author, thumbnail, caption where provided). If the caption links to a recipe site, import that. If the caption contains a recipe, AI structures it into a draft | AI only when needed | Imported (AI draft) or Saved as a link |
| Screenshot, photo of a card or cookbook page | AI vision reads it into a draft | AI | Imported (AI draft) for review |
| Pasted text | Ingredient/step splitting; AI only if the user asks | Free / AI | Draft for review |
| Another cook's public recipe | Copy into your version with `forked_from` and attribution | Free | Saved |

Rules:
- We **never** scrape logged-in pages, bypass platform restrictions or download platform videos. Social saves keep the
  link and show the platform's own preview. What a public recipe page may show from an imported recipe is decided by
  research issue (copyright/terms) before public launch; until then imported recipes cannot be published, only originals.
- AI output is always a draft the user reviews. Never a silent save. Fields AI was unsure of are marked.
- AI is capped: a per-user monthly allowance and a global monthly budget, checked server-side before any call. When the
  cap is reached the app says so and saves as a link instead. The provider and model are configured on the server, not in code.
- Reused building blocks: Kinetta's `recipe_fetch.py` (protected fetch) and `recipe_schema.py` (JSON-LD reader), and the
  household cookbook's ingredient-line parser, grocery merging and cooking-view behaviour (ported to this stack).

## Reliability

- Autosaved drafts (on device and server) for every editor; a failed save keeps the draft and shows Retry.
- Optimistic UI only where it can be rolled back; a pending-writes queue survives app restarts.
- Version history on recipes; 30-day trash for recipes and cookbooks; export everything as JSON plus printable HTML.
- Nightly verified database + media backups; restore tested before the beta opens to anyone outside the family.
- Error budget: crash-free sessions ≥ 99.8%; every import failure has a reason code, and failure rates are tracked per source.

## Media

Beta: photos stored on the server in a dedicated volume, served through authenticated routes, resized server-side
(thumbnail / card / full). Public launch: move to S3-compatible object storage with signed URLs; public media follows its
publication's visibility and is removed when it is unpublished.

## Accounts

Email + password (argon2) with invite-only sign-up during the beta. Before public launch: email verification, account recovery,
Sign in with Apple, rate limits and an admin/moderation page separate from the app.

## Testing

Unit tests for parsers and permissions; API tests with multiple fictional accounts; Playwright UI tests at 390 px in light and
dark mode; an import fixture corpus of saved (fictional or permissively licensed) pages so imports are tested offline. CI runs
on every ready pull request.

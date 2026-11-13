# Working on Spoonfuls: instructions for AI coding agents (Claude Code, Codex and others)

Spoonfuls is a mobile-first recipe app: save recipes from anywhere, organise them into cookbooks, cook from them, and
share them with family and the cooks you follow. The maintainer, Ben Banks, isn't a developer: write PR descriptions and
summaries in plain language, say what you tested and what you didn't, and explain any choice he has to make.

Read before you start: `docs/product.md` (what and why), `docs/architecture.md` (how, and the privacy rules),
`docs/design.md` (every UI change), `docs/roadmap.md` (order of work).

## This repository is public
Everything committed here is published. Never commit personal data, real people's names or recipes, server or house
details (addresses, IPs, hostnames), secrets or keys, or test output. Use only fictional demo data in `dev/demo/`.
Recipe fixtures for import tests must be written by us or permissively licensed; never commit copied blog pages.
`HOUSE.md`, `.env`, `data/`, `uploads/` and `backups/` are git-ignored on purpose.

## How work gets to users
- Work on a branch in your own worktree and open a pull request. Never push to `main`.
- Open PRs as **drafts** while iterating; mark ready once for the full test run. Wait for green CI before merge.
- The live server is updated separately by the lead. Cloud/code-only agents must not access it.
- About 400 changed lines per PR. Batch small fixes in one area.

## Pull request descriptions
The concrete problem, exactly what users will experience, before/after examples, checks run and their results, and
anything unverified (for example "not tested on a physical iPhone"). UI PRs attach screenshots of every state at 390 px,
light and dark, with fictional data.

## Rules that keep people's data safe
- Every endpoint uses `current_user` and reads or writes only rows that user owns or reaches through a cookbook membership.
  Never decide access from an ID the client sends.
- Every new table holding personal data gets row-level security and a policy (copy an existing example in `app/db.py`).
- Public pages read only from `publications`, never from private records.
- New things are private by default. Imports and AI output are drafts until the user saves them.
- External fetches go through the protected fetcher only (public HTTPS, size/time/redirect limits, no private addresses).
- Never scrape logged-in pages, bypass platform restrictions or download platform videos.

## Conventions
- Database changes: append a new numbered SQL string to the end of `MIGRATIONS` in `app/db.py`. Never edit a shipped migration.
  A new migration always needs the `spoon-core` lane.
- Plain JavaScript, no build step. Short functions; comments explain *why*; plain-language UI text.
- Colours, fonts and spacing come from `docs/design-tokens.json` only, in both light and dark mode.
- Dependencies must allow use in a commercial, closed product (MIT, BSD, Apache-2.0, ISC, MPL-2.0, or LGPL used
  unchanged as a separate package). Never GPL or AGPL. Add each to `THIRD_PARTY.md`.

## Working in parallel
Several builders work at once, each in their own worktree, branch and throwaway test server. Stay inside the lanes you
were assigned (see `docs/architecture.md` → Layout). Before opening a PR, rebase on `main`; if `main` gained a migration,
renumber yours to come after it. Keep CSS changes in your area's section of `style.css`.

## Run and test
Commands are added with the M0 skeleton. Until then there is nothing to run.

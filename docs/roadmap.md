# Roadmap

Milestones run in order; work inside a milestone can run in parallel across lanes. Each milestone ends with something
the family beta can actually use. GitHub issues carry the detailed specs; this file is the overview.

## M0: Foundation
- App skeleton: FastAPI + Postgres + static app shell + Docker Compose + health check + CI (tests on every ready PR).
- Accounts: invite-only sign-up, sign-in, sessions, password rules, security headers.
- Design tokens and app shell (four tabs, light/dark), after the owner picks a direction from mockups.
- Recipe import library: protected fetch + JSON-LD reader + ingredient-line parser, with an offline fixture corpus.
- Beta hosting: its own containers, database, backups and private address; nothing shared with any other app.

**Done when:** two fictional accounts can sign in on a phone, and imports pass the fixture corpus in CI.

## M1: My cookbook
- Recipe model with revisions and trash; write and edit a recipe; photos.
- Save from a website link with review-before-save and honest import states.
- Library: search, cookbooks, favourites, tags, sort. Recipe page with scaling. Cooking view with timers.
- Cooked-it log and private notes. Export everything (JSON + printable).
- Bring recipes over from the household cookbook's export.

**Done when:** the family uses it instead of their current app for two weeks without losing anything.

## M2: Save from anywhere
- iPhone app (Capacitor) on TestFlight with a Share extension: links, text and images.
- Social links saved with source card and caption; caption links followed to recipe sites.
- AI drafts from captions, screenshots and handwritten cards, with per-user and global monthly caps.

**Done when:** saving from Safari, TikTok and Instagram takes two taps and every result is one of the three honest states.

## M3: Share and cook together
- Handles and profiles; public and unlisted cookbook pages that work without an account; share links with good previews.
- Family cookbooks: invites, owner/editor/viewer, revocation, change history.
- Save someone else's recipe as your version, with attribution.
- One-way follows, follow requests for private profiles, the Following tab, saves count. Block and report.

**Done when:** a grandparent can open a shared family cookbook from a text message and a cousin can add to it.

## M4: Plan and shop
- Weekly meal plan; grocery list built from planned recipes with scaled, merged quantities and aisles.
- Nutrition per serving when the source provides it (source always shown).

## M5: Public launch readiness
- Email verification, account recovery, Sign in with Apple, rate limits, moderation tools, terms and privacy policy.
- Cloud hosting and object storage; restore drills; monitoring.
- Import from other apps (Paprika, RecipeSage, Mela). Onboarding.
- Plus subscription (App Store in-app purchase), with the free plan unchanged.
- Final brand, App Store listing, website.

## Research that gates decisions
- Copyright and platform terms for imports and public sharing (gates publishing imported recipes, M3).
- Competitor review mining: what users love and hate in current recipe apps (informs M1–M2 priorities).
- Brand: name, domain and trademark availability (gates M5).

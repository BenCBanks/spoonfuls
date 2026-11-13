# Product brief

Owner: Ben Banks (maintainer). Written November 2026 at the start of the project. The newest owner decision wins; record
decisions in the dated log at the bottom.

## The problem

People find recipes on TikTok, Instagram, Pinterest, food blogs, in screenshots, on handwritten cards and in messages.
Saving them is fragmented, finding them later is frustrating, and organising them takes effort. Existing apps cover
parts of this, but many have complicated interfaces, intrusive advertising, unreliable importing and crashes.

**Our opportunity is not the most features. It is the best experience for saving, organising, cooking and sharing recipes.**

## Who it is for

| Person | What they want | What wins them |
|---|---|---|
| **The collector** (primary) | Saves recipes everywhere and can never find them | One-tap saving from any app, good search, nothing lost |
| **The home cook** | Cooks the same 30 dishes and a few new ones each week | Their own versions and notes, cooking view, meal plan, grocery list |
| **The family keeper** | Wants Grandma's recipes in one shared place | Family cookbooks that several people can add to, without needing an account just to read them |
| **The sharer** | Friends always ask "send me that recipe" | A good-looking profile and cookbook link, follows without pressure |

We do **not** design for professional food creators first. They are welcome, but nothing in the app should
require posting, followers or engagement to be useful.

## Principles (every design and architecture decision is checked against these)

1. **Personal cookbook first, social second.** Home is your own collection. Social discovery is a separate tab, never the landing page.
2. **Effortless saving.** Saving is the most-optimised action in the app: share sheet → done in two taps.
3. **Honest importing.** Every import ends in one of three visible states: *Imported* (you review it), *Partly imported*
   (missing fields are marked) or *Saved as a link* (with the reason). Never a silent failure, never a half-blank recipe.
4. **Reliability is the feature.** No lost recipes, no unsaved edits, no data held hostage. Autosaved drafts, version
   history, a 30-day trash, full export at any time.
5. **Beautiful and calm.** Food photography, clear type and familiar patterns. Dense where it helps, quiet everywhere.
6. **Private by default, sharing is deliberate.** Recipes and cookbooks are private until you share them. Saved
   recipes from other sites are yours to use, not ours to republish.
7. **No ads, no dark patterns.** No engagement bait, no streaks, no notification spam, no paywall in the middle of cooking.
8. **AI is optional and specific.** It turns a caption, screenshot or card into a draft you check. It never invents a recipe
   silently or posts for you.

## The core objects

- **Recipe**: one of three kinds: *original* (you wrote it), *saved* (imported from a website or another cook, with
  attribution), or *link* (a post we could not turn into a recipe; source card and caption kept, fill in later).
- **Your version**: saving someone else's public recipe gives you your own copy, linked to the original. Your changes,
  notes and cooking history are yours; the original author's later edits never overwrite them.
- **Cookbook**: a named collection with a cover. A recipe can be in several cookbooks. Private, unlisted (anyone with
  the link) or public. Family cookbooks have members: owner, editor, viewer.
- **Profile**: `@handle`, name, photo, short bio and public cookbooks. Works as a shareable web page without an account.
- **Follow**: one-way, like Instagram. You can follow a cook without them following you back. Private profiles approve followers.
- **Cooked it**: a private log entry (date, optional note and photo, optional rating). Can optionally be shared.
- **Meal plan / grocery list**: planned recipes by day, and a list built from them with scaled, merged ingredients.

## Feature scope

Feature depth comparable to RecipeSage, with the social sharing of Spillt, and the polish of a modern consumer app.

| Area | Family beta (M1–M4) | Public launch (M5) | Later |
|---|---|---|---|
| Saving | Website import with review, manual entry, iPhone Share extension, social links with caption, AI from caption/screenshot/card | Import from other apps (Paprika, RecipeSage, Mela exports) | Browser extension, Android share |
| Library | Search (title, ingredient, tag, notes), cookbooks, favourites, tags, sort | Smart filters (time, what I have) | Duplicate detection across imports |
| Cooking | Recipe page, scaling, unit display, cooking view, timers, notes, cooked-it log | Nutrition where available | Voice step control |
| Sharing | Profiles, public/unlisted cookbooks, share links that work without an account, family cookbooks | Follows and a Following tab, saves count | Comments, collections from others, creator tools |
| Planning | Weekly meal plan, grocery list with aisles | Reminders | Pantry |
| Trust | Version history, trash, export | Account recovery, reporting, blocking, moderation | Custom domains for cookbooks |

## Monetisation direction

Freemium, never ads. The free plan stays genuinely complete: unlimited recipes, website imports, cookbooks, sharing,
following and cooking. A paid plan (working name *Plus*) covers features that cost us money to run or that power users
value: AI imports beyond a monthly free allowance, advanced meal planning, nutrition, larger family cookbooks. Paywalls
never appear in the middle of cooking or block access to a user's own recipes or exports. Pricing is decided before the public launch.

## How we measure success

Weekly active cooks; recipes saved per active cook; import success rate (Imported vs Partly vs Link) per source;
time from Share tap to saved; recipes cooked per week; 30-day retention; crash-free sessions (target ≥ 99.8%).

## Decision log

- **13 Nov 2026**: New product and team, separate from both the private household cookbook and Kinetta; reuse proven
  import, ingredient-parsing, cooking-view and planner logic from the household cookbook. iPhone app + web first, Android later.
  Public repository. Family beta first, then friends, then the public. One-way follows and a quiet Following tab.
  Freemium, no ads. Paid AI allowed for hard imports, with a capped budget. Same technology as Kinetta.

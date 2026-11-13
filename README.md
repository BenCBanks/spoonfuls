# Spoonfuls

**Your recipes, finally in one place.** Save a recipe from anywhere, keep your own version of it, cook from it, and share
your cookbook with the people you cook for.

> Working name. The final brand is still being chosen. Status: **early development**. Nothing here is ready to install yet.

## What it is

Recipes end up scattered across food blogs, TikTok, Instagram, Pinterest, screenshots, handwritten cards and group
chats. Spoonfuls is a mobile-first cookbook that pulls them together:

- **Save from anywhere.** Share a link from Safari or another app, and a website recipe is imported and laid out for you to check.
  A social post is saved with its source and caption. A photo of a handwritten card can be turned into a draft you review.
- **Your cookbook first.** Your own recipes, organised into cookbooks, searchable, with your notes, changes and cooking history.
- **Cook from it.** A clean recipe page, ingredient scaling and a step-by-step cooking view that keeps your screen awake.
- **Share it naturally.** A profile that works as a shareable digital cookbook, shared family cookbooks, and following the
  cooks you trust. No need to become a content creator.
- **Plan and shop.** A weekly meal plan and a grocery list built from your recipes.
- **No ads.** Never.

## Principles

1. Personal cookbook first, social second.
2. Saving a recipe is the easiest thing in the app.
3. Nothing is ever lost: imports explain themselves, edits save, history is kept, and your data can be exported.
4. Beautiful, calm and familiar. Food first, not an admin dashboard.
5. Sharing is deliberate. Everything is private until you choose to share it.

See [docs/product.md](docs/product.md) for the full product brief, [docs/design.md](docs/design.md) for design rules,
[docs/architecture.md](docs/architecture.md) for how it is built and [docs/roadmap.md](docs/roadmap.md) for the plan.

## Technology

Python 3.12 / FastAPI, PostgreSQL with row-level security, a plain-JavaScript phone web app with no build step, and a
Capacitor iPhone app with a Share extension.

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use requires a separate
license from the maintainer.

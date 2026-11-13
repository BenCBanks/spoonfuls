# Design guide

The one place for Spoonfuls design decisions. The owner's newest decision wins, then this file. When the owner makes a
standing design call, add it here with a date. Brand colours and fonts below are **provisional** until the owner picks
from mockups (milestone M0).

## The feel

A well-loved cookbook, not a dashboard. Food photography leads; type is warm and readable; the interface steps back.
Calm, compact and familiar: someone should understand any screen in two seconds.

## Standing rules (from the owner's taste, proven in a sibling app)

1. **Compact, slick, intuitive.** Choose the denser, quieter layout. Back and the title share one row; action footers stay on one row.
2. **No heavy chrome.** No grey pill fills, boxed sections, tab containers, circles around selected tabs or dashed placeholder boxes.
   A selected tab is bold text plus a 2 px underline.
3. **No explainer rows.** If a screen needs a hint line, redesign the action instead. An empty-state line is fine only when a list is empty.
4. **Colour means something.** The accent marks the primary action and active state. Never decoration. No red for "bad".
5. **One obvious action, few taps.** The primary action sits where the eye starts, near the content. Every row in a list uses
   the same trailing action. Edit lives on the detail page, long-press or swipe, not as a second icon on every row.
6. **Familiar patterns** (iOS, Instagram, Apple Notes, Paprika). Pickers apply on tap (rows + ✓, no Save button). Sheets close on choice.
7. **44 px touch targets**, 16 px minimum input text (no iPhone zoom), no sideways page scrolling, both safe areas respected.
8. **Text wraps, never clips.** No ellipsis on recipe titles, ingredient lines or names in lists that matter.
9. **No pressure.** No streaks, badges, counts of followers on home, "you haven't cooked in a while" nudges or guilt wording.
10. **Not everyone does everything.** Meal planning, nutrition and social only appear prominently for people who use them.
11. **Accessibility minimum:** VoiceOver labels, 4.5:1 contrast for text and primary actions, an automated accessibility check in CI.

## Social rules

- Home is **your cookbook**, always. The Following tab is a separate destination, not the landing page.
- The Following tab shows only what people deliberately shared (a published recipe, a cookbook update, a shared Cooked it), newest first. No algorithmic ranking in v1.
- The main public signal is **saves** ("Saved by 12"). No like counts, no follower counts on cards. Follower numbers live only on a profile.
- Following is one tap and needs no reason. Unfollow and block are always one menu away.
- Anything public (profile, cookbook page, share preview image) respects visibility; check the server response and the image, not only the screen.

## Navigation (proposal; owner preview required)

Four tabs, a fixed full-width bottom bar with icons and labels: **Cookbook** · **Following** · **Plan** · **List**.
Your profile and settings open from your avatar at the top-left of Cookbook. **Save** (＋) sits top-right of Cookbook and opens:
Paste a link · Take a photo · Choose a screenshot · Write a recipe. On iPhone the Share extension is the main way to save.
Hide the tab bar while the keyboard is open and during cooking view.

## Key screens

- **Cookbook (home):** search field first, then a row of cookbook covers, then recently saved and recently cooked recipes as
  photo cards. Import states show inline ("Saving…", "Needs a look", "Saved as link") on the card itself, not in a separate inbox.
- **Recipe:** full-width photo, serif title, source line ("from Smitten Kitchen · your version"), times and servings on one line,
  a servings stepper, Ingredients then Method, notes at the end. A **Cook** button fixed at the bottom.
- **Cooking view:** one step at a time, large text, swipe or tap to move, ingredients for this step, named timers, screen kept awake.
- **Import review:** looks like the recipe page in edit mode, with uncertain fields marked; Save at the bottom; nothing is saved until you tap it.
- **Profile / public cookbook page:** cover, name, handle, short bio, cookbooks as covers, then recipes. Reads well without an account.

## Visual system (provisional)

Single source of truth: `docs/design-tokens.json` → generated CSS. Edit the JSON, never a second palette.

| Token | Light | Dark |
|---|---|---|
| Background | warm paper `#FBF8F3` | `#151311` |
| Surface | `#FFFFFF` | `#1E1B18` |
| Text | ink `#1F1B16` | `#F3EEE7` |
| Secondary text | `#6B6258` | `#A89F94` |
| Accent (primary action, active) | paprika `#B8432A` | `#E0775C` |
| Divider | `#E9E2D8` | `#2C2824` |

- **Type:** a warm serif for recipe and page titles (Fraunces or Source Serif 4, open licence, bundled); the native system sans for
  controls, body and numbers (tabular figures). Page titles 28–32 px, sections 17–20 px, body 15–16 px, secondary 13–14 px (never below 12).
- **Spacing:** 4, 8, 12, 16, 24, 32, 48 px. Phone side margins 16–20 px. Radii: 12 px controls, 16 px photos and cards.
- **Photos:** 4:3 on cards and 3:2 on the recipe page, covering the frame. A recipe without a photo gets a calm typographic cover, never a grey box.
- **Icons:** one line-icon set, 20–24 px, inside 44 px targets.

## Review process

New interaction patterns or visible features: the lead writes the spec in the issue first (layout at 390 px, every state:
empty, loading, error, mine, others, private, public), the builder implements it. Draft PRs include screenshots of every state
at 390 px in light and dark with fictional data. The owner previews 2 screenshots of any new interaction pattern before merge.

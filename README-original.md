# Signalas — Narrative Observatory

Editable Lithuanian narrative-monitoring UI prototype exported from the existing Site.

## Start here

Open this `naratyvu-observatorija` folder as your local project in Codex or in your IDE with the Codex extension. With Codex CLI installed, start `codex` from this folder. Read `AGENTS.md` for the agreed product requirements.

Suggested first message:

> Read README.md and AGENTS.md, inspect the existing prototype, and help me continue development while preserving the current UI and fixed topic catalog.

## Preview

This is a static app with no dependencies or build step. Open `dist/index.html` in a browser, or serve it locally with Python 3:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

On Windows, if Python uses the `py` launcher:

```powershell
py -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Then visit http://127.0.0.1:8000/.

## Files

- `dist/index.html`: page shell and help dialog.
- `dist/styles.css`: responsive styles.
- `dist/app.js`: fixed topic catalog, demo narratives, views, filters, sorting and interactions.
- `AGENTS.md`: product constraints and coding guidance for continued work.
- `.openai/hosting.json`: identity and static-output configuration of the existing Site.

## Current behavior

- Three linked views: topic overview, narrative relationship map, and timeline.
- 18 fixed broad topics, with 8 marked as monitoring priorities.
- 21 narrative examples, including 11 user-supplied definitions.
- Narrative lists sort by most posts, fewest posts, newest or oldest first appearance.
- Counts use the selected period. Sorting persists when changing topic or period.
- Map above the ranked narrative accordion. Rows show support, opposition and quotation percentages; expanding a row reveals posts, relations and history.
- No community segmentation. Context tags appear in narrative details and search, with the selected tag shown as an active filter.

All post counts, timestamps, representative posts and relationship examples are demonstration data. There is no live social feed, AI integration, database or backend in this export. The original conversation is summarized in `AGENTS.md`; its full transcript is not included.

## Check changes

With Node.js installed:

```sh
node --check dist/app.js
```

In a browser, check topic and priority filters, tag search, all four sorting modes, period selection, narrative expansion, relation links and timeline selection. Verify a narrow viewport as well as desktop.

## Hosting

Existing private Site: https://naratyvu-observatorija.co-relevant-8077.chatgpt.site

This is a source snapshot. Editing or previewing this folder does not update that hosted Site automatically. Publishing to it requires the Sites tools and access to the same Site. Preserve its project ID and audience when continuing that deployment.

The package contains no Git history or repository credentials. You can initialize your own Git repository for continued development.

## Snapshot

Source commit: 225b3712d5744888abf09f58ed10ce088c31cef4
Export date: 2026-10-20

Official Codex guidance: https://learn.chatgpt.com/docs/projects and https://learn.chatgpt.com/docs/codex/cli

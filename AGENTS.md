# Project guidance

## Real data and platform-wide acquisition (2026-10-21)

The user explicitly replaced demo views with real data and requires the whole authorized training pod, independent of contacts/tags/personal feeds. live_data.py projects actual snapshots and validated content/context-bound AI proposals; never fall back to demo data after a live-mode error. The 15-topic catalog remains fixed. Empty narrative lists and unknown thermometer assessments are valid; do not fabricate counts/relations.

Read docs/COLLECTION.md. The current account supplies a paginated /stream.json plus its own profile stream; /admins/dashboard redirects to /stream and /local_public.json returns 404. collect-sample reads every account-visible feed/profile page without a total post cap; it is still not the whole pod. Whole-pod collect requires an administrator-supplied export; server/signalas_export.rb is a prepared Rails/PostgreSQL READ ONLY export, not executed against this remote server. Do not claim the full pod is connected. admin_export.py accepts every in-scope author independent of incomplete membership, preserves old parents as context for period comments, and verifies declared counts. Missing membership disables audience percentages, never content acquisition.

The selected period end date lives separately in var/dashboard-period.json; duration is preserved in browser storage. Never derive the user's period from latest posts/export/collection dates. Date controls may return an empty interval. No automatic paid analysis, public media proxy or permission bypass. Backend data is private under var/, never dist/. Keep coverage visible and distinguish verified client behavior from unexecuted administrator-side SQL.

## Explicit live-integration pilot (2026-10-21)

The user has now authorized OpenAI API implementation, a small paid live test, and authenticated read-only Diaspora collection. This supersedes earlier no-live-service restrictions only for these explicit pilot commands. integration_config.py reads server-side .env/environment settings; never print secrets or return settings/cookies to browser clients. configure_secrets.py provides terminal entry and a one-use loopback password form with Host/path/CSRF token checks and no secret logging.

diaspora_client.py reads all pages of the authenticated account stream and its own profile stream, expands post JSON and own comments/media, and extracts sourceUrl only from source HTML canonical/og:url metadata. Do not describe this bounded visible sample as the entire platform or assign old test content to future exercises. Membership and exercise ID remain unknown. integrations.py collects/imports explicitly and runs bounded OpenAI text pilots; no scheduler, automatic spending or changes to demo dashboards. openai_analysis.py preserves fixed topics, new-candidate proposals, names/source references and review for missing context/unread media. CLI context is supplied explicitly; do not invent it from browser localStorage. Real image/audio/video analysis is not connected. Keep tests/test_integrations.py and credential-redaction tests passing.

## Goal and implementation

Continue the existing Lithuanian-language Signalas narrative-monitoring web prototype. Preserve the established design and interactions unless the user requests changes. This is plain HTML, CSS and JavaScript under `dist/`; there is no build step. Keep dependencies and framework changes proportional to the requested work.

## Fixed broad topics

The administrator controls the catalog in `dist/app.js`. It has 15 topics in the user-approved order and 8 priorities. Changes explicitly requested by the user are authorized; automated classification must not change the catalog. Do not allow AI to create, rename, merge or remove broad topics. AI is intended to detect, enrich and classify narratives under existing topics. Unclear assignments belong in the unassigned-narratives queue; they are not proposals for new broad topics.

Keep the broad topics general. The user-approved catalog of 2026-10-20 combines sport with culture/history, everyday life with crises, and energy with environment/climate. Education includes science; technology has a separate category. Rights and law enforcement are combined. Retained topic IDs stay stable; retired IDs are justice (merged into rights), sports (culture), and leisure (emergencies). The Temų pulsas list follows catalog order rather than post counts. Energy narratives N-001 and N-002 belong to environment, and crisis-preparedness narrative N-006 belongs to emergencies. Locations such as Klaipėda and organization names are changeable context tags rather than permanent broad topics. Preserve existing topic and narrative IDs.

## Approved interface

- Keep the three linked views: overview, relationship map and timeline.
- Show broad-topic labels beside narratives. The separate overview insights block Kas keičiasi has been removed at the user’s request.
- Put the relationship map at the top and the ranked narrative accordion below it.
- Each collapsed row shows post count and support, opposition and quotation percentages for the selected period.
- Expanding a narrative reveals representative posts, relations and definition history inline.
- Support four sorting modes: most posts, fewest posts, newest and oldest first appearance. Counts use the selected period; dates use `firstSeenAt`. Keep the chosen sort across topic and period changes.
- Do not display a global strip of all context tags. Keep tags in expanded narrative metadata and search. Display only a selected tag as an active filter.
- Do not add community segmentation at this stage; the source data cannot distinguish communities reliably.

## Data and interpretation

The current dataset is demonstrative. Keep the 11 supplied narrative definitions and original examples identifiable, and label synthetic posts, metrics and relations as demonstrations. A claim being in the registry (`Registre`) means its narrative definition is registered; it does not verify the claim as true.

A topic priority is a monitoring choice, not proof of hostile activity. Mentions do not imply support. Narrative relationships describe content and do not establish common authorship or coordination. Keep stance analysis at post or aggregate level rather than attributing political profiles to private individuals. A location or organization tag indicates content mentioned, not the source of an influence operation.

Do not silently add a live feed, AI service, personal-data collection or backend. Implement these when the user defines and requests them.

## Verification

Run `node --check dist/app.js` for JavaScript changes. Check affected interactions in a browser, including responsive layout. Preserve selection and expanded-row behavior when changing sorting or views. Keep counts, percentages, dates and accessible controls coherent. If browser verification is unavailable, state that limitation.

## Deployment

`.openai/hosting.json` identifies the existing private Site. Preserve its identity and access policy when publishing to the same Site with the Sites tools. Local edits are not automatically synchronized to the hosted Site.

## Local Python development (2026-10-20)

The user requested a local version with Python as the foundation for future collection and processing. `app.py` now serves `dist/` on loopback and supports offline JSON/CSV ingestion into SQLite. This authorization does not define any live sources or AI provider. Read README.md for the import schema and limits.

Imported posts and original UI demonstration metrics are intentionally separate until a real-data view is implemented. Keep demonstration labeling accurate. Unassigned posts are not automatically new narrative candidates. Preserve IDs and align `data/catalog.json` with `dist/app.js` when an administrator changes the catalog. Run `python3 -m unittest discover -s tests -v` for backend changes and the JavaScript checks above for frontend changes. The local copy has no `.openai/hosting.json`; the deployment paragraph above describes the original export only.

## Content-direction thermometer

The user requested a fourth demo view, Nuotaikų termometras. Keep the approved 15-topic catalog (the pasted specification's 18-topic reference was stale). Read docs/THERMOMETER.md. Thermometer labels are independent of narrative stance, author roles and sentiment. Only the shared period filter applies to its entire synthetic content stream. Unassessed units are excluded from category denominators and displayed in coverage. Never present authored demo labels as model inference or participant psychology. Preserve separate acquisition, classification and statistics in Python. Do not add live collection, an AI provider or administration screens under the demo request. The user asked to stop interactive browser control; honor that preference until changed.

## Fixed initial exercise context (latest user requirement)

The user requested Pratybų kontekstas with two main text fields: Pradinė situacija and Patvirtinti scenarijaus faktai, now extended by the user-requested optional Pavadinimų atitikmenys table. Save once at exercise start in localStorage via dist/exercise-context.js. Saved fields are read-only. Do not add editing, events, version history, actor roles, sides, intentions or exercise-management controls. This supersedes prior recommendations to maintain evolving user exercise-context versions; historical synthetic thermometer fixture metadata is only the basis of authored demo labels, not the active user context.

Both narrative and thermometer integration entry points call SignalExerciseContext.analysisInput. Keep the same initial context separate from related posts/media and earlier comments. Unconfirmed later posts never become scenario facts. Unexpected events are not automatically false or destabilizing. Necessary missing facts require review with a reason. Initial context does not restrict the content stream or discovery of new narratives under the existing 15 topics. UI must distinguish prepared integration from executed analysis; custom context must not appear to reclassify authored demos. Check with node tests/test_exercise_context.cjs and JavaScript syntax checks. Continue honoring the request to stop interactive browser control.

## Collapsed thermometer content

Keep content messages collapsed by default behind the button Termometro turinys. Opening it shows all period units with category labels and filters for all three directions plus unassessed units. A category in the summary may explicitly open its filtered content. Each fresh mount starts collapsed. Preserve category explanations and the shared period scope.

## Significant narrative growth

The user removed Kas keičiasi; retain a single full-width topic overview followed by the existing narrative table. Add growth badges in the overview table and map accordion list only. Growth logic lives in dist/growth.js; the single source of trial thresholds is dist/metrics-context.json. Latest thresholds: previous count > 0, absolute increase >= max(3, ceil(1% of actual assigned exercise audience)), and percent increase >= 50; all criteria must hold. Missing, zero or mismatched exercise audience disables the badge; count-growth percentages do not need audience and are not people engagement shares. Do not fabricate a demo membership count. A unit is one separately published post/comment. Use actual adjacent equal-duration count windows, not stored percentages. For zero/missing prior counts show no percent or badge. All comparisons are synthetic demonstrations. Preserve candidate labels, all four sort options, selected/expanded narrative state and filters. Badge must be a separate accessible button; hover/focus/click explains counts and demo status without toggling the accordion. The user explicitly requested desktop/narrow browser QA for this change, permitting that bounded verification despite the earlier general request to stop browser control.

## Optional name mappings

Within Pratybų kontekstas, keep two mapping data columns: Tikras pavadinimas and Pavadinimas pratybose. Rows can be added/removed only before saving. The existing save stores optional nameMappings [{id, realName, exerciseName}] along with the two text fields in the same localStorage record; all are read-only thereafter. Missing nameMappings in a legacy context means an empty array, without rewriting or losing the existing saved fields. Ignore blank rows. Block incomplete/duplicate/conflicting pairs with row-specific messages, preserving typed values and never resolving conflicts automatically. Compare names case-insensitively with Unicode/whitespace normalization for validation, preserving the entered display names. IDs stay stable across edits, removals of other rows, save and reload.

Mappings are only additional analysis context. Both analysis input builders must pass the same mapping array and preserve original content text/source_reference; resulting names must remain the exercise names. Mapping an entity never determines content category, affiliation or intent. Do not restrict discovery to mapped names or existing narratives. Keep the integration clearly marked as prepared-only while AI remains disconnected. No separate administration, import, training or history features.

## Audience-aware metrics audit

Read docs/METRICS.md. Never assume 200–300 members, use active-only counts or global pod registration totals as exercise membership. metrics.py provides prepared calculations, not a connected collector: complete assigned account IDs including inactive accounts, exercise ID, historical snapshot validity, content author, visibility recipient IDs, and complete interaction actor/action IDs are required. Exclude the post author for other-member engagement. Union account sets across actions and posts, never add per-post uniques. Raw action counts stay absolute; optional content units per 100 members can exceed 100. Stance and thermometer fractions use assessed content, not membership. The user subsequently requested Platformos apžvalga and its author ranking; follow the latest section below. The median helper now includes every selected-period original post, including those without interactions. Preserve original content links. No credentials in project files or static bundles. Use the current missing-audience API response until an authoritative exercise roster and visibility feed exist.

## Platform overview and original links (latest user request)

The user explicitly requested the new Platformos apžvalga view. Keep three peer categories (up to 3 posts each): most comments including replies, most likes, most reshares. Desktop has 3 columns, narrow screens stack them. The user's image is only visual guidance; do not copy role labels or use them in ranking. This section uses the entire platform stream regardless of narrative assignment; only the existing period filter applies. Preserve narrative filters and expanded selection when returning to those views. Keep original text, author, Lithuania time, available media and genuine source links. Long text and each author's posts expand with native accessible details controls.

Python platform_overview.py owns selection/ranking and AUTHOR_POLICY. The whole section selects posts by publication period and uses lifetime counters and interactions, clearly disclosed in Lithuanian. Missing is not zero. Author median includes ALL original period posts, including unengaged posts; excludes comments and simple reshares. Other-member engagement deduplicates account IDs and excludes author from numerator and visible assigned exercise audience. At least 3 active originals plus positive median qualify; score = median percent * log2(1 + active originals). Centralize trial criteria; score is not audience percent. Missing interactions or membership makes an author ineligible with a clear insufficiency notice. The demo has a separate explicitly synthetic roster, never reuse it for actual exercise metrics or growth badges.

Use content.py and dist/source-content.js for sourceUrl / parentSourceUrl. Never guess a post/comment URL from an ID or substitute a platform homepage. Preserve supplied originals across SQLite, adapters and analysis inputs. All source-content renderers use the shared link helper; comments with only a parent URL say Atverti pirminį įrašą. All links open with target=_blank and rel=noopener noreferrer. Demo units have no genuine originals; disclose this instead of generating URLs. Existing narrative evidence arrays are supported through an adapter; new source content uses structured objects. No new live collector, credential persistence or AI is authorized by this demo extension. Check Python tests, all tests/*.cjs and JS syntax. Bounded background QA of this requested responsive section may verify layout/interactions without editing saved exercise context.

## Original-photo thumbnails (latest user request)

Use the shared media schema: kind, thumbnailUrl, originalUrl, alt. content.py normalizes it, platform_overview.py maps Diaspora own photos[].sizes, and SQLite preserves media JSON. Use only source-provided paths/URLs; never derive them from IDs. An explicit source_base_url may resolve a supplied relative media path. Do not create a public photo cache/proxy or bypass source authorization. The actual feed is still disconnected; demonstration SVGs are explicitly illustrations without fake original links.

SignalSourceContent.thumbnail/body is the single renderer for platform cards, author expansions, narrative evidence and thermometer own attachments / discussion context. Show first image at 96x72 (80x60 narrow) plus +N for the rest, lazy-loaded with alt text. A thumbnail anchor opens sourceUrl in a new tab, or the known parent URL for a comment if its own link is absent; keep the separate original-link action. Capture thumbnail clicks before accordion handlers without preventing the native link default action. Remove the entire thumbnail on image error; leave text and original links, and reserve no slot for absent images. Do not inherit parent/root media for comments/reshares. Keep video behavior, assessment attachments, labels and all ranking/statistics formulas unchanged. Run tests/test_thumbnails.cjs plus existing regressions and bounded background browser QA, including narrow view, failures and click/keyboard behavior. Never edit saved exercise context for QA.

## Hourly account collection (2026-10-21)

The user explicitly requested no total post limit and hourly refresh. `python3 integrations.py collect-sample` has no --limit, deduplicates feed/profile GUIDs, includes the signed-in author, and expands all returned comments. A 15-row server page is not a collection cap. max_time pagination overlaps the boundary second; an unpageable full second fails rather than skipping posts. Failed collection preserves the last published snapshot; JSON writes use atomic 0600 replacements and a collector lock prevents overlap.

Codex heartbeat `kas-valand-atnaujinti-signalo-duomenis` runs this command hourly, without AI analysis, code edits, period changes or secret output. It requires the local computer and Codex app to be running and network permission. Do not add a duplicate scheduler. The browser checks the local snapshot every minute/on focus and applies new data without changing filters or interrupting the context form. Account-scope totals and selected-period counts are distinct.

## Shared period options (2026-10-21)

The shared filter now has 10, 7, 3, 1 calendar-day windows in that order. periods.py owns backend validation and MAX_PERIOD; live bootstrap covers all 10 days, and frontend indexing uses each actual days array length. Preserve saved duration and end date when adding options. All views, original-post ranking, narrative totals/stances and thermometer content use the same interval. Lifetime counters retain their disclosed meaning. Demo 10-day narrative counts reuse already-authored preceding history; do not invent a missing prior 10-day comparison.

## Private real-photo delivery (2026-10-21)

The user reported missing actual thumbnails. The pod returns valid WEBP bytes as text/plain + nosniff, even with authorization. content.py upgrades HTTP media only on the explicitly configured HTTPS pod, retaining exact supplied paths; never upgrade arbitrary hosts or accept embedded credentials. DiasporaClient.image reads only same-origin HTTPS raster bytes with the existing session and checks signatures, rejecting HTML/SVG.

private_media.py is a private loopback delivery adapter, not a public media proxy. GET /api/media/image requires active live mode, the exact loopback Host and the per-process X-Signalas-CSRF header. Accept only source/record ID/own media index from the current private snapshot, never a caller-provided URL, parent-media inheritance, or cross-origin cookie forwarding. Keep the bounded cache/session in process memory only, clear on snapshot/config changes, and never write images into dist/ or expose authentication in URLs. Keep no-store and same-origin resource policy. Source-content uses the same lazy thumbnail component in all views, tries this protected fetch on image error, and releases transient blob URLs. Preserve source links, click isolation and all metrics. Tests cover MIME correction, HTML rejection, host/header denial, unknown records/indices/origins, parent-media isolation, original-image fallback and shared UI behavior.

## Compact platform heading (2026-10-21)

At the user’s explicit request remove the long paragraph below the platform scope/date tags (publication-date and lifetime-counter explanation, account-scope prose, total/period counts, popularity caveat). Keep the scope badge and selected date range visible. Do not recreate the paragraph or add a replacement explanatory block. Calculation semantics remain documented in README and unchanged.

## Do not duplicate the unassigned source stream (2026-10-21)

The user removed the raw-content block Turinys be naratyvo from narrative views. Do not append it to the overview, map or timeline, including their empty states. Preserve the Platformos apžvalga content list, source acquisition, narrative-assigned evidence and the thermometer. This is separate from the existing Nepriskirti naratyvai queue for narratives lacking a broad topic; do not remove that queue.

## Calendar range, without recollection (2026-10-21)

The user replaced fixed 10/7/3/1 windows and the separate end date with one compact calendar range control in live mode. Save both start_date/end_date in var/dashboard-period.json; include both Lithuania calendar days using half-open timestamps (DST-aware). Migrate the legacy browser duration/end choice once without shifting it. All live views and CSV use the same selected range; cache keys include both dates, not just duration. The demo fixture duration API remains for offline compatibility. Filtering reads the existing private snapshot only: never collect Diaspora, run AI, change context or derive dates from available content. The separate authorized hourly collection remains unchanged. Empty intervals are valid.

## Compact monitoring indicator (2026-10-21)

The user removed the sidebar explanatory subline and the entire real-data information card. Retain only the compact stream-status indicator: green Stebimas srautas; orange Srauto stebėjimas sustabdytas. monitoring.py stores collection/OpenAI outcomes separately with allowlisted reasons, never raw errors, keys or content. The browser polls the local status endpoint only; no new paid, balance or source API calls. Detect source failures, local/offline failures and snapshots older than 90 min (hourly plus 30 min grace). Recognize provider quota codes only from actual failed API requests, distinguish rate limits, and do not clear a quota error after a source refresh or models-list success. Keep the last good content and all user filters/context. The narrow sidebar retains an accessible dot. Do not restore the removed card via live-data.decorate.

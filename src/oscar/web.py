"""Minimal built-in settings UI; served without external CD/DVD privileges."""
from fastapi.responses import HTMLResponse

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSCAR · Go!</title>
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/brand/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/brand/apple-touch-icon.png">
<style>
:root{color-scheme:dark}body{font-family:system-ui,-apple-system,sans-serif;background:#10151d;color:#eef2f6;max-width:1160px;margin:20px auto;padding:0 20px}
h1{letter-spacing:.14em}p,small{color:#a9b6c4}section{background:#19222e;border:1px solid #324253;border-radius:14px;padding:20px;margin:16px 0}
.drive{border-top:1px solid #324253;padding:16px 0;display:grid;gap:8px}
label{display:block;margin:8px 0}[hidden]{display:none!important}input,select{background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px;font:inherit}
input[type=number]{width:120px}button{background:#bfd5ff;color:#091b35;border:0;border-radius:9px;padding:11px 18px;cursor:pointer;font-weight:700}
.note{padding:12px;background:#283342;border-radius:9px}#status{min-height:1.5em}
.oscar-brand{margin:0 0 16px;max-width:100%;min-width:0}
.oscar-brand-image{display:block;width:100%;max-width:1160px;height:auto;object-fit:contain;object-position:left center}
.oscar-brand-fallback h1{margin:0}.oscar-brand-fallback p{margin:6px 0 0}
@media(max-width:750px){.oscar-brand{margin-bottom:12px}}
.oscar-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 16px;border-bottom:1px solid #324253;padding-bottom:12px}
.oscar-tab{background:#19222e;color:#e5efff;border:1px solid #415269;border-radius:10px;padding:11px 17px}
.oscar-tab[aria-selected="true"]{background:#bfd5ff;color:#091b35}
.oscar-tab:focus-visible{outline:3px solid #8fc2ff;outline-offset:3px}
.oscar-panel[hidden]{display:none!important}
.oscar-panel h2{margin-top:0}
.go-drive-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:14px;margin-top:16px}
.go-drive-card{border:1px solid #42556b;border-radius:13px;background:#121c28;padding:16px;min-width:0}
.go-drive-card h3{margin:0 0 8px}.go-drive-card small{display:block;overflow-wrap:anywhere;margin:6px 0}
.go-drive-card button{width:100%;margin:8px 0 0}
.go-drive-controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}
.go-drive-controls button{margin:0}
.go-drive-card button:disabled{opacity:.5;cursor:not-allowed}
.go-drive-diagnostic{margin-top:12px;border-top:1px solid #42556b;padding-top:8px}
.go-drive-diagnostic summary{cursor:pointer;font-size:.85rem}
.go-drive-diagnostic input{max-width:100%;box-sizing:border-box;width:100%}
.go-drive-diagnostic p{font-size:.82rem}
.go-drive-card .drive-ready{color:#9ce4b3}.go-drive-card .drive-busy{color:#f1d393}
.go-rip-progress{margin:12px 0 6px}
.go-rip-progress label{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:.84rem;color:#d1def2}
.go-rip-progress progress{display:block;width:100%;height:14px;margin:7px 0 5px;accent-color:#94bfff}
.go-rip-progress small{color:#b7c6d8}
.go-rip-progress .go-progress-unknown{font-size:.82rem;color:#b7c6d8}

.go-workflow-row{border:1px solid #3c4b60;border-radius:10px;padding:11px;margin:10px 0;background:#131c29;overflow-wrap:anywhere}
.go-workflow-row button{padding:7px 12px;margin:6px 8px 0 0}
.go-job-toolbar{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin:12px 0}
.go-job-toolbar label{margin:0}.go-job-toolbar select{margin-left:6px}
.go-workflow-row{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.go-job-title{font-weight:700}.go-job-details{display:grid;gap:3px;min-width:0;flex:1 1 300px}
.go-job-details small{display:block;overflow-wrap:anywhere}.go-job-state{color:#d2dff2;font-size:.85rem}
#go-job-summary{color:#c5d6e9;margin:10px 0}
.oscar-advanced{border:1px solid #344559;border-radius:12px;padding:12px;margin:14px 0}
.oscar-advanced>summary{cursor:pointer;font-weight:650;padding:8px}
.oscar-advanced section{margin:12px 0}
@media(max-width:750px){.go-drive-grid{grid-template-columns:1fr}.oscar-tab{flex:1 1 40%}}

/* OSCAR responsive review surfaces */
.oscar-review-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.oscar-review-card{background:#121c28;border:1px solid #37475a;border-radius:12px;padding:12px;min-width:0;overflow-wrap:anywhere}
.oscar-review-card p{margin:5px 0}.oscar-review-card strong{color:#d8e8ff}
.oscar-review-card summary{cursor:pointer}.oscar-review-card pre{max-height:380px;overflow:auto;white-space:pre-wrap}
.oscar-review-cover{max-width:220px;width:100%;height:auto;border-radius:8px}
.oscar-review-note{border-left:3px solid #bfd5ff;padding:8px 12px;background:#142338;overflow-wrap:anywhere}
.oscar-review-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
.oscar-mobile-cards{display:none}
#review-output,#multi-output,#v2-output,#metadata-output,#inspect-result,#verify-output{overflow-wrap:anywhere}
@media(max-width:750px){
 body{margin:10px auto;padding:0 10px}
 section{padding:12px;margin:10px 0}
 h1{font-size:1.55rem}
 input,select,textarea{box-sizing:border-box;max-width:100%}
 button{max-width:100%;white-space:normal;text-align:center}
 #v2-output table,#metadata-output table,#inspect-result table,#verify-output table{display:none}
 .oscar-mobile-cards{display:grid;grid-template-columns:minmax(0,1fr);gap:9px;margin:12px 0}
 .oscar-mobile-cards .oscar-review-card{padding:12px}
 .oscar-mobile-cards dt{font-size:.77rem;color:#a9b6c4;margin-top:8px}
 .oscar-mobile-cards dd{margin:1px 0 5px;overflow-wrap:anywhere}
 .oscar-review-cover{max-width:180px}
}
</style></head><body>
<header class="oscar-brand" aria-label="OSCAR — Open Source CD Archiving and Ripping">
<img class="oscar-brand-image" src="/brand/OSCAR-header.png" alt="OSCAR — Open Source CD Archiving &amp; Ripping. Preserve every note." onerror="this.hidden=true;document.getElementById('oscar-brand-fallback').hidden=false">
<div class="oscar-brand-fallback" id="oscar-brand-fallback" hidden><h1>OSCAR</h1><p>Open Source CD Archiving &amp; Ripping</p></div>
</header>
<div class="note">Verified CD archiving · Original ripping files are preserved. Release inference is not proof of the physical pressing. Keep OSCAR on a trusted network or behind authentication.</div>
<nav id="oscar-tabs" class="oscar-tabs" role="tablist" aria-label="OSCAR sections"></nav>
<div id="oscar-panels"></div>
<section><h2>Ripping profile</h2>
<label for="profile">Default profile</label><select id="profile"><option value="archival">Archival / collectors</option><option value="classical">Classical / works &amp; performers</option></select>
<p>Profile selection is stored for future processing. Neither profile starts a rip.</p></section>
<section><h2>Release identification &amp; automation policy</h2>
<p>Choose the identification policy used by newly started Go! jobs. Saved policy is snapshotted per job. Semi Automatic requires release and archive approval; Best Guess automatic publication requires a separate container opt-in; Secure requires physical edition review.</p>
<label for="identification-mode">Identification mode</label>
<select id="identification-mode">
<option value="secure">Secure — evidence-first (default)</option>
<option value="semi_automatic">Semi Secure — Semi Automatic (release approval required)</option>
<option value="best_guess">Best Guess — inferred candidate (archive auto-publish requires opt-in)</option>
</select>
<div id="best-guess-note" class="oscar-review-note" hidden>Best Guess deliberately accepts the risk of choosing the wrong physical pressing. It will label release identification as inferred, never physically verified. If no credible candidate exists, it must preserve the verified rip for review. Automatic archive publishing requires OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH=1, one candidate and zero metadata warnings.</div>
<div id="semi-automatic-note" class="oscar-review-note" hidden>Semi Automatic rips and verifies, then lets you explicitly accept a proposed MusicBrainz release, or defer the verified rip. Accepting an inferred candidate does not physically verify your CD. A verified tagged staging copy can be prepared by Go; final archive publication still needs explicit approval.</div>
<div id="secure-review-options">
<label for="secure-review-level">Secure Mode: level of human review</label>
<select id="secure-review-level">
<option value="on_ambiguity">Review on ambiguity — require physical evidence when uncertain</option>
<option value="before_archive">Review before archive — approve final edition and archive preview</option>
<option value="every_step">Full Manual — explicitly review each workflow transition</option>
</select>
</div>
<p>These settings cannot bypass verification, physical-edition uncertainty or publication safeguards. Opt-in archive environment flags are configured in your Portainer stack.</p>
</section>
<section><h2>Language &amp; names</h2><label for="name-display">Show names</label><select id="name-display"><option value="original_and_english">Original + English (when available)</option><option value="original">Original only</option><option value="english">English preferred (original preserved)</option></select><label for="alias-fallback">When no English alias exists</label><select id="alias-fallback"><option value="original">Use original</option><option value="sort_name">Allow artist sort-name as transliteration (not a translation)</option></select><p>English aliases are fetched on demand from MusicBrainz. Original names and entity IDs are always retained. These settings do not tag audio files.</p></section>
<section><h2>Optical drives</h2><div id="drives"></div><button id="probe" type="button">Check inserted discs</button><p id="media-status" aria-live="polite"></p><div id="toc-results"></div></section>
<section><h2>Collection Library (local)</h2>
<p>Import existing published OSCAR archive manifests into a separate local SQLite catalog. Original FLACs, CUEs and manifests remain untouched. Local records are not Discogs collection entries.</p>
<button type="button" id="collection-import">Import published archive records</button>
<details class="oscar-advanced"><summary>Legacy Collection label enrichment (advanced)</summary>
<p>This older action fills missing label fields in the local Collection only, without approving or changing archived FLAC tags. Archive-wide metadata review is now preferred. Keep this tool for historical catalogs until archive migrations are supported.</p>
<button type="button" id="collection-enrich-labels">Fill missing labels from exact MusicBrainz release (Collection only)</button>
</details>
<button type="button" id="collection-refresh">Refresh collection</button>
<button type="button" id="collection-sync-approved-labels">Synchronize applied labels (Collection only)</button>
<p>Synchronize previously approved album labels after a completed archive revision, including multiple labels such as Daylight; Epic. Actual archived FLACs are independently checked first. Locally curated values stay unchanged.</p>
<label for="collection-search">Find in collection</label>
<input id="collection-search" placeholder="Artist, album, genre, label, composer, conductor or soloist" maxlength="150" style="width:350px;max-width:90%">
<label for="collection-section">Library</label>
<select id="collection-section"><option value="">All libraries</option><option value="Classical">Classical</option><option value="Popular">Pop / Rock / Dance &amp; other popular</option><option value="Unclassified">Unclassified</option></select>
<label for="collection-sort">Sort collection</label>
<select id="collection-sort">
<option value="artist">Artist</option><option value="title">Album title</option>
<option value="year">Year</option><option value="catalog_number">Catalog number</option>
<option value="archive_status">Archive status</option><option value="label">Label</option><option value="composer">Composer</option><option value="conductor">Conductor</option><option value="orchestra">Orchestra</option><option value="soloists">Soloists</option>
</select>
<button type="button" id="collection-ods">Export OpenDocument (.ods)</button>
<button type="button" id="collection-xlsx">Export Excel-compatible (.xlsx)</button>
<button type="button" id="collection-csv">Export CSV</button>
<div id="collection-result" aria-live="polite"></div>
<h3>Archive metadata maintenance (staging-independent)</h3>
<p>Scan the entire indexed published archive against MusicBrainz, without staging files. Each album is independently verified; errors are reported without interrupting the remaining albums. Accepted proposals remain pending migration, not applied to FLACs.</p>
<details class="oscar-advanced"><summary>Advanced · scan only one archive album</summary>
<label for="archive-scan-album">Published archive to scan (optional)</label>
<select id="archive-scan-album"><option value="">Import/refresh Collection and select an album</option></select>
<p>Choose an album here only for troubleshooting. The two main scan buttons below scan the entire Collection.</p>
<button type="button" id="archive-scan-one-additions">Scan selected album for additions</button>
<button type="button" id="archive-scan-one-changes">Scan selected album for changes</button>
</details>
<button type="button" id="archive-scan-additions">Scan archive for metadata additions</button>
<button type="button" id="archive-scan-changes">Scan archive for metadata changes</button>
<details class="oscar-advanced"><summary>Genre evidence — source comparison (read-only)</summary>
<p>Compare MusicBrainz release/release-group genre votes and optionally a catalog-matched Discogs CD release. Reported agreement is not the statistical probability of correctness. This does not modify tags, publication evidence or Collection.</p>
<label for="genre-evidence-discogs">Discogs release ID (optional; exact catalog and CD required)</label>
<input type="number" id="genre-evidence-discogs" min="1" max="99999999" placeholder="e.g. 123456" />
<label for="genre-evidence-workflow">Review policy</label>
<select id="genre-evidence-workflow"><option value="semi_automatic">Semi Automatic</option><option value="best_guess">Best Guess</option><option value="secure">Secure</option></select>
<button type="button" id="genre-evidence-preview">Compare genre sources (read-only)</button>
<div id="genre-evidence-result" aria-live="polite"></div>
</details>
<button type="button" id="archive-scan-review">Review pending metadata proposals</button>
<button type="button" id="archive-scan-history">View decision history</button>
<div id="archive-scan-result" aria-live="polite"></div>
<h3>Archive Metadata Migration (explicitly approved)</h3>
<p>Preview approved metadata proposals for an archived single-CD album. Actual migration is disabled unless OSCAR_ENABLE_ARCHIVE_REVISIONS=1. When enabled, OSCAR preserves the original published generation in retained archive history, verifies a new FLAC/tag/manifest generation, and updates Collection. A catalog-number change also updates the album folder name. Boxsets require a separate coordinated migration.</p>
<button type="button" id="archive-revision-preview">Preview approved archive migration for selected album</button>
<button type="button" id="archive-revision-operations">View archive revision history and recovery status</button>
<button type="button" id="archive-boxset-label-preview">Preview coordinated multidisc labels (read-only)</button>
<button type="button" id="archive-boxset-genre-preview">Preview coordinated multidisc genres (read-only)</button>
<button type="button" id="archive-boxset-history">View multidisc revision history / recovery</button>
<p>Verify checks new and original FLACs, manifests, CUE/source evidence and Collection. Clean permanently removes only the verified retained original of one operation, destroys OSCAR's internal rollback, and requires OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP=1 plus an independent backup and double confirmation. Prefer excluding hidden archive history from media-server scans. Never Clean if you need the original archive for recovery.</p>
<div id="archive-revision-output" aria-live="polite"></div>
<h3>Track-level catalog (classical &amp; other music)</h3>
<p>Search each archived FLAC's recorded track title, MusicBrainz Work, composer, conductor, performer or explicitly credited soloist. No missing credits are inferred.</p>
<button type="button" id="collection-index-tracks">Index verified published tracks</button>
<label for="track-search">Find track / work / musician</label>
<input id="track-search" maxlength="150" placeholder="e.g. Boulez, Handel, soprano, or Water Music" style="width:350px;max-width:90%">
<label for="track-role">Filter to tracks with contributor type</label>
<select id="track-role">
<option value="">All roles</option>
<option value="composer">Composer</option><option value="conductor">Conductor</option>
<option value="orchestra">Orchestra</option><option value="performer">Performer</option>
<option value="soloist">Explicit soloist</option>
</select>
<button type="button" id="track-search-btn">Find tracks</button>
<div id="tracks-output" aria-live="polite"></div>
<h3>Discogs connection (read-only)</h3>
<p>Your personal token is read only from the Portainer OSCAR_DISCOGS_PAT environment variable. Check account identity and collection folder names without modifying Discogs. The token is never shown or saved to the local catalog.</p>
<button type="button" id="discogs-check">Check Discogs account and folders</button>
<div id="discogs-result" aria-live="polite"></div>
</section>
<section><h2>Go! · rip, verification, metadata and archive (phase 3)</h2>
<p>Start a new rip and persist your saved Best Guess, Semi Automatic or Secure policy before extraction. Verification automatically starts after ripping. The controller checks MusicBrainz candidates only after verified audio, then can create a <strong>separate, integrity-checked tagged staging copy</strong> for an accepted Semi Automatic release or Best Guess inference. The original FLAC rip remains unchanged. <strong>Semi Automatic always requires separate publication approval. Best Guess may automatically publish only when OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH=1, archive publishing is enabled, a unique inferred candidate is present and metadata review raises no warnings. Neither inference nor archived_verified proves the exact physical edition.</strong></p>
<p>One independent Go! action per enabled, detected and offset-calibrated optical drive. A busy drive cannot start another rip. The cards show the latest jobs for each drive.</p>
<div id="go-drive-cards" class="go-drive-grid" aria-live="polite"></div>
<button type="button" id="go-refresh-drives">Refresh drive status</button>
<h3>Selected Go! workflow</h3>
<label for="go-drive">Selected optical drive</label><select id="go-drive"></select>
<button type="button" id="go-start" hidden>Go! — rip to verified staging</button>
<label for="go-job">Go job ID</label>
<input id="go-job" maxlength="32" placeholder="Created automatically or paste existing Go job ID" style="width:350px;max-width:95%">
<button type="button" id="go-advance">Check next safe step</button>
<div id="go-result" aria-live="polite"></div>
<h3>Tracked Go! jobs</h3>
<p>Saved MusicBrainz candidates are hints, not physical-edition proof. Published jobs are hidden by default; no archive or staging files are changed by these controls.</p>
<div class="go-job-toolbar">
<label for="go-job-filter">Show <select id="go-job-filter"><option value="action">Needs attention</option><option value="active">In progress</option><option value="published">Published</option><option value="all">All jobs</option></select></label>
<label for="go-job-sort">Sort <select id="go-job-sort"><option value="updated">Recent activity</option><option value="created">Newest created</option><option value="priority">Priority</option><option value="album">Album A–Z</option><option value="id">Job ID</option></select></label>
</div>
<div id="go-job-summary" aria-live="polite"></div>
<div id="go-workflows" aria-live="polite"></div>
</section>
<section><h2>Persistent workflow ledger · towards CD in → Go!</h2>
<p>Advanced recovery for already saved staging rips. Go! jobs are registered automatically; use this form only for manual recovery and historical imports. Nothing is re-ripped or overwritten.</p>
<label for="workflow-job">Staging rip job ID</label>
<input id="workflow-job" maxlength="32" placeholder="32-character saved OSCAR job ID" style="width:350px;max-width:95%">
<button type="button" id="workflow-register">Register saved rip</button>
<button type="button" id="workflow-refresh">Refresh from staging</button>
<button type="button" id="workflow-defer">Defer edition review</button>
<button type="button" id="workflow-resume">Resume edition review</button>
<button type="button" id="workflow-list">View tracked jobs</button>
<div id="workflow-result" aria-live="polite"></div>
</section>
<section><h2>Staging verification (experimental)</h2>
<p>Review an already completed OSCAR rip. Reads cyanrip AccurateRip evidence, checks saved SHA-256, decodes each FLAC and validates CUE references. No tagging, archiving or cleanup.</p>
<label for="verify-job">Staging rip job ID (32 hexadecimal characters)</label>
<input id="verify-job" placeholder="f41806152a614b1a9006b10456b9bbd4" maxlength="32" style="width:340px;max-width:90%">
<button id="verify-start" type="button">Verify staged rip</button>
<div id="verify-output" aria-live="polite"></div></section>
<section><h2>Metadata &amp; tagging (experimental)</h2>
<p>Only for a previously verified staging rip. Preview an explicitly selected MusicBrainz physical release, including its classical work/performer relationships. Review label/catalog details before copying. Original FLACs are never modified.</p>
<label for="metadata-job">Verified staging job ID</label>
<input id="metadata-job" maxlength="32" placeholder="Paste 32-character rip job ID" style="width:340px;max-width:90%">
<label for="metadata-release">MusicBrainz release UUID (exact physical edition, not release group)</label>
<input id="metadata-release" maxlength="36" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style="width:360px;max-width:90%">
<button type="button" id="metadata-preview-btn">Preview MusicBrainz tags</button>
<div id="metadata-output" aria-live="polite"></div></section>
<section><h2>Find a physical release without a Disc ID match (read-only)</h2>
<p>Look up MusicBrainz releases by the catalog number on the CD packaging, or by album title. This is candidate discovery only, not verified edition matching. Especially useful when the Disc ID points to a different release.</p>
<label for="catalog-search">Printed catalog number</label><input id="catalog-search" maxlength="100" placeholder="CCC 97001" style="width:260px;max-width:95%">
<button type="button" id="catalog-search-button">Search by catalog number</button>
<label for="title-search">Album title (alternative search)</label><input id="title-search" maxlength="100" placeholder="Essential Dance Traxx" style="width:320px;max-width:95%">
<button type="button" id="title-search-button">Search by title</button>
<div id="release-search-results" aria-live="polite"></div>
</section>
<section><h2>CD not found, wrong edition or incomplete metadata?</h2>
<p>OSCAR can preserve a verified rip safely while its physical release remains unresolved. A matching Disc ID does not prove an edition. Do not tag from an unrelated release.</p>
<label for="recovery-reason">What happened?</label>
<select id="recovery-reason">
<option value="missing_release">My physical CD is missing from MusicBrainz</option>
<option value="wrong_edition">MusicBrainz suggests the wrong edition</option>
<option value="ambiguous_edition">Several editions may match</option>
<option value="incomplete_metadata">The correct release has missing or incorrect metadata</option>
</select>
<div id="recovery-guidance" class="oscar-review-note" aria-live="polite"></div>
<label for="recovery-job">Verified staging rip job ID (optional until saving)</label>
<input id="recovery-job" maxlength="32" placeholder="32-character rip job ID" style="width:340px;max-width:95%">
<label for="recovery-title">Physical album title (optional)</label>
<input id="recovery-title" maxlength="200" placeholder="Essential Dance Traxx" style="width:340px;max-width:95%">
<label for="recovery-catalog">Catalog number on CD (optional)</label>
<input id="recovery-catalog" maxlength="100" placeholder="CCC 97001" style="width:280px;max-width:95%">
<label for="recovery-notes">Evidence / differences (optional)</label>
<textarea id="recovery-notes" maxlength="1000" rows="3" style="width:95%;background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px" placeholder="What differs from MusicBrainz? Missing barcode? Cover sticker?"></textarea>
<p>Only a successfully verified staging job can be added to the persistent follow-up list. This does not create a MusicBrainz edit, tags or a final archive. Raw ripping files remain untouched.</p>
<button type="button" id="recovery-defer">Save for later (no metadata changes)</button>
<button type="button" id="recovery-list">View pending CD reviews</button>
<div id="recovery-output" aria-live="polite"></div>
<p>Guides: <a href="https://musicbrainz.org/doc/How_to_Add_a_Release" target="_blank" rel="noopener noreferrer">Add a new MusicBrainz release</a> · <a href="https://musicbrainz.org/doc/How_to_Identify_Unknown_CDs" target="_blank" rel="noopener noreferrer">Identify an unknown CD</a> · <a href="https://musicbrainz.org/release/add" target="_blank" rel="noopener noreferrer">MusicBrainz release editor</a>. Publishing or linking to MusicBrainz requires separate user action and verification.</p>
</section>
<section><h2>Physical release comparison (read-only)</h2>
<p>Compare the catalog number printed on your CD and optional barcode with a specific MusicBrainz release, even when the Disc ID is associated with a different edition. No tagging or release selection occurs here. A matching Disc ID alone never proves the physical pressing.</p>
<label for="physical-job">Verified staging job ID</label><input id="physical-job" maxlength="32" placeholder="32-character rip job ID" style="width:340px;max-width:95%">
<label for="physical-release">MusicBrainz release UUID (not release group)</label><input id="physical-release" maxlength="36" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style="width:360px;max-width:95%">
<label for="physical-catalog">Catalog number printed on your physical CD</label><input id="physical-catalog" maxlength="100" placeholder="e.g. label catalog number" style="width:340px;max-width:95%">
<label for="physical-barcode">Printed barcode (optional)</label><input id="physical-barcode" maxlength="14" placeholder="Optional 8–14 digits" style="width:240px;max-width:95%">
<button type="button" id="physical-compare-btn">Compare physical edition</button>
<div id="physical-output" aria-live="polite"></div>
</section>
<section><h2>Inspect saved FLAC metadata</h2>
<p>Read the actual tags from the new copies, compare with the saved MusicBrainz preview, and verify the tagged file hashes. No files are modified.</p>
<label for="inspect-job">Rip job ID</label>
<input id="inspect-job" maxlength="32" placeholder="32-character rip job ID" style="width:340px;max-width:90%">
<label for="inspect-copy">Tagged copy ID</label>
<input id="inspect-copy" maxlength="32" placeholder="32-character tagged copy ID" style="width:340px;max-width:90%">
<button type="button" id="inspect-start">Inspect saved tags</button>
<div id="inspect-result" aria-live="polite"></div></section>
<section><h2>Classical metadata v2 — review</h2>
<p>Preview MusicBrainz works independently of optional, explicitly reviewed physical-CD sections. Leave sections blank if the booklet has not been checked. New copies require separate approval.</p>
<label for="v2-job">Rip job ID</label><input id="v2-job" maxlength="32" style="width:340px;max-width:90%">
<label for="v2-source">Completed tagged-copy ID</label><input id="v2-source" maxlength="32" style="width:340px;max-width:90%">
<label for="v2-sections">Optional booklet-verified CD sections (one per line: start-end | section title)</label>
<textarea id="v2-sections" rows="4" style="width:95%;background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px" placeholder="Leave blank unless verified against booklet: 1-4 | Section title"></textarea>
<p>Sections are not required. If entered, ranges must cover every track without gaps or overlaps.</p>
<label for="v2-movements">Optional manually reviewed movement labels (one per line: track number | movement text; leave blank to preserve unknown)</label>
<textarea id="v2-movements" rows="2" style="width:95%;background:#0c131b;color:white;border:1px solid #516376;border-radius:8px;padding:9px"></textarea>
<button id="v2-preview" type="button">Preview classical v2 tags</button>
<div id="v2-output" aria-live="polite"></div></section>
<section><h2>Archive review · consistency, cover &amp; CUE (read-only)</h2>
<p>Checks documented MusicBrainz recording/work relationships and duration evidence, previews the exact release's Cover Art Archive front candidate, and prepares a CUE preview preserving the original INDEX/PREGAP lines. Nothing is published or modified.</p>
<label for="review-job">Original rip job ID</label><input id="review-job" maxlength="32" style="width:340px;max-width:95%">
<label for="review-copy">Completed tagged-copy ID</label><input id="review-copy" maxlength="32" style="width:340px;max-width:95%">
<label for="review-kind">Copy type</label><select id="review-kind"><option value="original_tags">Original MusicBrainz tagged copy</option><option value="classical_v2">Classical v2 tagged staging copy</option></select>
<label for="review-profile">Music processing profile</label><select id="review-profile"><option value="auto">Automatic (recommended)</option><option value="standard">Standard: pop, rock, dance, compilation</option><option value="classical">Classical: conductor, ensemble, soloist</option></select>
<p>OSCAR chooses its processing policy from verified metadata, not a guessed music genre. You can override this read-only review if the automatic decision is unsuitable.</p>
<button type="button" id="review-start">Review metadata, artwork &amp; CUE</button>
<div id="review-output" aria-live="polite"></div></section>
<section><h2>Publish verified FLAC archive (explicit opt-in)</h2>
<p>Create a completely separate album folder from an existing, successfully verified tagged staging copy. Original rip, tagged FLACs, original CUE and logs remain unchanged. Publication needs a dedicated writable archive mount, `OSCAR_ARCHIVE_ROOT`, and `OSCAR_ENABLE_ARCHIVE_PUBLISH=1`; disabled by default. Only a fully reviewed physical release should be published.</p>
<label for="publish-job">Original verified rip job ID</label><input id="publish-job" maxlength="32" style="width:340px;max-width:95%">
<label for="publish-copy">Completed tagged-copy ID</label><input id="publish-copy" maxlength="32" style="width:340px;max-width:95%">
<label for="publish-kind">Tagging copy type</label><select id="publish-kind">
<option value="original_tags">Original MusicBrainz tagged copy (pop / dance)</option>
<option value="classical_v2">Classical v2 tagged copy</option>
</select>
<label for="publish-profile">Metadata/CUE processing</label><select id="publish-profile">
<option value="auto">Automatic from verified credits (recommended)</option>
<option value="standard">Standard (pop / rock / dance)</option>
<option value="classical">Classical (conductor / ensemble / soloist)</option>
</select>
<label><input type="checkbox" id="publish-cover"> Include reviewed Cover Art Archive front image (separate cover file, not embedded)</label>
<button type="button" id="publish-preview">Preview proposed archive (read-only)</button>
<div id="publish-plan" aria-live="polite"></div>
<div id="publish-confirmation" hidden>
<label><input type="checkbox" id="publish-physical"> I checked this exact physical MusicBrainz edition and tracklist against my CD.</label>
<label><input type="checkbox" id="publish-cue-approved"> I reviewed the proposed track filenames and the CUE, including source INDEX/PREGAP.</label>
<label id="publish-observation-label" hidden><input type="checkbox" id="publish-observations"> I reviewed and accept the listed unresolved metadata observations without claiming they are corrected.</label>
<label id="publish-cover-label" hidden><input type="checkbox" id="publish-cover-approved"> I compared the shown Cover Art Archive candidate with my physical CD and accept this particular image, including any sticker differences.</label>
<button type="button" id="publish-start">Publish reviewed copies to separate archive</button>
</div>
<div id="publish-result" aria-live="polite"></div>
<p>This never automatically approves a MusicBrainz match or deletes staging files. Publication status runs asynchronously while OSCAR stays online. Repeated publication refuses an existing destination; interrupted hidden staging copies are retained for inspection.</p>
</section>
<section><h2>Parallel optical drives</h2>
<p>Different enabled drives may rip simultaneously. Each has its own staging job and log. Drive count and available capacity are shown here; there is no persistent background queue or auto-eject yet.</p>
<button type="button" id="multi-refresh">Refresh drive dashboard</button>
<div id="multi-output" aria-live="polite"></div></section>
<button id="save">Save settings</button><p id="status" aria-live="polite"></p>
<script>
// Progressive enhancement: retain every existing form, endpoint and event
// handler; move the legacy specialist surfaces into a collapsible Review area.
const oscarTabNames=[
 ['go','Go!'],['review','Review'],['collection','Collection'],['settings','Settings']
];
const oscarNav=document.getElementById('oscar-tabs');
const oscarPanels=document.getElementById('oscar-panels');
const oscarTabButtons=new Map();
const oscarPanelsByName=new Map();
for(const [name,label] of oscarTabNames){
 const button=document.createElement('button');
 button.type='button';button.id='tab-'+name;button.className='oscar-tab';
 button.textContent=label;button.setAttribute('role','tab');
 button.setAttribute('aria-controls','panel-'+name);
 button.setAttribute('aria-selected','false');
 const panel=document.createElement('main');
 panel.id='panel-'+name;panel.className='oscar-panel';
 panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);
 panel.hidden=true;
 button.onclick=()=>{showOscarTab(name);history.replaceState(null,'','#'+name)};
 oscarNav.append(button);oscarPanels.append(panel);
 oscarTabButtons.set(name,button);oscarPanelsByName.set(name,panel);
}
const oscarAdvanced=document.createElement('details');
oscarAdvanced.className='oscar-advanced';
const advancedTitle=document.createElement('summary');
advancedTitle.textContent='Advanced tools · verification, tagging, physical release checks and manual publishing';
oscarAdvanced.append(advancedTitle);
const mainReview=oscarPanelsByName.get('review');
const reviewIntro=document.createElement('section');
reviewIntro.innerHTML='<h2>Jobs requiring review</h2><p>Find blocked, uncertain or historical jobs here. Only explicit actions change metadata or publish an archive.</p><div id="review-jobs"></div><button type="button" id="review-refresh">Refresh review queue</button>';
mainReview.append(reviewIntro,oscarAdvanced);
const mainGo=oscarPanelsByName.get('go');
const goIntro=document.createElement('p');
goIntro.textContent='Per-drive ripping and persistent Go! workflows. No unsafe automatic retry.';
mainGo.append(goIntro);
const settingsSectionTitles=new Set(['Ripping profile','Release identification & automation policy',
 'Language & names','Optical drives']);
for(const section of [...document.body.querySelectorAll(':scope > section')]){
 const title=section.querySelector('h2')?.textContent.trim()||'';
 if(title.startsWith('Go! ·'))mainGo.append(section);
 else if(title.startsWith('Collection Library'))oscarPanelsByName.get('collection').append(section);
 else if(settingsSectionTitles.has(title))oscarPanelsByName.get('settings').append(section);
 else oscarAdvanced.append(section);
}
const saveButton=document.getElementById('save');
const saveStatus=document.getElementById('status');
oscarPanelsByName.get('settings').append(saveButton,saveStatus);
function showOscarTab(name){
 if(!oscarPanelsByName.has(name))name='go';
 for(const [key,panel] of oscarPanelsByName){
  const active=key===name;panel.hidden=!active;
  oscarTabButtons.get(key).setAttribute('aria-selected',String(active));
  oscarTabButtons.get(key).tabIndex=active?0:-1;
 }
 if(name==='go')refreshGoCards(false);
 if(name==='review')refreshReviewQueue(false);
}
oscarNav.addEventListener('keydown',event=>{
 if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;
 event.preventDefault();
 const current=[...oscarTabButtons.keys()].find(k=>oscarTabButtons.get(k).getAttribute('aria-selected')==='true')||'go';
 const names=[...oscarTabButtons.keys()];
 let index=names.indexOf(current);
 if(event.key==='ArrowRight')index=(index+1)%names.length;
 if(event.key==='ArrowLeft')index=(index-1+names.length)%names.length;
 if(event.key==='Home')index=0;
 if(event.key==='End')index=names.length-1;
 showOscarTab(names[index]);oscarTabButtons.get(names[index]).focus();
 history.replaceState(null,'','#'+names[index]);
});
window.addEventListener('hashchange',()=>showOscarTab(location.hash.slice(1)));
let settings;
showOscarTab(location.hash.slice(1));

let trustedLocalUI=false;
fetch('/api/ui/access').then(r=>r.ok?r.json():{}).then(data=>{
 trustedLocalUI=!!data.trusted_local_ui;
}).catch(()=>{trustedLocalUI=false});
function requestAuthHeaders(description){
 if(trustedLocalUI)return {'X-OSCAR-UI-ACTION':'confirmed'};
 const token=window.prompt(description+' (OSCAR rip token)');
 return token?{'X-OSCAR-RIP-TOKEN':token}:null;
}
const area=document.getElementById('drives');
function safeText(node,value){node.textContent=value;}
async function init(){
 const [a,b]=await Promise.all([fetch('/api/settings'),fetch('/api/drives')]);
 if(!a.ok||!b.ok)throw new Error('Unable to load configuration');
 settings=await a.json();const live=await b.json();
 const goDrive=document.getElementById('go-drive');goDrive.replaceChildren();
 for(const drive of settings.drives.filter(d=>d.enabled)){
  const option=document.createElement('option');
  option.value=drive.stable_id;option.textContent=drive.label;goDrive.append(option);
 }
 document.getElementById('profile').value=settings.profile;
 document.getElementById('identification-mode').value=settings.identification_mode||'secure';
 document.getElementById('secure-review-level').value=settings.secure_review_level||'on_ambiguity';
 updateIdentificationMode();
 document.getElementById('name-display').value=settings.name_display||'original_and_english';
 document.getElementById('alias-fallback').value=settings.english_alias_fallback||'original';
 area.replaceChildren();
 for(const drive of settings.drives){
  const row=document.createElement('div');row.className='drive';
  const head=document.createElement('strong');safeText(head,drive.label);
  const device=document.createElement('small');
  const match=live.find(x=>x.stable_id===drive.stable_id);
  safeText(device,drive.stable_id+(match?(match.present?' · detected: ':' · missing: ')+match.device:' · not currently detected'));
  const label=document.createElement('label');const check=document.createElement('input');
  check.type='checkbox';check.checked=drive.enabled;check.onchange=()=>drive.enabled=check.checked;
  label.append(check,document.createTextNode(' Enable drive'));
  const offsetLabel=document.createElement('label');safeText(offsetLabel,' Read offset (samples; blank = unknown) ');
  const offset=document.createElement('input');offset.type='number';offset.min=-2000;offset.max=2000;
  offset.value=drive.offset_samples===null?'':drive.offset_samples;
  offset.oninput=()=>{drive.offset_samples=offset.value===''?null:Number(offset.value)};
  offsetLabel.append(offset);row.append(head,device,label,offsetLabel);
  const assist=document.createElement('div');
  const link=document.createElement('a');link.href='https://www.accuraterip.com/driveoffsets.htm';
  link.target='_blank';link.rel='noopener noreferrer';link.textContent='AccurateRip drive offset database';
  link.style.color='#bfd5ff';
  const hint=document.createElement('small');hint.style.display='block';
  hint.textContent=drive.offset_samples===null?'Offset not yet set.':'Saved offset: '+drive.offset_samples+' samples (never automatically overwritten).';
  const lookup=document.createElement('button');lookup.type='button';
  lookup.style.marginRight='8px';lookup.textContent='Look up offset';
  lookup.onclick=async()=>{
   hint.textContent='Checking AccurateRip drive-offset database…';
   try{
    const r=await fetch('/api/drive-offset/lookup?'+new URLSearchParams({stable_id:drive.stable_id}));
    if(!r.ok)throw new Error(await r.text());
    const data=await r.json();
    if(data.suggested_offset!==null){
     hint.textContent='Database suggests '+data.suggested_offset+' samples. Review before saving.';
     if(drive.offset_samples===null){
       offset.value=String(data.suggested_offset);
       drive.offset_samples=data.suggested_offset;
       hint.textContent+=' Suggested value filled in; click Save settings to persist.';
     }
    }else{
     hint.textContent=data.status==='conflict'?'Conflicting reported offsets for this model: '+
      [...new Set(data.matches.map(x=>x.offset_samples))].join(', ')+
      '. Do not guess; calibrate with a known disc or review the database.':
      'No reliable matching database offset. Try CD calibration or manual lookup.';
    }
   }catch(e){hint.textContent='Lookup unavailable; use the linked database manually. '+e.message}
  };
  const detect=document.createElement('button');detect.type='button';
  detect.style.marginRight='8px';detect.textContent='Detect from CD (experimental)';
  detect.onclick=async()=>{
    if(!confirm('Use the inserted CD to detect a drive offset with cyanrip? It must be known to AccurateRip. No audio is archived, and your settings will not be saved automatically.'))return;
    const access=requestAuthHeaders('Confirm CD offset calibration');
    if(!access)return;
    detect.disabled=true;hint.textContent='Reading offset from reference CD…';
    try{
      const r=await fetch('/api/drive-offset/from-disc',{method:'POST',
        headers:{...access,'Content-Type':'application/json'},
        body:JSON.stringify({stable_id:drive.stable_id,confirmation:'CALIBRATE_OFFSET'})});
      if(!r.ok)throw new Error(await r.text());
      const data=await r.json();
      if(data.suggested_offset!==null){
       hint.textContent='CD suggests '+data.suggested_offset+
        ' samples (experimental; review). Click Save settings to persist.';
       if(drive.offset_samples===null){
        offset.value=String(data.suggested_offset);drive.offset_samples=data.suggested_offset;
       }else hint.textContent+=' Existing saved offset left untouched.';
      }else hint.textContent=data.message;
    }catch(e){hint.textContent='CD calibration failed: '+e.message}
    finally{detect.disabled=false}
  };
  assist.append(lookup,detect,link,hint);row.append(assist);area.append(row);
  if(drive.offset_samples===null)lookup.click();
 }
}
document.getElementById('probe').onclick=async()=>{
 const el=document.getElementById('media-status');el.textContent='Checking drives…';
 try{
  const response=await fetch('/api/media');
  if(!response.ok)throw new Error(await response.text());
  const results=await response.json();
  el.replaceChildren();
  if(!results.length){el.textContent='No enabled drives detected. Enable and save a drive first.';return}
  for(const disc of results){
   const p=document.createElement('p');
   p.textContent=disc.label+' ('+disc.device+'): '+disc.status+
      (disc.disc_type?' · '+disc.disc_type:'')+(disc.error?' · '+disc.error:'');
   el.append(p);
   if(disc.status==='disc_present' && disc.disc_type==='audio'){
     const button=document.createElement('button');button.type='button';
     button.textContent='Read TOC and MusicBrainz ID';
     button.onclick=()=>showToc(disc.stable_id);
     el.append(button);
     const rip=document.createElement('button');rip.type='button';
     rip.style.marginLeft='8px';
     rip.textContent='Test rip to staging (experimental)';
     rip.onclick=()=>startTestRip(disc.stable_id,disc.label);
     el.append(rip);
   }
  }
 }catch(error){el.textContent='Probe unavailable: '+error.message}
};
async function startTestRip(stableId,label){
 const headers=requestAuthHeaders('Start experimental staging rip');
 if(!headers)return;
 const status=document.createElement('p');
 status.textContent='Checking test-rip plan for '+label+'…';
 document.getElementById('media-status').append(status);
 try{
  const planResponse=await fetch('/api/rip/plan?'+new URLSearchParams({stable_id:stableId}),{headers});
  if(!planResponse.ok)throw new Error(await planResponse.text());
  const plan=await planResponse.json();
  const accepted=window.confirm('EXPERIMENTAL RIP: '+plan.track_count+
    ' tracks from '+plan.device+' (offset '+plan.offset_samples+
    ') into a NEW folder below '+plan.output_root+
    '. No archive publication or cleanup. Continue?');
  if(!accepted){status.textContent='Test rip cancelled before starting';return}
  const response=await fetch('/api/rip/start',{
    method:'POST',
    headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify({stable_id:stableId,confirmation:'RIP_TO_STAGING'})
  });
  if(!response.ok)throw new Error(await response.text());
  const job=await response.json();
  status.textContent='Rip job '+job.id+' started. Checking status…';
  const poll=async()=>{
    try{
      const r=await fetch('/api/rip/jobs/'+encodeURIComponent(job.id),{headers});
      if(!r.ok)throw new Error(await r.text());
      const state=await r.json();
      status.textContent='Rip '+job.id+': '+state.status+
        (state.flac_count?' · '+state.flac_count+' FLAC files':'')+
        (state.error?' · '+state.error:'')+
        (state.warning?' · '+state.warning:'');
      if(state.status==='needs_verification'){
        document.getElementById('verify-job').value=job.id;
        const hint=document.createElement('button');hint.type='button';
        hint.textContent='Open verification for this rip';
        hint.onclick=()=>{document.getElementById('verify-job').scrollIntoView({behavior:'smooth'});
          document.getElementById('verify-job').focus();};
        status.append(document.createTextNode(' '),hint);
      }
      if(state.status==='queued'||state.status==='running')setTimeout(poll,3000);
    }catch(error){status.textContent='Rip status unavailable: '+error.message}
  };
  poll();
 }catch(error){status.textContent='Test rip not started: '+error.message}
}
async function showToc(stableId){
 const target=document.getElementById('toc-results');target.replaceChildren();
 const status=document.createElement('p');status.textContent='Reading disc TOC…';target.append(status);
 try{
  const r=await fetch('/api/toc?'+new URLSearchParams({stable_id:stableId}));
  if(!r.ok)throw new Error(await r.text());
  const toc=await r.json();
  status.textContent='MusicBrainz Disc ID: '+toc.musicbrainz_disc_id+' · '+toc.tracks.length+' tracks · Lead-out '+toc.leadout_sector;
  const note=document.createElement('p');note.textContent='INDEX 00, pregaps and hidden track-one audio are not checked by a standard TOC.';target.append(note);
  const table=document.createElement('table');table.style.width='100%';
  for(const track of toc.tracks){
    const tr=document.createElement('tr');
    for(const value of [track.number,track.start_sector,track.duration_seconds+' s']){
      const cell=document.createElement('td');cell.textContent=String(value);cell.style.padding='5px';tr.append(cell);
    }table.append(tr);
  }
  target.append(table);
  const lookup=document.createElement('button');lookup.type='button';
  lookup.textContent='Find release candidates on MusicBrainz';
  lookup.onclick=()=>showCandidates(stableId);target.append(lookup);
 }catch(error){status.textContent='TOC unavailable: '+error.message}
}
async function showCandidates(stableId,catalogNumber=''){
 const target=document.getElementById('toc-results');
 const previous=document.getElementById('disc-candidates');
 if(previous)previous.remove();
 const area=document.createElement('section');area.id='disc-candidates';target.append(area);
 const p=document.createElement('p');p.textContent='Looking up MusicBrainz candidates…';area.append(p);
 try{
  const params={stable_id:stableId};
  if(catalogNumber)params.catalog_number=catalogNumber;
  const r=await fetch('/api/releases?'+new URLSearchParams(params));
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();
  const gate=result.edition_gate||{};
  p.textContent=result.releases.length+' Disc ID candidate(s). None is automatically approved as the physical edition.';
  const guide=document.createElement('p');guide.className='oscar-review-note';
  guide.textContent=gate.message||'Compare the physical edition before tagging.';
  area.append(guide);
  if(gate.catalog_prompt_recommended){
    const label=document.createElement('label');
    label.textContent='Catalog number printed on your physical CD';
    const input=document.createElement('input');input.maxLength=100;
    input.placeholder='e.g. E 8512';input.value=catalogNumber;
    const search=document.createElement('button');search.type='button';
    search.textContent='Compare printed catalog number';
    search.onclick=()=>{
      const value=input.value.trim();
      if(!value){guide.textContent='Enter the catalog number to narrow the physical editions.';return}
      showCandidates(stableId,value);
    };
    area.append(label,input,search);
  }
  if(gate.status==='catalog_conflict'||gate.status==='no_disc_candidates'){
    const fallback=document.createElement('button');fallback.type='button';
    fallback.textContent='Search MusicBrainz independently by catalog number';
    fallback.onclick=()=>{
      const value=gate.printed_catalog||(area.querySelector('input')?.value||'').trim();
      if(!value){guide.textContent='Enter the catalog number first.';return}
      document.getElementById('catalog-search').value=value;
      document.getElementById('catalog-search-button').click();
      document.getElementById('release-search-results').scrollIntoView({behavior:'smooth'});
    };
    area.append(fallback);
  }
  for(const release of result.releases){
    const entry=document.createElement('p');
    const link=document.createElement('a');
    link.href='https://musicbrainz.org/release/'+encodeURIComponent(release.id);
    link.target='_blank';link.rel='noopener noreferrer';
    link.textContent=(release.title||'Untitled')+' · '+(release.artist||'Unknown')+' · '+(release.date||'?')+
      ' · '+(release.labels||[]).map(x=>(x.name||'')+' '+(x.catalog_number||'')).join(', ');
    entry.append(link);
    if(release.printed_catalog_matches===false){
      entry.append(document.createTextNode(' · printed catalog differs'));
    }
    const inspect=document.createElement('button');inspect.type='button';
    inspect.style.marginLeft='10px';inspect.textContent='Inspect disc & tracklist';
    inspect.onclick=()=>showMedium(stableId,release.id);
    if(gate.status==='catalog_conflict'||(catalogNumber&&release.printed_catalog_matches===false)){
      inspect.disabled=true;inspect.title='Catalog differs from physical CD';
    }
    entry.append(inspect);area.append(entry);
  }
  if(gate.status==='single_candidate'&&result.releases.length===1){
    // Read-only automatic inspection, never tagging or physical edition approval.
    await showMedium(stableId,result.releases[0].id);
  }
 }catch(error){p.textContent='MusicBrainz unavailable: '+error.message}
}
const aliasCache=new Map();
async function aliasFor(type,id){
 const key=type+':'+id;
 if(!aliasCache.has(key)){
  const req=fetch('/api/name-aliases?'+new URLSearchParams({entity_type:type,entity_id:id}))
   .then(async r=>{if(!r.ok)throw new Error(await r.text());return r.json()})
   .catch(e=>{aliasCache.delete(key);throw e});
  aliasCache.set(key,req);
 }
 return aliasCache.get(key);
}
function nameValue(original,alias){
 const mode=settings.name_display||'original_and_english';
 const fallback=settings.english_alias_fallback||'original';
 const extra=alias.english||(fallback==='sort_name'&&alias.sort_name!==original?alias.sort_name:null);
 if(!extra||extra===original||mode==='original')return original;
 if(mode==='english')return extra;
 return original+' ('+extra+')';
}
function aliasNode(type,id,original){
 const span=document.createElement('span');
 const value=document.createElement('span');value.textContent=original||'—';span.append(value);
 if(!id)return span;
 const button=document.createElement('button');button.type='button';
 button.style.margin='4px';button.style.padding='4px 8px';button.style.fontSize='12px';
 button.textContent='EN';button.title='English alias automatically enriched';
 button.className='alias-enrichment';button.dataset.aliasType=type;button.dataset.aliasId=id;
 button.applyAlias=(alias)=>{
   value.textContent=nameValue(original||alias.original,alias);
   const source=alias.english?alias.english_source:
      (settings.english_alias_fallback==='sort_name'&&alias.sort_name?'sort name':'no English alias');
   button.title=(alias.cache_status==='stale'?'Cached name; MusicBrainz temporarily unavailable. ':'')+source+'; original: '+alias.original;
   button.textContent=alias.cache_status==='stale'?'EN ~':(alias.english?'EN ✓':'EN —');
   button.disabled=true;
 };
 button.onclick=async()=>{
  button.disabled=true;button.textContent='…';
  try{
   const alias=await aliasFor(type,id);
   button.applyAlias(alias);
  }catch(e){button.disabled=false;button.textContent='EN';button.title=e.message}
 };
 span.append(button);return span;
}
async function enrichNamesAutomatically(area){
 const buttons=[...area.querySelectorAll('button.alias-enrichment')];
 const keys=new Map();
 for(const button of buttons){
  const key=button.dataset.aliasType+':'+button.dataset.aliasId;
  if(!keys.has(key))keys.set(key,{
   entity_type:button.dataset.aliasType,entity_id:button.dataset.aliasId
  });
  button.textContent='EN …';button.disabled=true;
 }
 const entities=[...keys.values()];
 if(!entities.length)return;
 const message=document.createElement('p');
 message.textContent='Automatically enriching '+entities.length+' unique composer, performer and work names…';
 area.prepend(message);
 let completed=0, failed=0, cacheHits=0;
 for(let i=0;i<entities.length;i+=8){
  if(!area.isConnected)return;
  const batch=entities.slice(i,i+8);
  try{
   const r=await fetch('/api/name-aliases/batch',{
     method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(batch)
   });
   if(!r.ok)throw new Error(await r.text());
   const data=await r.json();
   for(const item of data.entities||[]){
    completed++;
    if(item.error)failed++;
    else if(item.cache_status==='hit')cacheHits++;
    const matching=buttons.filter(b=>b.dataset.aliasType===item.entity_type
       &&b.dataset.aliasId.toLowerCase()===item.id);
    for(const b of matching){
      if(item.error){
        const temporary=/503|502|500|504|429|cooldown|temporarily unavailable|Could not obtain MusicBrainz/.test(item.error);
        b.textContent=temporary?'EN ↻':'EN !';
        b.title=temporary?(item.queued_for_retry?
          'Automatically queued for retry. Reopen this disc later to refresh the displayed alias. ':
          'MusicBrainz temporarily unavailable; retry was not persisted. ')+item.error:item.error;
        b.disabled=false;
      }
      else b.applyAlias(item);
    }
   }
  }catch(error){
   failed+=batch.length;
   completed+=batch.length;
   for(const b of buttons){
    if(batch.some(e=>e.entity_type===b.dataset.aliasType&&e.entity_id===b.dataset.aliasId)){
      b.textContent='EN ↻';b.title='Lookup failed; click to retry later. '+error.message;b.disabled=false;
    }
   }
  }
  message.textContent='English names processed: '+Math.min(i+8,entities.length)+' / '+entities.length;
 }
 message.textContent='English names checked · '+(completed-failed)+' resolved, '+failed+' pending/error, '+cacheHits+' fresh cache hits. EN — = no English alias, EN ↻ = retry later, EN ~ = stale cached alias, EN ! = other lookup error.';
}
async function showMedium(stableId, releaseId){
 const target=document.getElementById('toc-results');
 let area=document.getElementById('medium-results');
 if(!area){area=document.createElement('section');area.id='medium-results';target.append(area)}
 area.replaceChildren();
 const status=document.createElement('p');status.textContent='Loading exact medium…';area.append(status);
 try{
  const r=await fetch('/api/release-medium?'+new URLSearchParams({stable_id:stableId,release_id:releaseId}));
  if(!r.ok)throw new Error(await r.text());
  const info=await r.json();
  status.textContent=info.release_title+' · '+info.total_media+' discs · '+info.status;
  const warning=document.createElement('p');
  warning.textContent='Composer and performers are taken from explicit MusicBrainz relationships, not from the general artist credit. Missing information is shown as undocumented. Physical edition still requires review; nothing is written.';
  area.append(warning);
  if(!info.matched_media.length){
    const p=document.createElement('p');p.textContent='No medium has this exact Disc ID attached to MusicBrainz.';
    area.append(p);return;
  }
  for(const medium of info.matched_media){
    const title=document.createElement('h3');
    title.textContent='Disc '+medium.position+' of '+info.total_media+
       (medium.title?' · '+medium.title:'')+' ('+medium.track_count+' tracks)';
    area.append(title);
    if(!medium.track_count_matches){
      const mismatch=document.createElement('p');
      mismatch.textContent='Track count differs from the inserted disc; manual review required.';
      area.append(mismatch);
    }
    const label=document.createElement('p');
    label.textContent='Work groups only where MusicBrainz explicitly links a movement to a parent work. Otherwise tracks remain separate.';
    area.append(label);
    const tracksByNumber=new Map(medium.tracks.map(t=>[String(t.number||t.position),t]));
    for(const group of (medium.work_groups||[])){
      if(group.parent_work_id){
        const heading=document.createElement('h4');
        heading.textContent=group.parent_work_title||'Untitled work';
        area.append(heading);
        const source=document.createElement('small');
        source.textContent='Verified MusicBrainz work relationship · '+group.tracks.length+' track(s)';
        area.append(source);
      }
      const table=document.createElement('table');table.style.width='100%';
      for(const number of group.tracks){
        const track=tracksByNumber.get(String(number));
        if(!track)continue;
        const tr=document.createElement('tr');
        const composer=track.composers?.map(x=>x.name).join(', ')||'—';
        const cols=[
          track.number||track.position,
          track.title||'Untitled',
          null,null,null
        ];
        for(let i=0;i<cols.length;i++){
          const td=document.createElement('td');
          td.style.padding='6px';td.style.borderBottom='1px solid #324253';
          td.style.verticalAlign='top';
          if(i===2){
            const works=track.work_details||[];
            if(!works.length)td.textContent='Work not linked';
            for(const work of works){
              td.append(aliasNode('work',work.id,work.title||work.id));
            }
          }else if(i===3){
            if(!track.composers?.length)td.textContent='—';
            for(const composer of track.composers||[]){
              if(td.childNodes.length)td.append(document.createTextNode(', '));
              td.append(aliasNode('artist',composer.artist_id,composer.name));
            }
          }else if(i===4){
            if(!track.performers?.length)td.textContent='Not documented';
            for(const performer of track.performers||[]){
              if(td.childNodes.length)td.append(document.createTextNode(', '));
              td.append(aliasNode('artist',performer.artist_id,performer.name));
              if(performer.role){
                const role=document.createElement('span');
                role.textContent=' ('+performer.role+
                  (performer.attributes?.length?', '+performer.attributes.join(', '):'')+')';
                td.append(role);
              }
            }
          }else{td.textContent=String(cols[i]??'')}
          tr.append(td);
        }
        table.append(tr);
      }
      area.append(table);
    }
  }
  enrichNamesAutomatically(area);
 }catch(error){status.textContent='Could not retrieve medium: '+error.message}
}
async function verifyExistingJob(jobOverride=null, targetOverride=null){
 const target=targetOverride||document.getElementById('verify-output');
 const job=(jobOverride||document.getElementById('verify-job').value).trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)){target.textContent='Enter an OSCAR rip job ID (32 hexadecimal characters).';return}
 const headers=requestAuthHeaders('Verify staged rip');
 if(!headers)return;
 target.textContent='Starting verification (FLAC decoding may take some time)…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/verification',{method:'POST',headers});
  if(!r.ok)throw new Error(await r.text());
  async function poll(){
   const response=await fetch('/api/rip/jobs/'+job+'/verification',{headers});
   if(!response.ok)throw new Error(await response.text());
   const data=await response.json();
   if(data.status==='running'||data.status==='not_started'){
    target.textContent='Verification: '+data.status+' (reading stored FLAC files; no optical drive needed).';
    if(data.status==='running')setTimeout(()=>poll().catch(e=>target.textContent=e.message),2500);
    return;
   }
   target.replaceChildren();
   const summary=document.createElement('p');
   summary.textContent='Report: '+data.status+' · '+(data.flac_count??'?')+
      '/'+(data.expected_tracks??'?')+' FLAC · ripping errors: '+(data.ripping_errors??'?')+
      ' · CUE references match: '+(data.cue?.references_match?'yes':'no')+
      (data.error?' · '+data.error:'');
   target.append(summary);
   if(data.tracks?.length){
    const table=document.createElement('table');table.style.width='100%';
    const header=document.createElement('tr');
    for(const h of ['Track','AR v1','AR v2','SHA-256','FLAC decode','Result']){
     const cell=document.createElement('th');cell.textContent=h;cell.style.textAlign='left';
     cell.style.padding='6px';header.append(cell);
    }table.append(header);
    for(const track of data.tracks){
     const tr=document.createElement('tr');
     const ar=v=>{const a=track.accuraterip?.[v];
       return !a?'—':a.status==='accurately_ripped'?'Matched ('+a.confidence+')':a.status};
     for(const value of [track.number,ar('v1'),ar('v2'),
                         track.sha256_matches?'✓':'✗',track.flac_decodes?'✓':'✗',
                         track.checks_passed?'Passed':'Review']){
      const td=document.createElement('td');td.textContent=String(value);
      td.style.padding='6px';td.style.borderBottom='1px solid #324253';tr.append(td);
     }table.append(tr);
    }
    target.append(table);
   }
   const note=document.createElement('p');
   note.textContent=(data.notes||[]).join(' ');
   target.append(note);
  }
  await poll();
 }catch(e){target.textContent='Verification unavailable: '+e.message}
}
document.getElementById('verify-start').onclick=()=>verifyExistingJob();

let reviewedMetadata=null;
function metadataElement(tag,text){const e=document.createElement(tag);e.textContent=String(text??'—');return e;}
document.getElementById('metadata-preview-btn').onclick=async()=>{
 const output=document.getElementById('metadata-output');output.replaceChildren();
 reviewedMetadata=null;
 const job=document.getElementById('metadata-job').value.trim().toLowerCase();
 const release=document.getElementById('metadata-release').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9-]{36}$/.test(release)){
  output.textContent='Enter a valid staging job ID and MusicBrainz release UUID.';return;
 }
 const access=requestAuthHeaders('Inspect MusicBrainz metadata preview');
 if(!access)return;
 output.textContent='Checking completed rip, exact MusicBrainz medium and relationships…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/metadata/preview',{
    method:'POST',headers:{'Content-Type':'application/json',...access},
    body:JSON.stringify({release_id:release})
  });
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();reviewedMetadata=result;
  output.replaceChildren();
  output.append(metadataElement('h3',result.album.title));
  output.append(metadataElement('p','Album artist: '+result.album.artist+
   ' · Release date: '+(result.album.date||'unknown')+
   ' · Disc '+result.disc_number+'/'+result.disc_total));
  output.append(metadataElement('p','Labels: '+(result.album.labels||[]).map(x=>
    (x.name||'?')+' ['+(x.catalog_number||'no catalogue number')+']').join(', ')+
    ' · Barcode: '+(result.album.barcode||'unknown')));
  output.append(metadataElement('p','Proposed FLAC GENRE tags: '+
   ((result.album.genres||[]).join(' · ')||'none available')+
   ' · Source: '+(result.album.genre_source||'no verified genre evidence')+
   '. These genres are included only in the reviewed tagged staging copies.'));
  const link=document.createElement('a');
  link.href='https://musicbrainz.org/release/'+encodeURIComponent(result.release_id);
  link.rel='noopener noreferrer';link.target='_blank';link.textContent='Review exact MusicBrainz release';
  link.style.color='#bfd5ff';output.append(link);
  const table=document.createElement('table');table.style.width='100%';
  const head=document.createElement('tr');
  for(const v of ['#','Track title','Composer / work','Conductor / performers']){
   const th=metadataElement('th',v);th.style.padding='6px';th.style.textAlign='left';head.append(th);
  }table.append(head);
  for(const track of result.tracks){
   const tr=document.createElement('tr');
   const names=(track.composers||[]).map(x=>x.name).join(', ')||'Not documented';
   const works=(track.works||[]).map(x=>x.title).filter(Boolean).join(' / ')||'No work linked';
   const roles=(track.performers||[]).map(x=>x.name+(x.role?' ('+x.role+')':'')).join(', ')||'Not documented';
   for(const value of [track.number,track.tags.TITLE,names+' · '+works,roles]){
    const td=metadataElement('td',value);td.style.padding='6px';
    td.style.verticalAlign='top';td.style.borderBottom='1px solid #324253';tr.append(td);
   }table.append(tr);
  }output.append(table);
  output.append(metadataElement('p',(result.warnings||[]).join(' ')));
  const button=document.createElement('button');button.type='button';
  button.textContent='I reviewed this release — create separate tagged copies';
  button.onclick=async()=>{
   if(!reviewedMetadata||reviewedMetadata.fingerprint!==result.fingerprint)return;
   const confirmText='Create a NEW staging copy of '+result.track_count+' verified FLACs tagged as '+
     result.album.title+' ('+result.release_id+')? This does not publish or modify originals.';
   if(!confirm(confirmText))return;
   const copyAccess=requestAuthHeaders('Create reviewed FLAC copies');
   if(!copyAccess)return;
   button.disabled=true;
   const status=metadataElement('p','Copying and validating tagged FLACs…');output.append(status);
   try{
    const response=await fetch('/api/rip/jobs/'+job+'/metadata/copy',{
      method:'POST',headers:{'Content-Type':'application/json',...copyAccess},
      body:JSON.stringify({release_id:release,fingerprint:result.fingerprint,
                           confirmation:'COPY_TAGGED_TO_STAGING'})
    });
    if(!response.ok)throw new Error(await response.text());
    const started=await response.json();
    async function poll(){
      const r=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+started.copy_id,
                          {headers:copyAccess});
      if(!r.ok)throw new Error(await r.text());
      const task=await r.json();
      if(task.status==='running'){
       status.textContent='Tagging in progress; original FLACs remain unchanged…';
       setTimeout(()=>poll().catch(e=>status.textContent=e.message),3000);
      }else{
       if(task.status==='tagged_copy_ready_for_review'){
        document.getElementById('inspect-job').value=job;
        document.getElementById('inspect-copy').value=started.copy_id;
       }
       status.textContent=task.status+' · '+(task.count??'?')+' tagged FLAC copies'+
        (task.error?' · '+task.error:'')+
        ' · copy ID '+started.copy_id+'. No archive promotion.';
      }
    }await poll();
   }catch(e){status.textContent='Tagged-copy request failed: '+e.message}
   finally{button.disabled=false}
  };
  output.append(button);
 }catch(e){output.textContent='Metadata preview failed: '+e.message}
};


document.getElementById('inspect-start').onclick=async()=>{
 const job=document.getElementById('inspect-job').value.trim().toLowerCase();
 const copy=document.getElementById('inspect-copy').value.trim().toLowerCase();
 const target=document.getElementById('inspect-result');
 target.replaceChildren();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(copy)){
  target.textContent='Enter both 32-character IDs.';return;
 }
 const headers=requestAuthHeaders('Read actual tagged FLAC metadata');
 if(!headers)return;
 target.textContent='Reading the actual FLAC Vorbis comments and comparing saved preview…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+copy+'/inspect',{headers});
  if(!r.ok)throw new Error(await r.text());
  const result=await r.json();
  target.replaceChildren();
  const title=document.createElement('h3');title.textContent=result.album.title||'Unknown album';target.append(title);
  const overview=document.createElement('p');
  overview.textContent=result.track_count+' tracks · '+result.status+
    ' · source: actual saved FLAC tags (not a MusicBrainz lookup)';
  target.append(overview);
  const table=document.createElement('table');table.style.width='100%';
  const h=document.createElement('tr');
  for(const v of ['Track','Title','Composer','Work / grouping','Conductor','Orchestra','Checks']){
   const th=document.createElement('th');th.textContent=v;th.style.textAlign='left';
   th.style.padding='6px';h.append(th);
  }table.append(h);
  for(const track of result.tracks){
   const t=track.tags||{};
   const value=(k)=>Array.isArray(t[k])?t[k].join(', '):'—';
   const row=document.createElement('tr');
   for(const txt of [track.track,value('TITLE'),value('COMPOSER'),
       [value('WORK'),value('GROUPING')].filter(x=>x!=='—').join(' / ')||'—',
       value('CONDUCTOR'),value('ORCHESTRA'),track.status]){
    const td=document.createElement('td');td.textContent=String(txt);
    td.style.padding='6px';td.style.verticalAlign='top';
    td.style.borderBottom='1px solid #324253';row.append(td);
   }
   table.append(row);
   const expanded=document.createElement('tr');
   const cell=document.createElement('td');cell.colSpan=7;
   const details=document.createElement('details');
   const summary=document.createElement('summary');
   summary.textContent='Track '+track.track+' — all stored Vorbis tags and preview differences ('+
    Object.keys(track.differences||{}).length+' differences)';
   details.append(summary);
   const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';
   pre.style.overflowWrap='anywhere';pre.textContent=JSON.stringify({
      tags:track.tags,differences:track.differences,
      sha256_matches:track.sha256_matches,
      audio_streaminfo_md5_matches:track.audio_streaminfo_md5_matches
   },null,2);
   details.append(pre);cell.append(details);expanded.append(cell);table.append(expanded);
  }
  target.append(table);
  const footer=document.createElement('p');footer.textContent=(result.notes||[]).join(' ');
  target.append(footer);
 }catch(error){target.textContent='Inspection failed: '+error.message}
};



async function searchPhysicalReleases(kind){
 const target=document.getElementById('release-search-results');target.replaceChildren();
 const value=document.getElementById(kind==='catalog_number'?'catalog-search':'title-search').value.trim();
 if(!value||value.length>100){target.textContent='Enter a catalog number or a release title.';return}
 target.textContent='Searching MusicBrainz release candidates…';
 try{
  const response=await fetch('/api/release-search?'+new URLSearchParams({[kind]:value}));
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'MusicBrainz unavailable');
  target.replaceChildren();
  const info=document.createElement('p');
  info.textContent=data.releases.length+' candidate(s) from '+data.query_kind+' search. No physical edition or Disc ID has been verified.';
  target.append(info);
  if(!data.releases.length){
   const msg=document.createElement('p');msg.textContent='No release found. Try the alternative title search. Do not use unrelated releases just because their Disc ID matches.';target.append(msg);
  }
  for(const item of data.releases){
   const line=document.createElement('p');const a=document.createElement('a');
   a.href='https://musicbrainz.org/release/'+encodeURIComponent(item.id);
   a.target='_blank';a.rel='noopener noreferrer';
   a.textContent=(item.title||'Untitled')+' · '+(item.artist||'Unknown artist')+
      ' · '+(item.date||'?')+' · '+item.labels.map(x=>(x.name||'')+' '+(x.catalog_number||'')).join(', ');
   line.append(a);target.append(line);
  }
  const warning=document.createElement('p');warning.textContent='Candidates only. Follow up with the separate Physical release comparison using a verified staging job; do not tag from this list alone.';
  target.append(warning);
 }catch(error){target.textContent='Release search failed: '+error.message}
}
document.getElementById('catalog-search-button').onclick=()=>searchPhysicalReleases('catalog_number');
document.getElementById('title-search-button').onclick=()=>searchPhysicalReleases('title');

const recoveryAdvice={
 missing_release:'Missing release: search MusicBrainz by physical catalog number and title. Check the actual booklet, all track names/versions, and Disc ID/TOC. If genuinely absent, submit a new physical Various Artists or artist release through MusicBrainz. Never attach unrelated recordings or invent IDs. You can defer this entirely.',
 wrong_edition:'Wrong edition: compare printed catalog number, barcode, track count and track versions. A shared Disc ID may belong to several physical editions. Do NOT choose the wrong release. Look up the correct release or save for later.',
 ambiguous_edition:'Ambiguous edition: inspect each candidate against the physical CD. Keep all plausible candidates separate. If edition evidence cannot distinguish them, save for review rather than approve automatically.',
 incomplete_metadata:'Incomplete metadata: inspect missing fields and source evidence. Correct the exact MusicBrainz release/recording/work relationship only when independently supported. Preserve uncertainty; defer if source evidence is missing.'
};
function showRecoveryGuidance(){
 const reason=document.getElementById('recovery-reason').value;
 document.getElementById('recovery-guidance').textContent=recoveryAdvice[reason];
}
document.getElementById('recovery-reason').onchange=showRecoveryGuidance;
showRecoveryGuidance();
document.getElementById('recovery-defer').onclick=async()=>{
 const output=document.getElementById('recovery-output');output.replaceChildren();
 const job=document.getElementById('recovery-job').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)){output.textContent='A verified 32-character staging job ID is required to save for later.';return}
 const headers=requestAuthHeaders('Save unresolved CD for later');if(!headers)return;
 try{
  const response=await fetch('/api/rip/jobs/'+job+'/release-review/defer',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({
    reason:document.getElementById('recovery-reason').value,
    title:document.getElementById('recovery-title').value.trim(),
    catalog_number:document.getElementById('recovery-catalog').value.trim(),
    notes:document.getElementById('recovery-notes').value.trim()
   })
  });
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Unable to defer');
  output.textContent='Saved for later: '+data.job_id+'. Original rip, FLACs and CUE remain untouched. Nothing submitted to MusicBrainz.';
 }catch(error){output.textContent='Could not save follow-up: '+error.message}
};
document.getElementById('recovery-list').onclick=async()=>{
 const output=document.getElementById('recovery-output');output.replaceChildren();
 const headers=requestAuthHeaders('List unresolved CD releases');if(!headers)return;
 try{
  const response=await fetch('/api/release-reviews',{headers});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Unable to list reviews');
  if(!data.items.length){output.textContent='No deferred release reviews.';return}
  for(const item of data.items){
   const card=document.createElement('div');card.className='oscar-review-card';
   const title=document.createElement('strong');
   title.textContent=(item.title||'Unidentified CD')+' · '+item.reason;card.append(title);
   const p=document.createElement('p');p.textContent='Job '+item.job_id+
    (item.catalog_number?' · catalog '+item.catalog_number:'')+
    (item.notes?' · '+item.notes:'');card.append(p);
   const complete=document.createElement('button');complete.type='button';complete.textContent='Mark review resolved';
   complete.onclick=async()=>{
    if(!window.confirm('Close this follow-up task? No FLAC or metadata will change.'))return;
    try{
     const done=await fetch('/api/rip/jobs/'+item.job_id+'/release-review/resolve',
      {method:'POST',headers});
     if(!done.ok)throw new Error(await done.text());
     card.remove();
    }catch(e){p.textContent+=' · Could not close: '+e.message}
   };
   card.append(complete);output.append(card);
  }
 }catch(e){output.textContent='Could not load review backlog: '+e.message}
};

document.getElementById('physical-compare-btn').onclick=async()=>{
 const out=document.getElementById('physical-output');out.replaceChildren();
 const job=document.getElementById('physical-job').value.trim().toLowerCase();
 const release=document.getElementById('physical-release').value.trim().toLowerCase();
 const catalog=document.getElementById('physical-catalog').value.trim();
 const barcode=document.getElementById('physical-barcode').value.trim();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9-]{36}$/.test(release)||!catalog){
  out.textContent='Enter the verified rip job ID, exact MusicBrainz release UUID and catalog number printed on your CD.';return;
 }
 if(barcode&&!/^\\d{8,14}$/.test(barcode)){
  out.textContent='Enter only the 8–14 barcode digits, or leave the barcode blank.';return;
 }
 const headers=requestAuthHeaders('Compare the physical CD edition');if(!headers)return;
 out.textContent='Reading MusicBrainz release evidence; no tags or files are changed…';
 try{
  const response=await fetch('/api/rip/jobs/'+job+'/physical-release/compare',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({release_id:release,catalog_number:catalog,barcode:barcode||null})
  });
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Comparison unavailable.');
  out.replaceChildren();
  const info=document.createElement('p');
  info.textContent=(data.release.title||'Unknown release')+' · '+(data.release.artist||'Unknown artist')+' · '+(data.release.date||'No release date');
  out.append(info);
  const evidence=data.physical_evidence;
  const details=[
   'Catalog number matches: '+(evidence.catalog_number_matches?'yes':'NO'),
   'Barcode: '+evidence.barcode_status,
   'Disc ID attached to matching medium: '+(evidence.disc_id_attached_to_matching_medium?'yes':'NO'),
   'Release contains a medium with '+data.verified_tracks+' tracks: '+(evidence.track_count_present_on_release?'yes':'NO'),
   'MusicBrainz catalog numbers: '+data.release.labels.map(x=>(x.name||'Unknown label')+' '+(x.catalog_number||'—')).join('; ')
  ];
  for(const item of details){const p=document.createElement('p');p.textContent=item;out.append(p)}
  const headline=document.createElement('strong');
  headline.textContent=data.status==='review_required'?'Edition evidence needs review':'Evidence consistent; physical edition still requires confirmation';
  out.append(headline);
  for(const issue of data.observations){
   const p=document.createElement('p');p.textContent=issue.code+': '+issue.message;out.append(p);
  }
  const link=document.createElement('a');link.href='https://musicbrainz.org/release/'+encodeURIComponent(data.release_id);
  link.target='_blank';link.rel='noopener noreferrer';link.textContent='Inspect this exact release in MusicBrainz';
  out.append(link);
  const safety=document.createElement('p');
  safety.textContent='Read-only comparison. OSCAR did NOT approve the edition, attach the Disc ID, tag, rename or archive anything.';
  out.append(safety);
 }catch(error){out.textContent='Physical release comparison failed: '+error.message}
};

let v2Current=null;
function parseV2Lines(value,isMovement){
 const result=isMovement?{}:[];
 for(const raw of value.split(String.fromCharCode(10))){
  const line=raw.trim();if(!line)continue;
  const pos=line.indexOf('|');
  if(pos<0)throw new Error('Missing | separator: '+line);
  const left=line.slice(0,pos).trim(),name=line.slice(pos+1).trim();
  if(!name)throw new Error('Missing name: '+line);
  if(isMovement){
   if(!/^\\d+$/.test(left))throw new Error('Invalid track number: '+left);
   result[String(Number(left))]=name;
  }else{
   const m=/^(\\d+)\\s*-\\s*(\\d+)$/.exec(left);
   if(!m)throw new Error('Use start-end | title for every section');
   result.push({start:Number(m[1]),end:Number(m[2]),name});
  }
 }
 return result;
}
document.getElementById('v2-preview').onclick=async()=>{
 const target=document.getElementById('v2-output');target.replaceChildren();v2Current=null;
 const job=document.getElementById('v2-job').value.trim().toLowerCase();
 const source=document.getElementById('v2-source').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(source)){
  target.textContent='Enter both 32-character IDs.';return;
 }
 let sections,movements;
 try{
  sections=parseV2Lines(document.getElementById('v2-sections').value,false);
  movements=parseV2Lines(document.getElementById('v2-movements').value,true);
 }catch(e){target.textContent=e.message;return}
 const access=requestAuthHeaders('Preview reviewed Classical v2 tags');
 if(!access)return;
 target.textContent='Checking completed tagged source and reviewing work identity…';
 try{
  const response=await fetch('/api/rip/jobs/'+job+'/metadata/copies/'+source+'/classical-v2/preview',{
   method:'POST',headers:{'Content-Type':'application/json',...access},
   body:JSON.stringify({sections,movements})
  });
  if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(typeof error.detail==='string'?error.detail:'Unable to preview classical metadata; check the supplied sections.');}
  const data=await response.json();v2Current=data;
  target.replaceChildren();
  const caption=document.createElement('p');caption.textContent=data.track_count+
    ' tracks · '+(data.sections.length?data.sections.map(x=>x.name+' ('+x.start+'–'+x.end+')').join(' · '):'No physical-CD sections assigned; MusicBrainz works shown independently');
  target.append(caption);
  const table=document.createElement('table');table.style.width='100%';
  const head=document.createElement('tr');
  for(const key of ['#','Release section','CD title','MusicBrainz work','Parent work','Movement','EN aliases']){
   const th=document.createElement('th');th.textContent=key;th.style.textAlign='left';
   th.style.padding='5px';head.append(th);
  }table.append(head);
  for(const t of data.tracks){
   const tr=document.createElement('tr');
   for(const value of [t.number,t.release_section,t.title,
    (t.work||[]).join('; ')||'—',(t.work_parent||[]).join('; ')||'—',
    t.movement||'Not documented',Object.entries(t.aliases||{}).map(x=>x[0]+': '+x[1].join(', ')).join('; ')||'—']){
    const td=document.createElement('td');td.textContent=String(value);
    td.style.padding='5px';td.style.borderBottom='1px solid #324253';tr.append(td);
   }table.append(tr);
  }target.append(table);
  const notes=document.createElement('p');notes.textContent=data.warnings.join(' ');target.append(notes);
  const button=document.createElement('button');button.textContent='I reviewed classical metadata — create separate Classical v2 FLAC copies';
  button.type='button';
  button.onclick=async()=>{
   if(!v2Current||v2Current.fingerprint!==data.fingerprint)return;
   if(!confirm('Create a NEW tagged copy of '+data.track_count+' FLACs '+(data.sections.length?'using the reviewed CD sections':'without inventing physical-CD sections')+'? Original files and previous copies stay unchanged.'))return;
   const copyAccess=requestAuthHeaders('Confirm Classical v2 staging copy');if(!copyAccess)return;
   button.disabled=true;
   const note=document.createElement('p');note.textContent='Creating new FLAC copies…';target.append(note);
   try{
    const response=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copy',{
      method:'POST',headers:{'Content-Type':'application/json',...copyAccess},
      body:JSON.stringify({preview:data,confirmation:'COPY_CLASSICAL_V2_TO_STAGING'})
    });
    if(!response.ok)throw new Error(await response.text());
    const started=await response.json();
    async function poll(){
     const r=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copies/'+started.copy_id,
                         {headers:copyAccess});
     if(!r.ok)throw new Error(await r.text());
     const state=await r.json();
     if(state.status==='running'){
      note.textContent='Tagging Classical v2 copy, originals untouched…';
      setTimeout(()=>poll().catch(e=>note.textContent=e.message),2500);
     }else{
      note.textContent=state.status+' · '+(state.count??'?')+' FLAC copies · copy ID '+started.copy_id+
       (state.error?' · '+state.error:'')+'. No archive publication.';
      if(state.status==='classical_v2_ready_for_review'){
       const inspect=document.createElement('button');inspect.type='button';
       inspect.textContent='Inspect actual Classical v2 FLAC tags';
       inspect.onclick=async()=>{
        const readAccess=requestAuthHeaders('Inspect actual Classical v2 tags');
        if(!readAccess)return;
        note.textContent='Reading saved Classical v2 FLAC tags and hashes…';
        try{
         const response=await fetch('/api/rip/jobs/'+job+'/metadata/classical-v2/copies/'+started.copy_id+'/inspect',
          {headers:readAccess});
         if(!response.ok)throw new Error(await response.text());
         const results=await response.json();
         note.textContent='Classical v2 inspection: '+results.status+' · '+results.track_count+' tracks';
         const table=document.createElement('table');table.style.width='100%';
         const head=document.createElement('tr');
         for(const label of ['#','Release section','Title','Work parent','Movement','Aliases','Result']){
          const th=document.createElement('th');th.textContent=label;
          th.style.padding='5px';th.style.textAlign='left';head.append(th);
         }table.append(head);
         for(const t of results.tracks){
          const tr=document.createElement('tr');
          for(const val of [t.number,t.release_section,t.title,
              (t.work_parent||[]).join(', ')||'—',(t.movement||[]).join(', ')||'—',
              Object.entries(t.english_aliases||{}).map(x=>x[0]+': '+x[1].join(', ')).join('; ')||'—',t.status]){
           const td=document.createElement('td');td.textContent=String(val);
           td.style.padding='5px';td.style.borderBottom='1px solid #324253';tr.append(td);
          }table.append(tr);
         }target.append(table);
        }catch(err){note.textContent='Inspection error: '+err.message}
       };target.append(inspect);
      }
     }
    }await poll();
   }catch(e){note.textContent='Classical v2 copy failed: '+e.message}
   finally{button.disabled=false}
  };target.append(button);
 }catch(e){target.textContent='Classical metadata preview failed: '+e.message}
};


/* Tables generated from earlier modules become readable cards on narrow screens.
   Text-only DOM construction prevents injected metadata from becoming HTML. */
function enhanceOscarTables(){
 for(const containerId of ['verify-output','metadata-output','inspect-result','v2-output']){
  const container=document.getElementById(containerId);
  if(!container)continue;
  for(const table of container.querySelectorAll('table:not([data-oscar-cards])')){
   table.setAttribute('data-oscar-cards','1');
   const trs=Array.from(table.querySelectorAll('tr'));
   if(trs.length<2)continue;
   const headings=Array.from(trs[0].querySelectorAll('th')).map(x=>x.textContent.trim());
   const cards=document.createElement('div');cards.className='oscar-mobile-cards';
   let previous=null;
   for(const tr of trs.slice(1)){
    const cells=Array.from(tr.querySelectorAll('td'));
    if(!cells.length)continue;
    if(cells.length===1&&cells[0].colSpan>1&&previous){
      const detail=cells[0].querySelector('details');
      if(detail)previous.append(detail.cloneNode(true));
      continue;
    }
    const card=document.createElement('article');card.className='oscar-review-card';
    const title=document.createElement('strong');
    title.textContent='Track '+(cells[0]?.textContent.trim()||'?')+
      (headings.indexOf('Title')>=0?' · '+(cells[headings.indexOf('Title')]?.textContent.trim()||''):'');
    card.append(title);
    const dl=document.createElement('dl');
    for(let i=1;i<cells.length;i++){
     const name=document.createElement('dt');name.textContent=headings[i]||'Details';
     const value=document.createElement('dd');value.textContent=cells[i].textContent.trim()||'—';
     dl.append(name,value);
    }card.append(dl);cards.append(card);previous=card;
   }
   table.insertAdjacentElement('afterend',cards);
  }
 }
}
const oscarTableObserver=new MutationObserver(()=>enhanceOscarTables());
for(const target of ['verify-output','metadata-output','inspect-result','v2-output']){
 const node=document.getElementById(target);
 if(node)oscarTableObserver.observe(node,{childList:true,subtree:true});
}
function reviewCard(title,bodyText){
 const box=document.createElement('div');box.className='oscar-review-card';
 const heading=document.createElement('strong');heading.textContent=title;
 const text=document.createElement('p');text.textContent=bodyText;
 box.append(heading,text);return box;
}
let reviewedArchivePlan=null;
document.getElementById('publish-preview').onclick=async()=>{
 reviewedArchivePlan=null;
 const plan=document.getElementById('publish-plan');plan.replaceChildren();
 const result=document.getElementById('publish-result');result.replaceChildren();
 document.getElementById('publish-confirmation').hidden=true;
 const job=document.getElementById('publish-job').value.trim().toLowerCase();
 const copy=document.getElementById('publish-copy').value.trim().toLowerCase();
 const kind=document.getElementById('publish-kind').value;
 const profile=document.getElementById('publish-profile').value;
 const includeCover=document.getElementById('publish-cover').checked;
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(copy)){
  plan.textContent='Enter the completed rip job ID and tagged copy ID.';return
 }
 plan.textContent='Preparing archive preview authorization…';
 let headers;
 try{
  headers=requestAuthHeaders('Preview archive publication');
 }catch(error){
  plan.textContent='Archive preview authorization unavailable: '+error.message+
   '. Verify that browser dialogs are allowed for OSCAR.';return;
 }
 if(!headers){
  plan.textContent='Preview not started: OSCAR rip token was not supplied (or the browser dialog was cancelled/blocked). '+
   'Enter the configured OSCAR rip token when prompted, or use explicitly enabled trusted local UI mode.';return;
 }
 plan.textContent='Checking saved verification, tags, naming, CUE and target directory…';
 try{
  const r=await fetch('/api/rip/jobs/'+job+'/archive-publish/preview',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({copy_id:copy,kind,profile,include_cover:includeCover})
  });
  let data;
  try{data=await r.json()}catch(error){
   throw Error('OSCAR returned an unreadable response (HTTP '+r.status+'). Check browser Network and Portainer logs.');
  }
  if(!r.ok){
   const reason=typeof data.detail==='string'?data.detail:'Preview failed';
   throw Error('HTTP '+r.status+': '+reason);
  }
  reviewedArchivePlan={...data,headers,job,copy,kind,profile,includeCover};
  plan.replaceChildren();
  const heading=document.createElement('h3');heading.textContent='Destination: '+data.relative_directory;plan.append(heading);
  const info=document.createElement('p');info.textContent=data.tracks.length+
   ' FLAC files · Disc '+data.disc_number+'/'+data.disc_total+
   ' · Processing '+data.profile+' · '+data.metadata_observations.length+' metadata observations'+
   (data.output_exists?' · DESTINATION ALREADY EXISTS':'');
  plan.append(info);
  if(includeCover){
   const coverNote=document.createElement('p');
   coverNote.textContent='Exact-release cover candidate; compare against the physical booklet/box, including removable stickers:';
   plan.append(coverNote);
   const img=document.createElement('img');
   img.className='oscar-review-cover';
   img.src='https://coverartarchive.org/release/'+encodeURIComponent(data.release_id)+'/front-250';
   img.alt='MusicBrainz physical release cover candidate; requires human confirmation';
   plan.append(img);
  }
  const output=document.createElement('pre');output.className='oscar-review-card';
  output.style.whiteSpace='pre-wrap';output.style.maxHeight='360px';output.style.overflow='auto';
  output.textContent=data.tracks.map(t=>t.filename).join('\\n');plan.append(output);
  const cue=document.createElement('details');
  const summary=document.createElement('summary');summary.textContent='Inspect full proposed album.cue';cue.append(summary);
  const preview=document.createElement('pre');preview.textContent=data.cue;
  preview.style.whiteSpace='pre-wrap';preview.style.overflow='auto';cue.append(preview);plan.append(cue);
  for(const finding of data.metadata_observations){
   const p=document.createElement('p');p.textContent='Review: '+finding.code+' (tracks '+finding.tracks.join(', ')+') — '+finding.message;plan.append(p);
  }
  for(const id of ['publish-physical','publish-cue-approved','publish-observations','publish-cover-approved']){
   document.getElementById(id).checked=false;
  }
  document.getElementById('publish-observation-label').hidden=data.metadata_observations.length===0;
  document.getElementById('publish-cover-label').hidden=!includeCover;
  document.getElementById('publish-confirmation').hidden=!!data.output_exists;
 }catch(error){reviewedArchivePlan=null;plan.textContent='Archive preview unavailable: '+error.message}
};
document.getElementById('publish-start').onclick=async()=>{
 const state=reviewedArchivePlan,output=document.getElementById('publish-result');
 if(!state){output.textContent='Preview the archive first.';return}
 const physical=document.getElementById('publish-physical').checked;
 const cue=document.getElementById('publish-cue-approved').checked;
 const observations=document.getElementById('publish-observations').checked;
 const cover=document.getElementById('publish-cover-approved').checked;
 if(!physical||!cue||(state.metadata_observations.length&&!observations)||(state.includeCover&&!cover)){
  output.textContent='Please review and confirm the physical edition, filenames/CUE, metadata observations and optional cover first.';return
 }
 if(!window.confirm('Publish '+state.tracks.length+' copied FLACs to '+state.relative_directory+'? This creates a new archive folder without modifying originals.'))return;
 const startButton=document.getElementById('publish-start');startButton.disabled=true;
 output.textContent='Publishing verified copies in a separate archive folder…';
 try{
  const response=await fetch('/api/rip/jobs/'+state.job+'/archive-publish/start',{
   method:'POST',headers:{'Content-Type':'application/json',...state.headers},
   body:JSON.stringify({copy_id:state.copy,kind:state.kind,profile:state.profile,
    include_cover:state.includeCover,approve_cover:cover,
    acknowledge_metadata_observations:observations,
    fingerprint:state.fingerprint,confirmation:'PUBLISH_REVIEWED_ARCHIVE'})
  });
  const started=await response.json();
  if(!response.ok)throw Error(typeof started.detail==='string'?started.detail:'Publish refused');
  const poll=async()=>{
   const r=await fetch('/api/rip/jobs/'+state.job+'/archive-publish/'+started.publish_id,
    {headers:state.headers});
   if(!r.ok)throw Error(await r.text());
   const data=await r.json();
   if(data.status==='running'){
    output.textContent='Archive publication '+started.publish_id+': running; no source files are modified.';
    setTimeout(async()=>{try{await poll()}catch(e){output.textContent='Status lookup failed: '+e.message}},3000);
   }else if(data.status==='published_verified'){
    output.textContent='Archive published and verified: '+data.relative_directory+
      ' · '+data.file_count+' FLACs · Original staging preserved. Manifest SHA-256: '+data.manifest_sha256;
    document.getElementById('publish-confirmation').hidden=true;
   }else output.textContent='Publication failed: '+(data.error||'Unknown error')+
      '. Original rip and tags were preserved. Inspect partial hidden folder before attempting again.';
  };
  await poll();
 }catch(error){output.textContent='Archive publication could not start: '+error.message}
 finally{startButton.disabled=false}
};

document.getElementById('review-start').onclick=async()=>{
 const job=document.getElementById('review-job').value.trim().toLowerCase();
 const copy=document.getElementById('review-copy').value.trim().toLowerCase();
 const kind=document.getElementById('review-kind').value;
 const profile=document.getElementById('review-profile').value;
 const output=document.getElementById('review-output');output.replaceChildren();
 if(!/^[a-f0-9]{32}$/.test(job)||!/^[a-f0-9]{32}$/.test(copy)){
  output.textContent='Enter valid 32-character rip and tagged-copy IDs.';return;
 }
 const headers=requestAuthHeaders('Review staged archive metadata and CUE');
 if(!headers)return;
 output.textContent='Reading staged FLAC metadata, looking up cover candidate and preparing CUE…';
 try{
  const url='/api/rip/jobs/'+job+'/archive-review/'+copy+'?'+new URLSearchParams({kind,profile});
  const response=await fetch(url,{headers});
  if(!response.ok)throw new Error(await response.text());
  const data=await response.json();output.replaceChildren();
  const top=document.createElement('h3');top.textContent=data.album.title||'Album review';output.append(top);
  const profileNote=document.createElement('p');profileNote.textContent='Processing profile: '+data.music_profile.name+
   ' ('+data.music_profile.source+')'+(data.music_profile.requires_review?' · Profile classification remains reviewable':'');
  output.append(profileNote);
  const small=document.createElement('p');small.textContent=(data.album.artist||'Unknown album artist')+
   ' · '+(data.album.date||'Undated')+' · '+data.tracks.length+' tracks · '+
   (data.album.catalog_numbers||[]).join(', ');output.append(small);
  const sections=document.createElement('div');sections.className='oscar-review-grid';
  const flags=data.consistency.flags||[];
  sections.append(reviewCard('Consistency',data.consistency.status+' · '+flags.length+
    ' review items. Shared work IDs do not automatically mean audio or recording duplication.'));
  sections.append(reviewCard('CUE',data.cue.status+
    ' · '+(data.cue.track_count??'?')+' tracks. Original INDEX and PREGAP lines kept, no new indexes invented.'));
  sections.append(reviewCard('Cover Art Archive',data.cover_art.status+
    ' · candidate tied to selected MusicBrainz physical release; check against booklet.'));
  output.append(sections);
  if(data.cover_art.thumbnail_url){
   const photo=document.createElement('img');photo.className='oscar-review-cover';
   photo.src=data.cover_art.thumbnail_url;photo.alt='Cover candidate; inspect physical edition';
   photo.loading='lazy';output.append(photo);
  }
  const warning=document.createElement('p');warning.className='oscar-review-note';
  warning.textContent='This is a review, not approval. MusicBrainz Work is not Recording. No AcoustID, CTDB or automatic publishing.';
  output.append(warning);
  const reviewTitle=document.createElement('h4');reviewTitle.textContent='Metadata observations ('+flags.length+')';
  output.append(reviewTitle);
  if(!flags.length)output.append(reviewCard('No automatic conflicts','Nothing was flagged from available evidence; this is not proof that every MusicBrainz link is correct.'));
  for(const flag of flags){
   output.append(reviewCard('Tracks '+flag.tracks.join(', ')+' · '+flag.code,
                            flag.message));
  }
  const cueBox=document.createElement('details');
  const summary=document.createElement('summary');summary.textContent='Preview complete CUE without rewriting original';
  cueBox.append(summary);
  if(data.cue.text){
   const preview=document.createElement('pre');
   preview.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:440px;overflow:auto';
   preview.textContent=data.cue.text;cueBox.append(preview);
   const copyBtn=document.createElement('button');copyBtn.type='button';copyBtn.textContent='Copy CUE preview';
   copyBtn.onclick=()=>navigator.clipboard.writeText(data.cue.text);
   cueBox.append(copyBtn);
   if(data.cue.archive_cue_proposal){
    const proposed=document.createElement('details');
    const title=document.createElement('summary');
    title.textContent='Proposed future archive CUE (requires matching renamed FLAC files)';
    proposed.append(title);
    const info=document.createElement('p');
    info.textContent='This is a filename proposal ONLY. The target FLAC files have not been created or renamed; do not use this CUE as an archive file yet.';
    proposed.append(info);
    const planned=document.createElement('pre');
    planned.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:440px;overflow:auto';
    planned.textContent=data.cue.archive_cue_proposal;proposed.append(planned);
    const copyPlanned=document.createElement('button');copyPlanned.type='button';
    copyPlanned.textContent='Copy proposed archive CUE';
    copyPlanned.onclick=()=>navigator.clipboard.writeText(data.cue.archive_cue_proposal);
    proposed.append(copyPlanned);cueBox.append(proposed);
   }
  }else cueBox.append(reviewCard('CUE needs attention',data.cue.reason||'Cannot preview the original CUE safely'));
  output.append(cueBox);
  const heading=document.createElement('h4');heading.textContent='Track overview';output.append(heading);
  const cards=document.createElement('div');cards.className='oscar-review-grid';
  for(const track of data.tracks){
   const titles=[track.number+'. '+track.title,
    'Artist: '+(track.artist||'Unknown'),
    'Recording: '+(track.recording_id||'Not linked'),
    'Works: '+(track.work_names||[]).join('; '),
    'FLAC: '+track.length_seconds+' s'];
   const card=reviewCard(titles[0],titles.slice(1).join(' · '));
   cards.append(card);
  }output.append(cards);
 }catch(e){output.textContent='Review could not finish: '+e.message}
};
document.getElementById('multi-refresh').onclick=async()=>{
 const output=document.getElementById('multi-output');output.textContent='Reading optical drives…';
 const headers=requestAuthHeaders('Inspect parallel optical drives');
 if(!headers)return;
 try{
  const r=await fetch('/api/rip/dashboard',{headers});
  if(!r.ok)throw new Error(await r.text());
  const data=await r.json();output.replaceChildren();
  const status=document.createElement('p');
  status.textContent=data.active_count+'/'+data.max_concurrent_rips+' running · '+
   data.slots_available+' available slots · '+data.drives.length+' configured enabled drives.';
  output.append(status);
  const grid=document.createElement('div');grid.className='oscar-review-grid';
  for(const drive of data.drives){
   const card=reviewCard(drive.label,drive.status+' · '+(drive.device||'not detected')+
    ' · '+(drive.offset_set?'offset set':'offset not set')+
    (drive.job?' · last rip '+drive.job.id+' ('+drive.job.status+')':''));
   if(drive.present&&drive.offset_set&&drive.status==='ready'){
    const button=document.createElement('button');button.textContent='Rip this drive to staging';
    button.onclick=()=>startTestRip(drive.stable_id,drive.label);card.append(button);
   }
   grid.append(card);
  }output.append(grid);
  output.append(reviewCard('Multidrive safety',data.note));
 }catch(e){output.textContent='Drive dashboard unavailable: '+e.message}
};

async function findArchivedTracks(){
 const out=document.getElementById('tracks-output');
 const headers=requestAuthHeaders('Search archived track metadata');if(!headers)return;
 out.textContent='Searching verified archive track index…';
 const query=new URLSearchParams({search:document.getElementById('track-search').value.trim(),
  role:document.getElementById('track-role').value});
 try{
  const response=await fetch('/api/collection/tracks?'+query,{headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Track lookup failed');
  out.replaceChildren();
  const summary=document.createElement('p');
  summary.textContent=data.total+' indexed track(s), showing '+data.tracks.length+'.';out.append(summary);
  for(const track of data.tracks){
   const info=reviewCard(track.track_number+'. '+(track.title||track.filename),
    track.artist+' — '+track.album+' · '+(track.label||'Unknown label'));
   const credits=document.createElement('p');
   credits.textContent=track.credits.map(x=>x.person_name+' ('+x.credit_role+
      (x.role_detail?': '+x.role_detail:'')+')').join(' · ')||'No explicit performer relationships';
   info.append(credits);
   const works=document.createElement('p');
   works.textContent=track.works.map(x=>x.work_title+
      (x.musicbrainz_work_id?' [MB work '+x.musicbrainz_work_id+']':'')).join(' · ')||'No explicit Work relationship';
   info.append(works);
   const source=document.createElement('small');
   source.textContent='Metadata source: archived FLAC Vorbis comments; no inferred credits';
   info.append(source);out.append(info);
  }
 }catch(error){out.textContent='Track search failed: '+error.message}
}
document.getElementById('track-search-btn').onclick=findArchivedTracks;
document.getElementById('collection-index-tracks').onclick=async()=>{
 const out=document.getElementById('tracks-output');
 const headers=requestAuthHeaders('Index archived FLAC metadata');if(!headers)return;
 out.textContent='Checking archive FLAC hashes and indexing tags…';
 try{
  const response=await fetch('/api/collection/index-tracks',{method:'POST',headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Indexing failed');
  await findArchivedTracks();
  const note=document.createElement('p');
  note.textContent=data.tracks_indexed+' tracks indexed; '+data.albums_skipped+' albums skipped. No source audio modified.';
  out.prepend(note);
 }catch(error){out.textContent='Track indexing failed: '+error.message}
};

async function showArchiveProposals(){
 const box=document.getElementById('archive-scan-result');
 const headers=requestAuthHeaders('Read archived metadata proposals');if(!headers)return;
 const response=await fetch('/api/collection/archive-metadata/proposals',{headers});
 const data=await response.json();
 if(!response.ok)throw new Error(data.detail||'Proposal list unavailable');
 box.replaceChildren();
 const status=document.createElement('p');status.textContent=data.count+' pending metadata proposal(s).';
 box.append(status);
 for(const item of data.items){
  const article=document.createElement('section');
  const heading=document.createElement('strong');
  heading.textContent=(item.scope==='track'?'Track '+item.track:'Album')+' · '+item.field;
  article.append(heading);
  const values=document.createElement('p');
  values.textContent='Archive: '+JSON.stringify(item.before)+' · MusicBrainz: '+JSON.stringify(item.after);
  article.append(values);
  const loc=document.createElement('small');
  loc.textContent=item.archive_path+' · '+item.source_url;
  article.append(loc);
  for(const [choice,label] of [['accept','Accept proposal (approval only)'],['ignore','Ignore this exact change']]){
   const button=document.createElement('button');button.type='button';button.textContent=label;
   article.append(button);
   button.onclick=async()=>{
    if(!window.confirm(choice==='accept'
     ? 'Record approval for a future separately reviewed archive migration? NO FLAC or Collection metadata will be changed.'
     : 'Ignore this exact proposed value on future scans? A different value can be proposed later.'))return;
    const auth=requestAuthHeaders('Record archive metadata decision');if(!auth)return;
    button.disabled=true;
    try{
     const response=await fetch('/api/collection/archive-metadata/decision',{
      method:'POST',headers:{'Content-Type':'application/json',...auth},
      body:JSON.stringify({fingerprint:item.fingerprint,choice})
     });
     const outcome=await response.json();
     if(!response.ok)throw new Error(outcome.detail||'Decision refused');
     await showArchiveProposals();
    }catch(error){button.disabled=false;const err=document.createElement('p');
     err.textContent='Decision not saved: '+error.message;article.append(err)}
   };
  }
  box.append(article);
 }
}
async function previewGenreEvidence(){
 const output=document.getElementById('genre-evidence-result');
 const path=document.getElementById('archive-scan-album').value;
 if(!path){output.textContent='Select an indexed published archive album first.';return}
 const value=document.getElementById('genre-evidence-discogs').value.trim();
 if(value&&!/^[0-9]{1,8}$/.test(value)){output.textContent='Discogs release ID must be a positive number.';return}
 const auth=requestAuthHeaders('Compare archival genre evidence');if(!auth)return;
 output.textContent='Reading verified archive and provider genre evidence (read-only)…';
 const body={archive_path:path,
  workflow:document.getElementById('genre-evidence-workflow').value};
 if(value)body.discogs_release_id=Number(value);
 try{
  const response=await fetch('/api/collection/genre-evidence/preview',{
   method:'POST',headers:{'Content-Type':'application/json',...auth},
   body:JSON.stringify(body)
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.detail||'Genre evidence unavailable');
  output.replaceChildren();
  const summary=document.createElement('p');
  summary.textContent='Read-only genre evidence · '+result.independent_sources_with_genres+
   ' independent provider(s) with usable genre data · '+
   result.sources_without_applicable_genres+' without applicable genres. No archive writes.';
  output.append(summary);
  for(const finding of result.findings){
   const p=document.createElement('p');
   p.textContent=finding.genre+' · '+finding.confidence+' · '+
    finding.agreement_fraction+' independent applicable sources ('+
    finding.agreement_percent+'% agreement; not a probability)';
   output.append(p);
  }
  if(!result.findings.length){
   const p=document.createElement('p');p.textContent='No supported genres found. Keep Unclassified unless independently reviewed.';output.append(p);
  }
  for(const claim of result.sources){
   const p=document.createElement('p');
   p.textContent=claim.provider+' / '+claim.scope+' · '+claim.status+
    ' · Original: '+(claim.raw_genres.join('; ')||'(no genre)')+
    ' · Normalized: '+(claim.genres.join('; ')||'(none)')+
    ' · Identity: '+claim.identity_evidence+' · Independence group: '+claim.independence_group;
   const link=document.createElement('a');link.href=claim.reference;
   link.target='_blank';link.rel='noopener noreferrer';link.textContent=' · Open source';
   p.append(link);output.append(p);
  }
  const note=document.createElement('p');note.textContent=result.note;
  output.append(note);
 }catch(error){output.textContent='Read-only genre comparison could not complete: '+error.message}
}
document.getElementById('genre-evidence-preview').onclick=previewGenreEvidence;
async function runArchiveScan(mode){
 const box=document.getElementById('archive-scan-result');
 const path=document.getElementById('archive-scan-album').value;
 if(!path){box.textContent='Select a published archive album first.';return}
 const headers=requestAuthHeaders('Scan published archive for metadata');if(!headers)return;
 box.textContent='Verifying archive hashes and comparing MusicBrainz metadata…';
 try{
  const response=await fetch('/api/collection/archive-metadata/scan',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({mode,archive_path:path})
  });
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Archive scan failed');
  await showArchiveProposals();
  const info=document.createElement('p');
  info.textContent='Scan found '+data.detected+' value difference(s), of which '+
   data.suppressed+' already accepted/ignored; archive files untouched.';
  box.prepend(info);
 }catch(error){box.textContent='Archive scan safely stopped: '+error.message}
}
async function showArchiveRevisionOperations(){
 const out=document.getElementById('archive-revision-output');
 const headers=requestAuthHeaders('Read archive revision journal');if(!headers)return;
 try{
  const response=await fetch('/api/collection/archive-revisions/operations',{headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Revision journal unavailable');
  out.replaceChildren();
  const p=document.createElement('p');
  p.textContent=data.items.length+' recorded archive revision operation(s).';out.append(p);
  for(const entry of data.items){
   const item=document.createElement('p');
   item.textContent=entry.status+' · '+entry.source_path+' → '+entry.dest_path+
    (entry.cleanup_status==='completed'?' · original generation permanently cleaned':
     ' · original retained: '+entry.backup_path);
   out.append(item);
   if(entry.cleanup_status){
    const state=document.createElement('span');
    state.textContent=' · retained history cleanup: '+entry.cleanup_status+
     (entry.cleaned_at?' ('+entry.cleaned_at+')':'');
    item.append(state);
   }
   if(entry.status==='completed'&&!entry.cleanup_status){
    const verification=document.createElement('p');out.append(verification);
    const verifyButton=document.createElement('button');
    verifyButton.type='button';verifyButton.textContent='Verify';
    const cleanButton=document.createElement('button');
    cleanButton.type='button';cleanButton.textContent='Clean (verified only)';
    const bothButton=document.createElement('button');
    bothButton.type='button';bothButton.textContent='Verify & Clean';
    item.append(verifyButton,cleanButton,bothButton);
    let verifiedReceipt=null;
    cleanButton.disabled=true;
    async function runVerify(){
     const auth=requestAuthHeaders('Independently verify both archive generations');if(!auth)return null;
     verifyButton.disabled=true;bothButton.disabled=true;cleanButton.disabled=true;
     verifiedReceipt=null;
     verification.textContent='Verifying both generations: all FLAC tags, SHA-256, audio, CUE/evidence, Collection…';
     try{
      const response=await fetch('/api/collection/archive-revisions/verify',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({operation_id:entry.operation_id})
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.detail||'Archive verification failed');
      verifiedReceipt=result.cleanup_eligible ? result.verification_fingerprint : null;
      verification.textContent='VERIFIED: '+result.revised_flacs_verified+' new FLACs + '+
       result.original_flacs_verified+' originals, '+result.approved_fields_verified+
       ' approved change(s); CUE/evidence and Collection OK. No archive bytes changed.'+
       (result.historical_revision ?
        ' Historical generation (superseded by a later revision); cleanup prohibited.' : '');
      cleanButton.disabled=!result.cleanup_eligible;
      return verifiedReceipt;
     }catch(error){
      verification.textContent='VERIFY FAILED: '+error.message+
       '. Nothing has been deleted.';
      return null;
     }finally{verifyButton.disabled=false;bothButton.disabled=false}
    }
    async function runClean(receipt){
     if(!receipt){verification.textContent='First run Verify successfully.';return}
     if(!window.confirm(
      'PERMANENT deletion of ONE retained original archive generation? '+
      'This removes the original CUE, FLACs and provenance; OSCAR cannot restore it. '+
      'Make an external backup first. This cannot be undone.'
     ))return;
     const typed=window.prompt('Type DELETE ORIGINAL to confirm permanent loss of this archived version.');
     if(typed!=='DELETE ORIGINAL')return;
     if(!window.confirm(
      'Confirm you have a RESTORABLE EXTERNAL BACKUP of this original version, '+
      'outside the OSCAR archive and media-server library. Without that backup, Cancel.'
     ))return;
     const auth=requestAuthHeaders('Permanently clean a verified original archive version');
     if(!auth)return;
     verifyButton.disabled=true;cleanButton.disabled=true;bothButton.disabled=true;
     verification.textContent='Re-verifying the COMPLETE original and new publications under lock before cleanup…';
     try{
      const response=await fetch('/api/collection/archive-revisions/clean',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({
        operation_id:entry.operation_id,
        verification_fingerprint:receipt,
        confirmation:'PERMANENTLY_DELETE_VERIFIED_ORIGINAL_VERSION',
        external_backup_confirmed:true
       })
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.detail||'Cleanup refused');
      verification.textContent='Cleaned verified retained original: '+result.original_version_removed+
       '. Current album was not modified. External backup is the only recovery source.';
      await showArchiveRevisionOperations();
     }catch(error){
      verification.textContent='CLEAN NOT CONFIRMED: '+error.message+
       '. Inspect revision/cleanup journal before any further attempt.';
      verifyButton.disabled=false;bothButton.disabled=false;
     }
    }
    verifyButton.onclick=()=>runVerify();
    cleanButton.onclick=()=>runClean(verifiedReceipt);
    bothButton.onclick=async()=>{
     const receipt=await runVerify();
     if(receipt)await runClean(receipt);
    };
   }
   if(entry.status==='prepared'){
    const button=document.createElement('button');
    button.type='button';button.textContent='Reconcile interrupted revision';
    item.append(button);
    button.onclick=async()=>{
     if(!window.confirm('Reconcile this interrupted journal operation? OSCAR verifies both archive versions and never deletes the original.'))return;
     const auth=requestAuthHeaders('Reconcile archive revision');if(!auth)return;
     button.disabled=true;
     try{
      const response=await fetch('/api/collection/archive-revisions/reconcile',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({operation_id:entry.operation_id})
      });
      const result=await response.json();
      if(!response.ok)throw new Error(result.detail||'Could not reconcile');
      await showArchiveRevisionOperations();
     }catch(error){button.disabled=false;const warning=document.createElement('span');
      warning.textContent=' · '+error.message;item.append(warning)}
    };
   }
  }
 }catch(error){out.textContent='Revision journal: '+error.message}
}
async function previewCoordinatedBoxset(field){
 const out=document.getElementById('archive-revision-output');
 const selected=document.getElementById('archive-scan-album');
 const release=selected.selectedOptions[0]?.dataset.releaseId;
 if(!release){out.textContent='Select a disc in Advanced · scan only one archive album first.';return}
 const headers=requestAuthHeaders('Read-only coordinated boxset metadata review');
 if(!headers)return;
 out.textContent='Verifying all archived CD media and reviewed MusicBrainz '+field+' values…';
 try{
  const response=await fetch('/api/collection/archive-revisions/boxset-preview',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({release_id:release,field})
  });
  const data=await response.json();
  if(!response.ok)throw Error(data.detail||'Boxset review unavailable');
  out.replaceChildren();
  const h=document.createElement('h4');h.textContent='Multidisc release '+(field==='GENRE'?'genre':'label')+' review (read-only)';out.append(h);
  for(const line of [
   'MusicBrainz release: '+data.release_id,
   'Archived discs: '+data.present_disc_numbers.join(', ')+' of '+data.disc_total,
   'Missing discs: '+(data.missing_disc_numbers.join(', ')||'none'),
   'Reviewed '+field+': '+(field==='GENRE'?data.reviewed_genres:data.reviewed_labels).join('; '),
   'All existing discs reviewed: '+(data.all_present_discs_reviewed?'yes':'no'),
   data.note
  ]){const p=document.createElement('p');p.textContent=line;out.append(p)}
  for(const disc of data.disc_reviews){
   const p=document.createElement('p');
   p.textContent='Disc '+disc.disc+' · '+disc.track_count+' tracks · '+
    (field==='GENRE'?disc.genre_status:disc.label_status)+
    ' · FLAC '+field+': '+((field==='GENRE'?disc.existing_flac_genres:disc.existing_flac_labels).join('; ')||'(missing)')+
    ' · '+disc.archive_path;out.append(p);
  }
  if(data.apply_supported){
   const apply=document.createElement('button');
   apply.type='button';apply.textContent='Apply coordinated boxset revision (opt-in; originals retained)';
   out.append(apply);
   apply.onclick=async()=>{
    const header=requestAuthHeaders('Apply coordinated boxset migration');if(!header)return;
    const agreed=window.confirm('This changes ALL reviewed present discs as one recoverable group. Original versions remain retained. A partial filesystem promotion may require explicit recovery. Proceed?');
    if(!agreed)return;
    const typed=window.prompt('To approve the coordinated, versioned group migration, type APPLY_COORDINATED_BOXSET_REVISION');
    if(typed!=='APPLY_COORDINATED_BOXSET_REVISION')return;
    apply.disabled=true;
    try{
     const response=await fetch('/api/collection/archive-revisions/boxset-apply',{
      method:'POST',headers:{'Content-Type':'application/json',...header},
      body:JSON.stringify({release_id:data.release_id,field,fingerprint:data.fingerprint,confirmation:typed})
     });
     const started=await response.json();
     if(!response.ok)throw Error(started.detail||'Boxset migration could not start');
     const note=document.createElement('p');note.textContent='Boxset operation running; verifying all candidate FLACs before publication…';out.append(note);
     let task=started;
     while(task.status==='running'){
      await new Promise(resolve=>setTimeout(resolve,1500));
      const resp=await fetch('/api/collection/archive-revisions/boxset-workers/'+started.task_id,{headers:header});
      task=await resp.json();
      if(!resp.ok)throw Error(task.detail||'Worker status unavailable; inspect durable group journal');
     }
     if(task.status!=='completed')throw Error(task.error||'Group migration failed');
     note.textContent='Group '+task.result.operation_id+' · '+task.status+
      ' · discs '+task.result.discs.join(', ')+'. Original generations retained.';
    }catch(error){const p=document.createElement('p');p.textContent='Group migration stopped: '+error.message+'. Inspect group history; do not manually move/delete archive files.';out.append(p)}
    finally{apply.disabled=false}
   };
  }
 }catch(error){out.textContent='Read-only boxset preview blocked: '+error.message}
}
document.getElementById('archive-boxset-label-preview').onclick=()=>previewCoordinatedBoxset('LABEL');
document.getElementById('archive-boxset-genre-preview').onclick=()=>previewCoordinatedBoxset('GENRE');
document.getElementById('archive-boxset-history').onclick=async()=>{
 const out=document.getElementById('archive-revision-output');
 const headers=requestAuthHeaders('Boxset migration journal');if(!headers)return;
 try{
  const response=await fetch('/api/collection/archive-revisions/boxset-operations',{headers});
  const data=await response.json();
  if(!response.ok)throw Error(data.detail||'Could not load group history');
  out.replaceChildren();
  const heading=document.createElement('h4');heading.textContent='Coordinated multidisc revision journal';out.append(heading);
  for(const operation of data.items){
   const text=document.createElement('p');
   text.textContent=operation.operation_id+' · '+operation.status+
    ' · release '+operation.release_id+(operation.error?' · '+operation.error:'');
   out.append(text);
   if(operation.status==='completed'){
    const verify=document.createElement('button');verify.type='button';
    verify.textContent='Verify original, audio, metadata and Collection (read-only)';
    out.append(verify);
    verify.onclick=async()=>{
     const auth=requestAuthHeaders('Verify completed multidisc revision');if(!auth)return;
     verify.disabled=true;
     const report=document.createElement('pre');report.textContent='Verifying both generations…';
     out.append(report);
     try{
      const resp=await fetch('/api/collection/archive-revisions/boxset-verify',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({operation_id:operation.operation_id})
      });
      const result=await resp.json();
      if(!resp.ok)throw Error(result.detail||'Unable to verify group');
      report.textContent='Integrity '+result.status.toUpperCase()+
       '\\n'+result.verified_discs.map(d=>'Disc '+d.disc+': '+d.status+
        ' ('+d.tracks+' tracks)'+
        (d.observations.length?' · '+d.observations.join('; '):'')).join('\\n')+
       '\\n'+result.note;
     }catch(error){report.textContent='Verification unavailable: '+error.message}
     finally{verify.disabled=false}
    };
   }
   if(operation.status==='prepared'){
    const reconcile=document.createElement('button');reconcile.type='button';
    reconcile.textContent='Reconcile interrupted group (opt-in)';out.append(reconcile);
    reconcile.onclick=async()=>{
     const auth=requestAuthHeaders('Recover interrupted group');if(!auth)return;
     if(!window.confirm('Inspect the original, staging and promoted disc generations before proceeding. Reconcile only this interrupted group?'))return;
     try{
      const resp=await fetch('/api/collection/archive-revisions/boxset-reconcile',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({operation_id:operation.operation_id})
      });
      const result=await resp.json();
      if(!resp.ok)throw Error(result.detail||'Reconciliation blocked');
      text.textContent=operation.operation_id+' · '+result.status;
     }catch(error){text.textContent='Reconciliation blocked: '+error.message}
    };
   }
  }
  if(!data.items.length){const p=document.createElement('p');p.textContent='No coordinated boxset operations recorded.';out.append(p)}
 }catch(error){out.textContent='Boxset history unavailable: '+error.message}
};
document.getElementById('archive-revision-operations').onclick=showArchiveRevisionOperations;
document.getElementById('archive-revision-preview').onclick=async()=>{
 const out=document.getElementById('archive-revision-output');
 const source=document.getElementById('archive-scan-album').value;
 if(!source){
  out.textContent='Select an album in Advanced · scan only one archive album, then preview its approved migration.';return;
 }
 const headers=requestAuthHeaders('Preview approved archive migration');if(!headers)return;
 out.textContent='Verifying archive integrity and approved current MusicBrainz metadata…';
 try{
  const response=await fetch('/api/collection/archive-revisions/preview',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({archive_path:source})
  });
  const plan=await response.json();if(!response.ok)throw new Error(plan.detail||'Migration preview unavailable');
  out.replaceChildren();
  const title=document.createElement('h4');title.textContent='Verified archive migration preview';out.append(title);
  for(const line of [
   'Original: '+plan.source_path,'New archive: '+plan.dest_path,
   'Catalog number: '+(plan.catalog_number||'(none)'),
   'Reviewed change(s): '+plan.accepted_changes.length,
   'Tracks: '+plan.track_count,
   'Original publication: '+plan.original_publish_id,
   plan.note]){
   const p=document.createElement('p');p.textContent=line;out.append(p);
  }
  const button=document.createElement('button');
  button.type='button';button.textContent='Apply approved archive revision (opt-in required)';
  out.append(button);
  button.onclick=async()=>{
   const message='Apply '+plan.accepted_changes.length+' previously approved changes to NEW VERIFIED FLAC copies? Original generation will be retained in archive history. The archive folder/Collection reference may change. No staging is required. Requires OSCAR_ENABLE_ARCHIVE_REVISIONS=1.';
   if(!window.confirm(message))return;
   const auth=requestAuthHeaders('Apply approved archive revision');if(!auth)return;
   button.disabled=true;
   try{
    const response=await fetch('/api/collection/archive-revisions/apply',{
     method:'POST',headers:{'Content-Type':'application/json',...auth},
     body:JSON.stringify({archive_path:source,fingerprint:plan.fingerprint,
      confirmation:'APPLY_VERIFIED_ARCHIVE_REVISION'})
    });
    const task=await response.json();
    if(!response.ok)throw new Error(task.detail||'Archive revision refused');
    const row=document.createElement('p');out.append(row);
    async function poll(){
     const response=await fetch('/api/collection/archive-revisions/workers/'+task.task_id,{headers:auth});
     const status=await response.json();
     if(!response.ok)throw new Error(status.detail||'Revision status unavailable');
     row.textContent='Archive revision: '+status.status+
      (status.error?' · '+status.error:'')+
      (status.result?' · '+status.result.archive_path+' · original retained at '+status.result.original_retained_at:'');
     if(status.status==='running'){
      window.setTimeout(()=>poll().catch(error=>{row.textContent='Check durable revision journal: '+error.message}),2000);
     }else if(status.status==='completed'){
      await fetchLocalCollection();
      await showArchiveRevisionOperations();
     }else button.disabled=false;
    }
    await poll();
   }catch(error){button.disabled=false;const p=document.createElement('p');
    p.textContent='Revision stopped safely: '+error.message+'; inspect archive revision journal.';out.append(p)}
  };
 }catch(error){out.textContent='Migration preview blocked: '+error.message}
};

let archiveBulkPoll=null;
async function updateArchiveBulkProgress(scanId, headers){
 const box=document.getElementById('archive-scan-result');
 try{
  const response=await fetch('/api/collection/archive-metadata/scan-all/'+scanId,{headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Scan status unavailable');
  box.replaceChildren();
  const summary=document.createElement('p');
  summary.textContent='Archive '+data.mode+' scan · '+data.processed+'/'+data.total+
   ' albums checked · '+data.detected+' differences · '+data.suppressed+
   ' already decided · '+data.failed+' failed · status: '+data.status;
  box.append(summary);
  const bar=document.createElement('progress');
  bar.max=data.total;bar.value=data.processed;bar.style.width='100%';box.append(bar);
  for(const failure of data.errors){
   const row=document.createElement('p');
   row.textContent='Skipped '+failure.archive_path+' · '+failure.error;
   box.append(row);
  }
  if(data.status==='running'){
   archiveBulkPoll=window.setTimeout(()=>updateArchiveBulkProgress(scanId,headers),1500);
  }else{
   archiveBulkPoll=null;
   const button=document.createElement('button');
   button.type='button';button.textContent='Review pending metadata proposals';
   box.append(button);button.onclick=()=>showArchiveProposals();
  }
 }catch(error){
  archiveBulkPoll=null;
  box.textContent='Scan progress unavailable: '+error.message+
    '. Previously saved metadata decisions and proposals remain in SQLite.';
 }
}
async function runArchiveBulkScan(mode){
 const box=document.getElementById('archive-scan-result');
 const headers=requestAuthHeaders('Scan entire OSCAR archive');if(!headers)return;
 if(archiveBulkPoll){window.clearTimeout(archiveBulkPoll);archiveBulkPoll=null}
 box.textContent='Starting archive-wide metadata scan…';
 try{
  const response=await fetch('/api/collection/archive-metadata/scan-all',{
   method:'POST',headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({mode})
  });
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Could not start full archive scan');
  await updateArchiveBulkProgress(data.scan_id,headers);
 }catch(error){box.textContent='Archive scan safely stopped: '+error.message}
}
document.getElementById('archive-scan-additions').onclick=()=>runArchiveBulkScan('additions');
document.getElementById('archive-scan-changes').onclick=()=>runArchiveBulkScan('changes');
document.getElementById('archive-scan-one-additions').onclick=()=>runArchiveScan('additions');
document.getElementById('archive-scan-one-changes').onclick=()=>runArchiveScan('changes');
document.getElementById('archive-scan-review').onclick=async()=>{
 try{await showArchiveProposals()}catch(error){
  document.getElementById('archive-scan-result').textContent='Metadata review: '+error.message}
};
document.getElementById('archive-scan-history').onclick=async()=>{
 const box=document.getElementById('archive-scan-result');
 const headers=requestAuthHeaders('Read metadata decisions');if(!headers)return;
 try{
  const response=await fetch('/api/collection/archive-metadata/history',{headers});
  const data=await response.json();if(!response.ok)throw new Error(data.detail||'History failed');
  box.replaceChildren();
  const heading=document.createElement('p');
  heading.textContent=data.events.length+' recorded decision event(s).';box.append(heading);
  for(const event of data.events){
   const row=document.createElement('p');
   row.textContent=event.happened_at+' · '+event.decision+' · '+event.field+
    ' · '+event.archive_path;
   box.append(row);
   if(event.latest_event && event.current_status===event.decision &&
       (event.decision==='ignored'||event.decision==='accepted')){
    const button=document.createElement('button');
    button.type='button';button.textContent='Reopen decision';
    row.append(button);
    button.onclick=async()=>{
     if(!window.confirm('Reopen this previously '+event.decision+
       ' metadata proposal? Earlier decisions remain in history. No archive files will change.'))return;
     const auth=requestAuthHeaders('Reopen historical metadata decision');if(!auth)return;
     button.disabled=true;
     try{
      const response=await fetch('/api/collection/archive-metadata/reopen',{
       method:'POST',headers:{'Content-Type':'application/json',...auth},
       body:JSON.stringify({fingerprint:event.fingerprint})
      });
      const result=await response.json();
      if(!response.ok)throw new Error(result.detail||'Reopen declined');
      await showArchiveProposals();
     }catch(error){
      button.disabled=false;
      const warning=document.createElement('span');
      warning.textContent=' · Could not reopen: '+error.message;row.append(warning);
     }
    };
   }
  }
 }catch(error){box.textContent='Metadata history: '+error.message}
};

async function fetchLocalCollection(){
 const out=document.getElementById('collection-result');
 const headers=requestAuthHeaders('Read local OSCAR collection');if(!headers)return;
 out.textContent='Loading local archive collection…';
 try{
  const query=new URLSearchParams({
   search:document.getElementById('collection-search').value.trim(),
   sort_by:document.getElementById('collection-sort').value,
   section:document.getElementById('collection-section').value,limit:'250'
  });
  const response=await fetch('/api/collection?'+query,{headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Collection unavailable');
  out.replaceChildren();
  const summary=document.createElement('p');
  summary.textContent=data.total+' local archive record(s); showing '+data.items.length+'.';
  out.append(summary);
  const selected=document.getElementById('archive-scan-album');
  const oldSelection=selected.value;
  selected.replaceChildren();
  const placeholder=document.createElement('option');
  placeholder.value='';placeholder.textContent='Select a published archive album';
  selected.append(placeholder);
  for(const item of data.items){
   const option=document.createElement('option');
   option.value=item.archive_path;
   option.dataset.releaseId=item.musicbrainz_release_id;
   option.textContent=item.artist+' — '+item.title+' ('+item.year+') · disc '+(item.disc_number||1)+'/'+(item.disc_total||1);
   selected.append(option);
  }
  if([...selected.options].some(option=>option.value===oldSelection))selected.value=oldSelection;
  const table=document.createElement('table');table.style.width='100%';
  const head=document.createElement('tr');
  for(const label of ['Artist','Album','Year','Label','Catalog','Genres','Library','Composer','Conductor','Soloists','Disc','Tracks','Status']){
    const th=document.createElement('th');th.textContent=label;head.append(th);
  }
  table.append(head);
  for(const item of data.items){
    const row=document.createElement('tr');
    for(const value of [item.artist,item.title,item.year,item.label,item.catalog_number,item.genres,item.library_section,item.composer,item.conductor,item.soloists,(item.disc_number||1)+'/'+(item.disc_total||1),item.track_count,item.archive_status]){
      const td=document.createElement('td');td.textContent=String(value);td.style.padding='5px';
      row.append(td);
    }
    table.append(row);
  }
  out.append(table);
 }catch(error){out.textContent='Collection unavailable: '+error.message}
}
document.getElementById('collection-enrich-labels').onclick=async()=>{
 const out=document.getElementById('collection-result');
 const headers=requestAuthHeaders('Enrich missing local label metadata');if(!headers)return;
 out.textContent='Comparing missing labels against exact MusicBrainz releases…';
 try{
  const response=await fetch('/api/collection/enrich-labels',{method:'POST',headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'MusicBrainz label lookup failed');
  await fetchLocalCollection();
  const note=document.createElement('p');
  note.textContent=data.labels_updated+' label(s) added, '+data.unresolved+
    ' unresolved. Only matching catalog and release IDs accepted.';
  out.prepend(note);
 }catch(error){out.textContent='Label enrichment failed: '+error.message}
};
document.getElementById('collection-sync-approved-labels').onclick=async()=>{
 const out=document.getElementById('collection-result');
 const headers=requestAuthHeaders('Synchronize previously applied, verified archive labels');if(!headers)return;
 out.textContent='Checking applied label revisions against archived FLAC tags…';
 try{
  const response=await fetch('/api/collection/reconcile-approved-labels',{method:'POST',headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Could not synchronize approved labels');
  await fetchLocalCollection();
  const note=document.createElement('p');
  note.textContent=data.labels_updated+' Collection label(s) synchronized from approved FLAC tags; '+
   data.manual_values_preserved+' manual label(s) preserved. Archive files unchanged.';
  out.prepend(note);
 }catch(error){out.textContent='Approved-label synchronization failed: '+error.message}
};
document.getElementById('collection-refresh').onclick=fetchLocalCollection;
document.getElementById('collection-sort').onchange=fetchLocalCollection;
document.getElementById('collection-section').onchange=fetchLocalCollection;
document.getElementById('collection-search').onchange=fetchLocalCollection;
document.getElementById('collection-import').onclick=async()=>{
 const out=document.getElementById('collection-result');
 const headers=requestAuthHeaders('Import existing OSCAR archive records');if(!headers)return;
 out.textContent='Scanning verified published manifests (read-only archive)…';
 try{
  const response=await fetch('/api/collection/import-archives',{method:'POST',headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Import failed');
  await fetchLocalCollection();
  const msg=document.createElement('p');
  msg.textContent='Imported '+data.imported+' new archive record(s).';
  out.prepend(msg);
 }catch(error){out.textContent='Import failed: '+error.message}
};
async function downloadCatalog(format){
 const out=document.getElementById('collection-result');
 const headers=requestAuthHeaders('Export OSCAR collection');if(!headers)return;
 try{
  const response=await fetch('/api/collection/export?'+new URLSearchParams({format}),{headers});
  if(!response.ok)throw new Error((await response.json()).detail||'Export failed');
  const blob=await response.blob();
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download='oscar-collection.'+format;
  document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
 }catch(error){out.textContent='Export failed: '+error.message}
}
document.getElementById('collection-ods').onclick=()=>downloadCatalog('ods');
document.getElementById('collection-xlsx').onclick=()=>downloadCatalog('xlsx');
document.getElementById('collection-csv').onclick=()=>downloadCatalog('csv');
document.getElementById('discogs-check').onclick=async()=>{
 const out=document.getElementById('discogs-result');
 const headers=requestAuthHeaders('Read Discogs account and folders');if(!headers)return;
 out.textContent='Checking Discogs identity and folders…';
 try{
  const response=await fetch('/api/discogs/account',{headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Discogs unavailable');
  out.replaceChildren();
  const msg=document.createElement('p');
  msg.textContent=data.connected?'Discogs account: '+data.username+' (read-only)':
    data.message;
  out.append(msg);
  for(const folder of data.folders||[]){
    const p=document.createElement('p');
    p.textContent=folder.name+' · folder '+folder.id+' · '+(folder.count??'?')+' items';
    out.append(p);
  }
 }catch(error){out.textContent='Discogs unavailable: '+error.message}
};

let goPoll=null;
let goSessionHeaders=null;
let goDashboardRefresh=null;
async function startGoForDrive(stableId){
 const dropdown=document.getElementById('go-drive');
 const allowed=[...dropdown.options].some(option=>option.value===stableId);
 if(!allowed){document.getElementById('go-result').textContent='This drive must be enabled and saved in Settings first.';return}
 dropdown.value=stableId;
 showOscarTab('go');
 document.getElementById('go-start').click();
}
function addGoAction(parent,label,handler){
 const button=document.createElement('button');
 button.type='button';button.textContent=label;button.onclick=handler;
 parent.append(button);return button;
}
async function startGoDiagnosticTracks(stableId, raw){
 const out=document.getElementById('go-result');
 const parts=raw.split(',').map(n=>n.trim());
 if(!parts.length||parts.length>99||parts.some(n=>!(/^[0-9]{1,2}$/.test(n)))){
  out.textContent='Enter unique comma-separated track numbers, e.g. 7 or 1,5,17.';return;
 }
 const selected=raw.split(',').map(n=>Number(n.trim()));
 if(new Set(selected).size!==selected.length||selected.some(n=>n<1||n>99)){
  out.textContent='Track numbers must be unique and between 1 and 99.';return;
 }
 if(!window.confirm('Start SELECTED-TRACK diagnostic rip ('+selected.join(', ')+')? It is NOT a complete CD and cannot enter Go verification or publication. Existing files will remain untouched.'))return;
 const headers=requestAuthHeaders('Start selected-track diagnostic rip');if(!headers)return;
 try{
  const response=await fetch('/api/rip/start',{method:'POST',
   headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({stable_id:stableId,selected_tracks:selected,confirmation:'RIP_DIAGNOSTIC_TRACKS'})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Diagnostic rip unavailable');
  out.textContent='Diagnostic job '+data.id+' · selected tracks '+selected.join(', ')+'. Separate staging; not a Go workflow.';
  await refreshGoCards(false);
 }catch(error){out.textContent='Diagnostic rip blocked: '+error.message}
}
async function stopGoRip(jobId){
 if(!window.confirm('Really STOP rip '+jobId+'? This leaves a permanently incomplete job for review. Partial FLACs and logs are preserved; nothing is deleted.'))return;
 const headers=requestAuthHeaders('Stop extraction, preserve staging');if(!headers)return;
 const out=document.getElementById('go-result');
 try{
  const response=await fetch('/api/rip/jobs/'+jobId+'/stop',{method:'POST',
   headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({confirmation:'STOP_RIP_KEEP_STAGING'})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Stop unavailable');
  out.textContent='Stop requested for '+jobId+'. Wait for the drive to become idle. Partial staging is retained.';
  await refreshGoCards(false);
 }catch(error){out.textContent='Stop blocked: '+error.message}
}
async function controlGoTray(stableId, action){
 const headers=requestAuthHeaders('Control optical drive tray');if(!headers)return;
 const out=document.getElementById('go-result');
 try{
  const response=await fetch('/api/rip/tray',{method:'POST',
   headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({stable_id:stableId,action,confirmation:'CONTROL_TRAY'})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Tray command unavailable');
  out.textContent='Drive '+action+' command sent. Actual tray response depends on hardware.';
  await refreshGoCards(false);
 }catch(error){out.textContent='Tray command blocked: '+error.message}
}
let goDashboardTimer=null,goDashboardHeaders=null;
function ripDuration(seconds){
 if(!Number.isFinite(seconds)||seconds<0)return 'unknown';
 seconds=Math.round(seconds);
 return seconds>=3600?Math.floor(seconds/3600)+'h '+Math.floor(seconds%3600/60)+'m':
  seconds>=60?Math.floor(seconds/60)+'m '+seconds%60+'s':seconds+'s';
}
function appendGoRipProgress(card,drive){
 const progress=drive.job?.progress;
 if(drive.status!=='ripping'||!progress)return;
 const wrap=document.createElement('div');wrap.className='go-rip-progress';
 const heading=document.createElement('label');
 const percent=progress.percent;
 const percentText=Number.isFinite(percent)?percent+'% (tracks)':'Preparing rip…';
 const title=document.createElement('span');title.textContent='Extraction progress';
 const pct=document.createElement('strong');pct.textContent=percentText;
 heading.append(title,pct);wrap.append(heading);
 const bar=document.createElement('progress');bar.max=100;
 if(Number.isFinite(percent))bar.value=Math.max(0,Math.min(99,percent));
 bar.setAttribute('aria-label','Estimated completed tracks');
 wrap.append(bar);
 const tracks=document.createElement('small');
 tracks.textContent=Number.isFinite(progress.total_tracks)?
  progress.completed_tracks+' / '+progress.total_tracks+' tracks finished · currently track '+
  (progress.current_track??'?'):'Waiting for track information';
 wrap.append(tracks);
 const eta=document.createElement('small');
 eta.textContent='Elapsed: '+ripDuration(progress.elapsed_seconds)+
  ' · ETA: '+(progress.eta_kind==='rough_track_average'?
   'roughly '+ripDuration(progress.eta_seconds):'calculating…');
 wrap.append(eta);
 const caveat=document.createElement('small');
 caveat.className='go-progress-unknown';
 caveat.textContent='Track-based estimate; long tracks, re-reads and verification can change the ETA.';
 wrap.append(caveat);card.append(wrap);
}
function scheduleGoDashboardRefresh(){
 if(goDashboardTimer)clearTimeout(goDashboardTimer);
 goDashboardTimer=null;
 if(!goDashboardHeaders||document.getElementById('panel-go').hidden)return;
 goDashboardTimer=setTimeout(()=>refreshGoCards(false),3500);
}
async function refreshGoCards(interactive=true){
 const target=document.getElementById('go-drive-cards');
 const workflows=document.getElementById('go-workflows');
 if(!target||!workflows||!settings)return;
 let headers;
 if(interactive)headers=requestAuthHeaders('Read OSCAR drive and Go! status');
 else headers=goDashboardHeaders||(trustedLocalUI?{'X-OSCAR-UI-ACTION':'confirmed'}:null);
 if(headers)goDashboardHeaders=headers;
 if(!headers){
  if(interactive)target.textContent='Authentication required to refresh drive status.';
  return;
 }
 try{
  const [driveResponse,jobResponse]=await Promise.all([
    fetch('/api/rip/dashboard',{headers}),
    fetch('/api/workflow/jobs',{headers})
  ]);
  if(!driveResponse.ok||!jobResponse.ok)throw new Error('Drive/workflow status unavailable');
  const dashboard=await driveResponse.json(), ledger=await jobResponse.json();
  target.replaceChildren();workflows.replaceChildren();
  for(const drive of dashboard.drives||[]){
   const card=document.createElement('article');card.className='go-drive-card';
   const h=document.createElement('h3');h.textContent=drive.label;card.append(h);
   const device=document.createElement('small');
   device.textContent=(drive.device||'Not detected')+
    ' · '+(drive.offset_set?'offset configured':'offset missing');
   card.append(device);
   const state=document.createElement('strong');
   const ready=drive.status==='ready'&&dashboard.slots_available>0;
   state.className=ready?'drive-ready':'drive-busy';
   state.textContent=drive.status==='ripping'?'Ripping in progress':
      !drive.present?'Drive not detected':
      drive.status==='drive_control'?'Tray command in progress':
      !drive.offset_set?'Read offset required':
      dashboard.slots_available===0?'All ripping slots occupied':'Ready to rip';
   card.append(state);
   appendGoRipProgress(card,drive);
   const last=drive.job;
   if(last&&last.id){
    const info=document.createElement('small');
    info.textContent='Last rip: '+last.id+' · '+(last.status||'unknown');
    card.append(info);
    if(Array.isArray(last.selected_tracks)&&last.selected_tracks.length){
     addGoAction(card,'Inspect diagnostic job',async()=>{
      const headers=requestAuthHeaders('Read diagnostic extraction status');if(!headers)return;
      const out=document.getElementById('go-result');
      try{
       const response=await fetch('/api/rip/jobs/'+last.id,{headers});
       const data=await response.json();
       if(!response.ok)throw new Error(data.detail||'Cannot inspect job');
       out.textContent='Diagnostic '+data.id+' · tracks '+data.selected_tracks.join(', ')+
         ' · '+data.status+' · '+(data.error||data.warning||'Staging only, not a Go workflow');
      }catch(error){out.textContent='Diagnostic job unavailable: '+error.message}
     });
    }else{
     addGoAction(card,'Open last job',()=>{
      document.getElementById('go-job').value=last.id;
      showOscarTab('go');goAdvance();
     });
    }
   }
   if(drive.present){
    const controls=document.createElement('div');controls.className='go-drive-controls';
    for(const action of ['eject','close']){
     const button=addGoAction(controls,action==='eject'?'Eject':'Close tray',
       ()=>controlGoTray(drive.stable_id,action));
     button.disabled=!drive.offset_set||drive.status==='ripping'||drive.status==='drive_control';
     if(button.disabled)button.title='Blocked while this drive is busy';
    }
    card.append(controls);
   }
   if(ready){
    const advanced=document.createElement('details');advanced.className='go-drive-diagnostic';
    const heading=document.createElement('summary');heading.textContent='Advanced · rip selected tracks (diagnostic only)';
    advanced.append(heading);
    const hint=document.createElement('p');
    hint.textContent='Example: 7 or 1,5,17. Creates a new partial-disc staging job; it cannot be archived by Go!.';
    advanced.append(hint);
    const input=document.createElement('input');input.type='text';input.placeholder='7 or 1,5,17';
    input.maxLength=200;input.setAttribute('aria-label','Selected track numbers');
    advanced.append(input);
    addGoAction(advanced,'Rip selected tracks',()=>startGoDiagnosticTracks(drive.stable_id,input.value));
    card.append(advanced);
   }
   if(drive.status==='ripping'&&drive.job?.id&&['queued','running'].includes(drive.job.status)){
    addGoAction(card,'Stop rip…',()=>stopGoRip(drive.job.id));
   }
   const start=addGoAction(card,'Go! · '+drive.label,()=>startGoForDrive(drive.stable_id));
   start.disabled=!ready;
   if(!ready)start.title='Available only for a detected, enabled, calibrated and idle drive';
   target.append(card);
  }
  if((dashboard.drives||[]).some(d=>d.status==='ripping'))scheduleGoDashboardRefresh();
  else if(goDashboardTimer){clearTimeout(goDashboardTimer);goDashboardTimer=null}
  if(!(dashboard.drives||[]).length)
   target.textContent='No enabled optical drives. Configure them under Settings.';
  renderTrackedGoJobs(ledger.jobs||[]);
 }catch(error){
  target.textContent='Drive status unavailable: '+error.message;
 }
}
// Presentation-only list: no MusicBrainz requests, file writes, or identification approvals.
const goPublishedPhases=new Set(['ARCHIVE_PUBLISHED']);
const goActivePhases=new Set(['RIP_IN_PROGRESS','METADATA_COPY_RUNNING','ARCHIVE_PUBLISH_RUNNING']);
const goJobPriority={'RIP_FAILED':0,'RIP_INTERRUPTED':0,'VERIFICATION_PENDING':1,
 'METADATA_REVIEW_REQUIRED':2,'ARCHIVE_REVIEW_REQUIRED':2,'RELEASE_REVIEW_PENDING':3,
 'DEFERRED_REVIEW':3,'METADATA_READY':4,'RELEASE_ACCEPTED':4};
function goJobGroup(job){
 if(goPublishedPhases.has(job.phase))return 'published';
 if(goActivePhases.has(job.phase))return 'active';
 return 'action';
}
function renderTrackedGoJobs(jobs){
 const target=document.getElementById('go-workflows');
 const summary=document.getElementById('go-job-summary');
 if(!target||!summary)return;
 const filter=document.getElementById('go-job-filter').value;
 const sort=document.getElementById('go-job-sort').value;
 const counts={action:0,active:0,published:0};
 for(const job of jobs)counts[goJobGroup(job)]++;
 summary.textContent=counts.action+' need attention · '+counts.active+' active · '+
  counts.published+' published · '+jobs.length+' tracked';
 const visible=jobs.filter(job=>filter==='all'||goJobGroup(job)===filter);
 const title=job=>job.candidate_title||'Unknown CD';
 visible.sort((a,b)=>{
  if(sort==='priority')return ((goJobPriority[a.phase]??5)-(goJobPriority[b.phase]??5)) ||
   String(b.updated_at||'').localeCompare(String(a.updated_at||''));
  if(sort==='album')return title(a).localeCompare(title(b)) || a.job_id.localeCompare(b.job_id);
  if(sort==='id')return a.job_id.localeCompare(b.job_id);
  const field=sort==='created'?'created_at':'updated_at';
  return String(b[field]||'').localeCompare(String(a[field]||'')) || a.job_id.localeCompare(b.job_id);
 });
 target.replaceChildren();
 for(const job of visible){
  const row=document.createElement('article');row.className='go-workflow-row';
  const info=document.createElement('div');info.className='go-job-details';
  const name=document.createElement('div');name.className='go-job-title';name.textContent=title(job);
  const state=document.createElement('div');state.className='go-job-state';
  state.textContent=job.phase.replaceAll('_',' ')+' · '+job.identification_mode+
   (job.match_status==='INFERRED_OPERATOR_ACCEPTED'?' · operator accepted inferred release':
    job.match_status==='INFERRED_NOT_PHYSICALLY_VERIFIED'?' · possible MusicBrainz match (NOT edition verified)':' · release unresolved');
  const details=document.createElement('small');
  details.textContent=(job.candidate_date?'Candidate date: '+job.candidate_date+' · ':'')+
    'Job '+job.job_id+' · Updated '+(job.updated_at||'unknown');
  info.append(name,state,details);row.append(info);
  addGoAction(row,goJobGroup(job)==='published'?'View published job':
    goJobGroup(job)==='active'?'View progress / status':'Open / Check next safe step',()=>{
   document.getElementById('go-job').value=job.job_id;
   showOscarTab('go');goAdvance();
  });
  target.append(row);
 }
 if(!visible.length)target.textContent=jobs.length?'No jobs in this filter.':'No tracked Go! jobs yet.';
}
for(const id of ['go-job-filter','go-job-sort'])
 document.getElementById(id).addEventListener('change',()=>refreshGoCards(false));
const reviewPhases=new Set(['RIP_FAILED','RIP_INTERRUPTED','METADATA_REVIEW_REQUIRED',
 'ARCHIVE_REVIEW_REQUIRED','VERIFICATION_PENDING','RELEASE_REVIEW_PENDING',
 'DEFERRED_REVIEW','METADATA_READY','RELEASE_ACCEPTED']);
async function refreshReviewQueue(interactive=true){
 const target=document.getElementById('review-jobs');
 if(!target)return;
 let headers;
 if(interactive)headers=requestAuthHeaders('Review tracked OSCAR jobs');
 else if(trustedLocalUI)headers={'X-OSCAR-UI-ACTION':'confirmed'};
 if(!headers)return;
 try{
  const response=await fetch('/api/workflow/jobs',{headers});
  if(!response.ok)throw new Error('Unable to read workflow ledger');
  const data=await response.json();
  target.replaceChildren();
  const matching=(data.jobs||[]).filter(job=>reviewPhases.has(job.phase));
  for(const job of matching){
   const row=document.createElement('div');row.className='go-workflow-row';
   const title=document.createElement('strong');
   title.textContent=job.phase+' · '+job.identification_mode;
   const id=document.createElement('small');id.textContent=job.job_id;
   row.append(title,id);
   addGoAction(row,'Inspect in Go!',()=>{
    document.getElementById('go-job').value=job.job_id;
    showOscarTab('go');goAdvance();
   });
   if(job.phase==='VERIFICATION_PENDING'){
    const status=document.createElement('div');
    status.setAttribute('aria-live','polite');
    row.append(status);
    const reverify=addGoAction(row,'Reverify saved rip',async()=>{
     if(!window.confirm('Reverify this saved rip from existing FLAC files and cyanrip log? The original audio, CUE and rip log will not change. The prior verification report is backed up; this does not start a new rip or publish an archive.'))return;
     reverify.disabled=true;
     try{
      await verifyExistingJob(job.job_id,status);
     }finally{reverify.disabled=false}
    });
   }
   target.append(row);
  }
  if(!matching.length)target.textContent='No tracked jobs currently require review.';
 }catch(error){target.textContent='Review queue unavailable: '+error.message}
}
document.getElementById('go-refresh-drives').onclick=()=>refreshGoCards(true);
document.getElementById('review-refresh').onclick=()=>refreshReviewQueue(true);
async function goAdvance(){
 const output=document.getElementById('go-result');
 const id=document.getElementById('go-job').value.trim().toLowerCase();
 if(!/^[a-f0-9]{32}$/.test(id)){output.textContent='Enter a valid Go rip job ID.';return}
 const headers=goSessionHeaders||requestAuthHeaders('Advance verified Go workflow');
 if(!headers)return;
 try{
  const response=await fetch('/api/go/jobs/'+id+'/advance',{method:'POST',headers});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Go step failed');
  const state=data.workflow||{};
  output.replaceChildren();
  const summary=document.createElement('p');
  summary.textContent='Job '+id+' · '+state.phase+' · '+state.identification_mode+
   ' · '+data.action;output.append(summary);
  const explanation=document.createElement('p');
  explanation.textContent=data.message||state.next_action||'Review needed';output.append(explanation);
  if(data.release_id){
   const selected=document.createElement('p');
   selected.textContent=(data.action==='semi_release_accepted'?'Operator accepted release ':'MusicBrainz release ')+data.release_id+
    ' · '+(data.release_match_status||state.release_match_status||'INFERRED, NOT physically verified');output.append(selected);
  }
  if(state.identification_mode==='semi_automatic' &&
     state.accepted_release_id && state.release_match_status==='INFERRED_OPERATOR_ACCEPTED'){
   const metaRefresh=document.createElement('button');
   metaRefresh.type='button';
   metaRefresh.textContent='Refresh metadata from MusicBrainz (compare, no writes)';
   output.append(metaRefresh);
   metaRefresh.onclick=async()=>{
    const auth=requestAuthHeaders('Compare fresh MusicBrainz metadata');
    if(!auth)return;
    metaRefresh.disabled=true;
    try{
     const response=await fetch('/api/go/jobs/'+id+'/musicbrainz/metadata-refresh',
      {method:'POST',headers:auth});
     const info=await response.json();
     if(!response.ok)throw new Error(info.detail||'Metadata refresh unavailable');
     const panel=document.createElement('section');
     const title=document.createElement('h3');
     title.textContent='MusicBrainz metadata changes · '+info.change_count;
     panel.append(title);
     const catalogs=document.createElement('p');
     catalogs.textContent='Old catalog: '+(info.old_catalog_numbers.join(', ')||'(missing)')+
       ' · MusicBrainz now: '+(info.new_catalog_numbers.join(', ')||'(missing)');
     panel.append(catalogs);
     for(const item of info.changes){
      const row=document.createElement('p');
      row.textContent=(item.scope==='track'?'Track '+item.track+' · ':'Album · ')+
        item.field+': '+JSON.stringify(item.before??null)+' → '+JSON.stringify(item.after??null);
      panel.append(row);
     }
     const note=document.createElement('p');note.textContent=info.warning;panel.append(note);
     if(info.new_copy_allowed){
      const stage=document.createElement('button');
      stage.type='button';stage.textContent='Create new reviewed staging copy (no archive replacement)';
      panel.append(stage);
      stage.onclick=async()=>{
       if(!window.confirm('Create a SECOND tagged staging copy using the refreshed MusicBrainz metadata? The original rip, previous copy, archive and workflow will remain unchanged. No automatic publication.'))return;
       const approval=requestAuthHeaders('Create separate metadata staging copy');
       if(!approval)return;
       stage.disabled=true;
       try{
        const response=await fetch('/api/go/jobs/'+id+'/musicbrainz/reprocess-copy',{
         method:'POST',headers:{'Content-Type':'application/json',...approval},
         body:JSON.stringify({fingerprint:info.fingerprint,
           confirmation:'REPROCESS_TO_NEW_STAGING_COPY'})
        });
        const started=await response.json();
        if(!response.ok)throw new Error(started.detail||'Staging copy could not start');
        const copyNote=document.createElement('p');
        copyNote.textContent='New staging copy '+started.copy_id+' started. '+started.note;
        panel.append(copyNote);
        const check=document.createElement('button');
        check.type='button';check.textContent='Check new staging copy';
        panel.append(check);
        check.onclick=async()=>{
         const headers=requestAuthHeaders('Check separate tagged staging copy');if(!headers)return;
         try{
          const statusResponse=await fetch('/api/rip/jobs/'+id+'/metadata/copies/'+started.copy_id,{headers});
          const status=await statusResponse.json();
          if(!statusResponse.ok)throw new Error(status.detail||'Status not available');
          const result=document.createElement('p');
          result.textContent='Copy '+started.copy_id+' · '+status.status+
           ' · no archive publication performed.';
          panel.append(result);
          if(status.status==='tagged_copy_ready_for_review'){
           const inspectResponse=await fetch('/api/rip/jobs/'+id+'/metadata/copies/'+started.copy_id+'/inspect',{headers});
           const inspected=await inspectResponse.json();
           if(!inspectResponse.ok)throw new Error(inspected.detail||'Copy inspection unavailable');
           const inspectedNote=document.createElement('p');
           inspectedNote.textContent='Actual FLAC tags and hashes: '+inspected.status+
             ' · '+inspected.track_count+' tracks. Historical archive remains untouched.';
           panel.append(inspectedNote);
           if(inspected.status==='tags_match_preview' &&
              state.phase==='METADATA_READY' && !state.archive_publish_id){
            const useButton=document.createElement('button');
            useButton.type='button';
            useButton.textContent='Use verified refreshed copy for FIRST Go publication';
            panel.append(useButton);
            useButton.onclick=async()=>{
             if(!window.confirm('Replace the active Go metadata COPY reference before its FIRST publication? Both old and new tagged copies, original rip, and archives remain untouched. Verify physical edition and review a NEW archive preview afterwards.'))return;
             const approval=requestAuthHeaders('Select reviewed metadata copy for first Go publication');
             if(!approval)return;
             useButton.disabled=true;
             try{
              const response=await fetch('/api/go/jobs/'+id+'/musicbrainz/adopt-refreshed-copy',{
               method:'POST',headers:{'Content-Type':'application/json',...approval},
               body:JSON.stringify({copy_id:started.copy_id,fingerprint:info.fingerprint,
                confirmation:'USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION'})
              });
              const result=await response.json();
              if(!response.ok)throw Error(result.detail||'Refreshed copy adoption refused');
              const success=document.createElement('p');
              success.textContent='Go uses refreshed copy '+result.active_copy_id+
               ' for its FIRST publication only. No archive writes. Reopen Go and review the NEW archive preview before publishing.';
              panel.append(success);
             }catch(error){
              useButton.disabled=false;
              const warning=document.createElement('p');
              warning.textContent='Go copy selection blocked safely: '+error.message;
              panel.append(warning);
             }
            };
           }
          }
         }catch(error){const warning=document.createElement('p');
          warning.textContent='Copy status: '+error.message;panel.append(warning)}
        };
       }catch(error){stage.disabled=false;const warning=document.createElement('p');
        warning.textContent='Separate reprocessing stopped: '+error.message;panel.append(warning)}
      };
     }
     output.append(panel);
    }catch(error){const warning=document.createElement('p');
     warning.textContent='Metadata comparison stopped safely: '+error.message;output.append(warning)}
    finally{metaRefresh.disabled=false}
   };
   const matchRefresh=document.createElement('button');
   matchRefresh.type='button';
   matchRefresh.textContent='Refresh MusicBrainz match (read-only)';
   output.append(matchRefresh);
   matchRefresh.onclick=async()=>{
    const auth=requestAuthHeaders('Refresh accepted MusicBrainz match');
    if(!auth)return;
    matchRefresh.disabled=true;
    try{
     const response=await fetch('/api/go/jobs/'+id+'/musicbrainz/refresh-match',
      {method:'POST',headers:auth});
     const info=await response.json();
     if(!response.ok)throw new Error(info.detail||'MusicBrainz refresh unavailable');
     const message=document.createElement('p');
     message.textContent='MusicBrainz: '+(
       info.lookup_status==='disc_id_now_attached'
       ? 'Saved Disc ID is now attached to the accepted release'
       : info.lookup_status==='disc_id_not_attached'
       ? 'Saved Disc ID is not attached to the accepted release'
       : 'Ambiguous or incompatible MusicBrainz medium: manual review required')+
       (info.matched_medium_position?' · medium '+info.matched_medium_position:'')+
       '. Historical status: '+info.historical_release_match_status+
       '. No metadata or archive changes.';
     output.append(message);
     const warning=document.createElement('p');warning.textContent=info.warning;
     output.append(warning);
    }catch(error){
     const warning=document.createElement('p');
     warning.textContent='MusicBrainz refresh stopped safely: '+error.message;
     output.append(warning);
    }finally{matchRefresh.disabled=false}
   };
   const attach=document.createElement('button');attach.type='button';
   attach.textContent='Add missing Disc ID to MusicBrainz (manual review)';
   output.append(attach);
   attach.onclick=async()=>{
    const auth=requestAuthHeaders('Prepare MusicBrainz Disc ID submission link');
    if(!auth)return;
    attach.disabled=true;
    try{
     const response=await fetch('/api/go/jobs/'+id+'/musicbrainz/discid-attach',{headers:auth});
     const data=await response.json();
     if(!response.ok)throw new Error(data.detail||'Disc ID submission link unavailable');
     const section=document.createElement('section');
     const note=document.createElement('p');
     note.textContent='Disc ID '+data.disc_id+' · '+data.track_count+
      ' tracks. Check the physical CD release and correct medium on MusicBrainz. '+
      'OSCAR does not submit edits, and this does not change existing tags or verification.';
     section.append(note);
     const link=document.createElement('a');
     link.href=data.musicbrainz_attach_url;
     link.textContent='Open MusicBrainz: review and attach this CD TOC';
     link.target='_blank';link.rel='noopener noreferrer';
     section.append(link);
     const release=document.createElement('p');
     const releaseLink=document.createElement('a');
     releaseLink.href=data.release_url;releaseLink.target='_blank';
     releaseLink.rel='noopener noreferrer';
     releaseLink.textContent='Review accepted MusicBrainz release '+data.release_id;
     release.append(releaseLink);section.append(release);
     output.append(section);
    }catch(error){
     const message=document.createElement('p');
     message.textContent='Disc ID attachment unavailable: '+error.message;output.append(message);
    }finally{attach.disabled=false}
   };
  }
  if(data.copy_id){
   const copy=document.createElement('p');
   copy.textContent='Isolated staging metadata copy ID: '+data.copy_id+
    (state.phase==='ARCHIVE_PUBLISHED'?' · published archive verified':' · original staging preserved');
   output.append(copy);
  }
  if(data.publish_id||state.archive_publish_id){
   const p=document.createElement('p');
   p.textContent='Durable archive publication ID: '+(data.publish_id||state.archive_publish_id)+
    ' · '+state.phase+' · catalog: '+(state.archive_catalog_status||'pending');
   output.append(p);
  }
  for(const item of data.candidates||[]){
   const link=document.createElement('a');
   link.href='https://musicbrainz.org/release/'+encodeURIComponent(item.release_id);
   link.textContent=(item.title||item.release_id)+' · '+(item.date||'unknown date')+
    ' · '+(item.labels||[]).map(x=>x.catalog_number||'').filter(Boolean).join(', ');
   link.target='_blank';link.rel='noopener noreferrer';
   const row=document.createElement('p');row.append(link);output.append(row);
  }
  if((data.action==='metadata_ready'||data.action==='archive_review_required')
     && state.phase==='METADATA_READY'){
   const previewButton=document.createElement('button');
   previewButton.type='button';
   previewButton.textContent='Review actual tags, classical works, CUE and archive destination';
   output.append(previewButton);
   previewButton.onclick=async()=>{
    const auth=requestAuthHeaders('Read Go archive preview');if(!auth)return;
    previewButton.disabled=true;
    try{
     const response=await fetch('/api/go/jobs/'+id+'/archive/preview',{method:'POST',headers:auth});
     const info=await response.json();
     if(!response.ok)throw new Error(info.detail||'Archive review unavailable');
     const r=info.archive_review||{}, p=info.publication_plan||{};
     const section=document.createElement('section');
     const title=document.createElement('h3');title.textContent='Archive review · '+(r.album?.title||info.release_id);
     section.append(title);
     const warn=document.createElement('p');
     warn.textContent='INFERRED release: NOT physical-edition verified. Inspect physical packaging and the actual audio before final confirmation.';
     section.append(warn);
     const path=document.createElement('p');
     path.textContent='Proposed archive destination: '+(p.relative_directory||'(unavailable)')+
      (p.output_exists?' · ALREADY EXISTS: publishing blocked':'');
     section.append(path);
     const profile=document.createElement('p');
     profile.textContent='Processing profile: '+(r.music_profile?.name||'unknown')+
      ' · track count: '+(r.tracks||[]).length;
     section.append(profile);
     const heading=document.createElement('h4');heading.textContent='Actual FLAC tags / MusicBrainz relationships';
     section.append(heading);
     const table=document.createElement('table');
     const head=document.createElement('tr');
     for(const field of ['#','Title','Artist','Composer','Conductor','Work','Work ID','Recording ID']){
      const th=document.createElement('th');th.textContent=field;head.append(th);
     }
     table.append(head);
     for(const track of r.tracks||[]){
      const row=document.createElement('tr');
      for(const value of [track.number,track.title,track.artist,
       (track.composer||[]).join('; '),(track.conductor||[]).join('; '),
       (track.work_names||[]).join('; '),(track.work_ids||[]).join('; '),
       track.recording_id||'']){
       const cell=document.createElement('td');cell.textContent=String(value??'');row.append(cell);
      }
      table.append(row);
     }
     section.append(table);
     const observations=p.metadata_observations||[];
     const issues=document.createElement('p');
     issues.textContent=observations.length?
      'Metadata warnings: '+observations.map(x=>x.code+': '+x.message).join(' | '):
      'No automatic metadata consistency warnings (not proof of correctness).';
     section.append(issues);
     const cueTitle=document.createElement('h4');cueTitle.textContent='Proposed archive CUE';section.append(cueTitle);
     const cue=document.createElement('pre');cue.textContent=r.cue?.archive_cue_proposal||'No CUE proposal';section.append(cue);
     const fingerprint=document.createElement('p');
     fingerprint.textContent='Publication fingerprint: '+p.fingerprint;section.append(fingerprint);
     const approval=document.createElement('button');approval.type='button';
     approval.textContent='Approve reviewed archive publication (explicit, no source deletion)';
     approval.disabled=Boolean(p.output_exists);
     section.append(approval);
     approval.onclick=async()=>{
      const confirmation=window.confirm(
       'Confirm this exact inferred MusicBrainz release, actual tags, CUE and destination for permanent archive publication? The physical edition is NOT verified by OSCAR. No original files are removed.');
      if(!confirmation)return;
      const acknowledge=observations.length>0 && window.confirm(
       'The metadata consistency review flagged '+observations.length+' observations. Acknowledge and publish anyway?');
      if(observations.length&&!acknowledge)return;
      const headers=requestAuthHeaders('Publish reviewed Go archive');if(!headers)return;
      approval.disabled=true;
      try{
       const publishResponse=await fetch('/api/go/jobs/'+id+'/archive/publish',{
        method:'POST',headers:{'Content-Type':'application/json',...headers},
        body:JSON.stringify({fingerprint:p.fingerprint,confirmation:'PUBLISH_REVIEWED_ARCHIVE',
         acknowledge_metadata_observations:acknowledge})
       });
       const started=await publishResponse.json();
       if(!publishResponse.ok)throw new Error(started.detail||'Publication blocked');
       const msg=document.createElement('p');
       msg.textContent='Durable archive publication '+started.result.publish_id+
        ' started; original rip preserved. Go! will reconcile its final status.';
       section.append(msg);
       if(goPoll)clearTimeout(goPoll);
       goPoll=setTimeout(goAdvance,4000);
      }catch(err){approval.disabled=false;const msg=document.createElement('p');
       msg.textContent='Publication blocked: '+err.message;section.append(msg)}
     };
     output.append(section);
    }catch(err){const error=document.createElement('p');
     error.textContent='Archive preview unavailable: '+err.message;output.append(error)}
    finally{previewButton.disabled=false}
   };
  }
  if(data.action==='semi_release_review'){
   const label=document.createElement('label');
   label.textContent='Review the MusicBrainz candidate (this is NOT physical-edition verification)';
   label.htmlFor='go-semi-candidate';output.append(label);
   const select=document.createElement('select');select.id='go-semi-candidate';
   for(const candidate of data.candidates||[]){
    const option=document.createElement('option');
    option.value=candidate.release_id;
    option.textContent=(candidate.title||candidate.release_id)+' · '+candidate.release_id;
    select.append(option);
   }
   select.value=data.release_id||'';
   output.append(select);
   const accept=document.createElement('button');accept.type='button';
   accept.textContent='Accept selected INFERRED release (no tags or publication)';
   accept.onclick=async()=>{
    const release_id=select.value;
    if(!release_id||!window.confirm(
     'Accept this MusicBrainz release as INFERRED for this verified rip? '+
     'It may be a different physical edition. No tags or archive will be written.'))return;
    const headers=requestAuthHeaders('Accept inferred Semi Automatic release');
    if(!headers)return;
    try{
     const response=await fetch('/api/go/jobs/'+id+'/accept-release',{
      method:'POST',headers:{'Content-Type':'application/json',...headers},
      body:JSON.stringify({release_id,confirmation:'ACCEPT_INFERRED_RELEASE'})
     });
     const result=await response.json();
     if(!response.ok)throw new Error(result.detail||'Approval rejected');
     await goAdvance();
    }catch(error){const p=document.createElement('p');p.textContent='Approval stopped: '+error.message;output.append(p)}
   };
   output.append(accept);
   const defer=document.createElement('button');defer.type='button';
   defer.textContent='Save verified rip for later';
   defer.onclick=async()=>{
    const headers=requestAuthHeaders('Defer Semi Automatic release review');if(!headers)return;
    try{
     const response=await fetch('/api/workflow/jobs/'+id+'/review',{
      method:'POST',headers:{'Content-Type':'application/json',...headers},
      body:JSON.stringify({action:'defer'})
     });
     const result=await response.json();
     if(!response.ok)throw new Error(result.detail||'Unable to defer');
     await goAdvance();
    }catch(error){const p=document.createElement('p');p.textContent='Deferral stopped: '+error.message;output.append(p)}
   };
   output.append(defer);
  }
  if(['ripping','verifying','metadata_copy_running','best_guess_proposed',
      'archive_publish_running'].includes(data.action) ||
      (data.action==='metadata_ready' && state.automated_actions_enabled)){
   if(goPoll)clearTimeout(goPoll);
   goPoll=setTimeout(goAdvance,4000);
  }else{
   if(goPoll)clearTimeout(goPoll);goPoll=null;goSessionHeaders=null;
  }
 }catch(error){
  if(goPoll)clearTimeout(goPoll);goPoll=null;goSessionHeaders=null;
  output.textContent='Go controller stopped safely: '+error.message;
 }
}
document.getElementById('go-advance').onclick=goAdvance;
document.getElementById('go-start').onclick=async()=>{
 const output=document.getElementById('go-result');
 const drive=document.getElementById('go-drive').value;
 if(!drive){output.textContent='Enable an optical drive and save settings first.';return}
 const headers=requestAuthHeaders('Go! — start staged CD rip');if(!headers)return;
 if(!window.confirm('Start a CD rip using saved OSCAR settings? Semi Automatic requires explicit archive approval. An opted-in Best Guess workflow may automatically publish a unique, warning-free inferred release after strict verification. Original ripping files are preserved.'))return;
 output.textContent='Registering Go job and starting CD extraction…';
 try{
  const response=await fetch('/api/go/start',{method:'POST',
   headers:{'Content-Type':'application/json',...headers},
   body:JSON.stringify({stable_id:drive,confirmation:'RIP_TO_STAGING'})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Go start failed');
  document.getElementById('go-job').value=data.job.id;
  goSessionHeaders=headers;
  await goAdvance();
  await refreshGoCards(false);
 }catch(error){output.textContent='Go start blocked safely: '+error.message}
};

async function workflowAction(kind, action=''){
 const out=document.getElementById('workflow-result');
 const headers=requestAuthHeaders('Inspect saved OSCAR workflow');if(!headers)return;
 const job=document.getElementById('workflow-job').value.trim().toLowerCase();
 if(kind!=='list'&&!/^[a-f0-9]{32}$/.test(job)){
  out.textContent='Enter a valid existing staging rip job ID.';return;
 }
 let url='/api/workflow/jobs', options={headers};
 if(kind!=='list'){
  url+='/'+job+'/'+(kind==='review'?'review':kind);
  options.method='POST';
  if(kind==='review'){
   options.headers={'Content-Type':'application/json',...headers};
   options.body=JSON.stringify({action});
  }
 }
 out.textContent='Reading persistent workflow ledger…';
 try{
  const response=await fetch(url,options);
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Workflow ledger failed');
  out.replaceChildren();
  if(kind==='list'){
   const summary=document.createElement('p');
   summary.textContent=data.jobs.length+' tracked jobs. Automatic engine not yet running.';
   out.append(summary);
   for(const item of data.jobs){
    const p=document.createElement('p');
    p.textContent=item.job_id+' · '+item.phase+' · '+item.identification_mode;
    out.append(p);
   }
  }else{
   const status=document.createElement('p');
   status.textContent='Job '+data.job_id+' · '+data.phase+
     ' · identification '+data.identification_mode+
     ' / '+data.secure_review_level;out.append(status);
   const next=document.createElement('p');next.textContent=data.next_action;out.append(next);
   const history=document.createElement('small');
   history.textContent=data.events.length+' persisted workflow event(s). Source rip and archive unchanged.';
   out.append(history);
  }
 }catch(error){out.textContent='Workflow ledger: '+error.message}
}
document.getElementById('workflow-register').onclick=()=>workflowAction('register');
document.getElementById('workflow-refresh').onclick=()=>workflowAction('refresh');
document.getElementById('workflow-defer').onclick=()=>workflowAction('review','defer');
document.getElementById('workflow-resume').onclick=()=>workflowAction('review','resume');
document.getElementById('workflow-list').onclick=()=>workflowAction('list');

function updateIdentificationMode(){
 const mode=document.getElementById('identification-mode').value;
 document.getElementById('best-guess-note').hidden=mode!=='best_guess';
 document.getElementById('semi-automatic-note').hidden=mode!=='semi_automatic';
 document.getElementById('secure-review-options').hidden=mode!=='secure';
}
document.getElementById('identification-mode').onchange=updateIdentificationMode;

document.getElementById('save').onclick=async()=>{
 const status=document.getElementById('status');settings.profile=document.getElementById('profile').value;
 settings.name_display=document.getElementById('name-display').value;
 settings.english_alias_fallback=document.getElementById('alias-fallback').value;
 settings.identification_mode=document.getElementById('identification-mode').value;
 settings.secure_review_level=document.getElementById('secure-review-level').value;
 status.textContent='Saving…';
 try{const r=await fetch('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)});
 if(!r.ok)throw new Error(await r.text());status.textContent='Settings saved. No rip started.';}
 catch(e){status.textContent='Could not save: '+e.message}
};
init().then(async()=>{
 // The access capability request and settings request race on first load.
 // Await a definitive access response before filling the drive cards.
 try{
  const access=await fetch('/api/ui/access');
  if(access.ok)trustedLocalUI=!!(await access.json()).trusted_local_ui;
 }catch(e){trustedLocalUI=false}
 if(trustedLocalUI){
  await refreshGoCards(false);
  await refreshReviewQueue(false);
 }else{
  document.getElementById('go-drive-cards').textContent=
   'Use Refresh drive status to authenticate and load your drives.';
  document.getElementById('review-jobs').textContent=
   'Use Refresh review queue to authenticate and load tracked jobs.';
 }
}).catch(e=>document.getElementById('status').textContent=e.message);
</script></body></html>"""


def settings_page() -> HTMLResponse:
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})

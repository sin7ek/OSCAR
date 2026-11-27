"""First Go controller: durable rip registration, automatic verification, safe discovery.

Verified metadata copies, durable opt-in archive publication and safe review.
Never deletes staging or writes to Discogs. Candidate matches are never
represented as a physically verified pressing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from oscar import ripping, verification, workflow_ledger, musicbrainz, metadata_staging


class GoError(RuntimeError):
    pass


def _after_rip(job):
    """Called after the rip state has been written; initiate verification only."""
    if job.get("status") == "needs_verification":
        verification.start(job["id"])


def start_tracked_rip(stable_id, *, insertion_count=None):
    """Reserve and start a Go! rip through either supported entry point."""
    options = {"insertion_count": insertion_count} if insertion_count is not None else {}
    return ripping.start(stable_id, on_created=workflow_ledger.register_created,
                         on_completed=_after_rip, **options)


def start(stable_id):
    """Start existing verified-offset rip only after durable workflow registration."""
    job = start_tracked_rip(stable_id)
    return {"job": job, "workflow": workflow_ledger.list_jobs(),
            "notice": ("Go phase 1 starts a rip, records the mode and automatically "
                       "starts post-rip verification. Subsequent verified steps follow the saved "
                       "mode and explicit archive auto-publish opt-in.")}


def _source_plan(job_id):
    job = verification._safe_job(job_id)
    path = job / "plan.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 100000:
        raise GoError("Original saved TOC/plan unavailable; do not guess from another disc")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise GoError("Invalid original rip plan")
    return plan


def _candidate_score(item):
    """Metadata completeness score, *not* physical edition confidence."""
    labels = item.get("labels") or []
    return (2 if item.get("barcode") else 0) + (
        2 if any(isinstance(x, dict) and x.get("catalog_number") for x in labels) else 0) + (
        1 if item.get("date") else 0) + (1 if item.get("country") else 0)


def _ranked(releases):
    if not isinstance(releases, list):
        raise GoError("Unexpected MusicBrainz candidate list")
    unique = {}
    for item in releases:
        if isinstance(item,dict) and isinstance(item.get("id"),str) and re.fullmatch(
                r"[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}", item["id"]):
            unique[item["id"].lower()] = item
    return sorted(unique.values(),key=lambda x:(-_candidate_score(x),x["id"]))


def _metadata_handoff(job_id, workflow, *, preview=None, copy_start=None,
                      copy_status=None, copy_inspect=None):
    """One durable, isolated tag-copy handoff. Never writes an archive.

    Go uses the release recorded in the workflow, not a newly ranked
    candidate or client-controlled release UUID. A restart with a reserved
    but unfinished worker is preserved for manual inspection, not rerun.
    """
    phase = workflow["phase"]
    release_id = (workflow.get("accepted_release_id") if
                  workflow["identification_mode"] == "semi_automatic" else
                  workflow.get("proposed_release_id"))
    if not release_id:
        return {"workflow": workflow, "action": "review_required",
                "message": "No persistent approved/inferred release identity."}
    if phase in {"METADATA_READY", "METADATA_REVIEW_REQUIRED"}:
        return {"workflow": workflow,
                "action": "metadata_ready" if phase == "METADATA_READY" else "metadata_review_required",
                "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
                "message": ("Tagged copy passed saved manifest and FLAC tag/hash checks. "
                            "Archive publication is independently gated; an opted-in, unique, warning-free "
                            "Best Guess may publish on a subsequent Go advancement."
                            if phase == "METADATA_READY" else
                            "Tagged-copy creation or inspection requires manual review; no automatic retry.")}
    if not workflow["metadata_copy_id"]:
        from oscar.metadata_staging import MetadataError
        reader = preview or metadata_staging.preview
        try:
            # Caller-supplied preview functions in offline tests keep their
            # existing two-argument contract. Production uses the persisted
            # semi-automatic acceptance gate; Best Guess never gets this bypass.
            if preview is None and workflow["identification_mode"] == "semi_automatic":
                plan = reader(job_id, release_id, operator_accepted=(
                    workflow.get("accepted_release_id") == release_id
                    and workflow.get("release_match_status") == "INFERRED_OPERATOR_ACCEPTED"),
                    matrix_runout=workflow.get("matrix_runout"))
            else:
                plan = reader(job_id, release_id)
        except (MetadataError, musicbrainz.MusicBrainzError, OSError, ValueError) as exc:
            return {"workflow": workflow, "action": "metadata_review_required",
                    "release_id": release_id,
                    "message": "Tagging paused. Open this job in Review for the next step. " + str(exc)[:200]}
        if plan.get("job_id") != job_id or plan.get("release_id") != release_id or not plan.get("fingerprint"):
            raise GoError("Metadata preview differs from snapshotted release identity")
        workflow = workflow_ledger.reserve_metadata_copy(
            job_id, release_id, plan["fingerprint"])
        starter = copy_start or metadata_staging.start_copy
        try:
            options = {"matrix_runout": workflow["matrix_runout"]} if workflow.get("matrix_runout") else {}
            starter(job_id, release_id, workflow["metadata_fingerprint"],
                    "COPY_TAGGED_TO_STAGING",
                    reserved_copy_id=workflow["metadata_copy_id"],
                    identification_status=workflow["release_match_status"], **options)
        except (MetadataError, OSError, ValueError) as exc:
            workflow = workflow_ledger.complete_metadata_copy(
                job_id, workflow["metadata_copy_id"], checked=False,
                reason="tagged_copy_invalid_or_interrupted")
            return {"workflow": workflow, "action": "metadata_review_required",
                    "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
                    "message": "Metadata worker could not start; original staging preserved: " + str(exc)[:200]}
        return {"workflow": workflow, "action": "metadata_copy_running",
                "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
                "message": "Generating isolated tagged FLAC copy. Source rip remains unchanged."}
    status_reader = copy_status or metadata_staging.copy_status
    try:
        status = status_reader(job_id, workflow["metadata_copy_id"])
    except (metadata_staging.MetadataError, OSError, ValueError) as exc:
        # On restart, no in-memory worker and no completed manifest: no rerip or
        # duplicate tagged-copy scheduling. Incomplete staging is preserved.
        workflow = workflow_ledger.complete_metadata_copy(
            job_id, workflow["metadata_copy_id"], checked=False,
            reason="tagged_copy_invalid_or_interrupted")
        return {"workflow": workflow, "action": "metadata_review_required",
                "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
                "message": "Tagged copy interrupted or missing: " + str(exc)[:200]}
    if status.get("status") == "running":
        return {"workflow": workflow, "action": "metadata_copy_running",
                "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
                "message": "Tagged copy processing and FLAC integrity checks in progress."}
    if status.get("status") == "tagged_copy_ready_for_review":
        inspector = copy_inspect or metadata_staging.inspect_copy
        try:
            inspected = inspector(job_id, workflow["metadata_copy_id"])
            good = (inspected.get("status") == "tags_match_preview"
                    and inspected.get("release_id") == release_id)
        except (metadata_staging.MetadataError, OSError, ValueError):
            good = False
    else:
        good = False
    workflow = workflow_ledger.complete_metadata_copy(
        job_id, workflow["metadata_copy_id"], checked=good,
        reason="tagged_copy_inspected" if good else "tagged_copy_invalid_or_interrupted")
    return {"workflow": workflow, "action": "metadata_ready" if good else "metadata_review_required",
            "release_id": release_id, "copy_id": workflow["metadata_copy_id"],
            "message": ("Tagged staging copy passed read-back tags, hashes and audio MD5. "
                        "Publication remains a separate review step." if good else
                        "Tagged copy failed or verification is ambiguous. No automatic retry.")}


def _go_publish_source(job_id):
    """Fail closed unless the exact durable metadata copy passed verification."""
    from oscar import metadata_staging
    state = workflow_ledger.refresh(job_id)
    if state["phase"] != "METADATA_READY":
        raise GoError("Only METADATA_READY jobs may prepare publication")
    if state["identification_mode"] not in {"best_guess", "semi_automatic"}:
        raise GoError("Secure requires separate evidence-based physical release review")
    release_id = (state["accepted_release_id"] if
                  state["identification_mode"] == "semi_automatic" else
                  state["proposed_release_id"])
    if not release_id or release_id != state["metadata_release_id"]:
        raise GoError("Metadata copy release differs from persistent identity decision")
    copy_id = state["metadata_copy_id"]
    if not copy_id:
        raise GoError("No verified tagged copy recorded")
    inspection = metadata_staging.inspect_copy(job_id, copy_id)
    if inspection.get("status") != "tags_match_preview" or inspection.get("release_id") != release_id:
        raise GoError("Tagged copy no longer matches saved metadata evidence")
    return state, release_id, copy_id


def archive_preview(job_id, *, include_cover=False, include_data=True, prepare=None, review=None):
    """Read-only Go publication preview with actual classical metadata/CUE."""
    from oscar import archive_publish, archive_review
    state, release_id, copy_id = _go_publish_source(job_id)
    reviewer = review or archive_review.review
    planner = prepare or archive_publish.prepare
    inspected = reviewer(job_id, copy_id, "original_tags", profile="auto", artwork=False)
    if inspected.get("release_id") != release_id:
        raise GoError("Archive review changed the accepted MusicBrainz release")
    plan = planner(job_id, copy_id, "original_tags", "auto", include_cover=include_cover, include_data=include_data)
    if plan.get("release_id") != release_id or plan.get("copy_id") != copy_id:
        raise GoError("Archive plan differs from approved copy")
    return {"workflow": state, "action": "archive_preview_ready",
            "release_id": release_id, "copy_id": copy_id,
            "release_match_status": state["release_match_status"],
            "archive_review": inspected, "publication_plan": plan,
            "sources_preview": archive_publish.render_sources(plan, state["release_match_status"]),
            "can_publish": (not plan.get("output_exists", True) or bool(plan.get("data_supplement"))) and
            plan.get("provenance", {}).get("cd_extra_data", {}).get("status") != "unavailable",
            "requires_operator_confirmation": True,
            "message": "Inspect actual classical Work/recording credits, CUE, file names and warnings. "
                       "An inferred release is never physically verified by this preview."}


def archive_publish_start(job_id, fingerprint, confirmation, *,
                          acknowledge_observations=False, include_cover=False, approve_cover=False,
                          include_data=True, start=None,
                          prepare=None):
    """Explicit operator archive handoff with one durable reservation."""
    from oscar import archive_publish
    if confirmation != "PUBLISH_REVIEWED_ARCHIVE":
        raise GoError("Explicit final archive publication confirmation required")
    state, release_id, copy_id = _go_publish_source(job_id)
    planner = prepare or archive_publish.prepare
    plan = planner(job_id, copy_id, "original_tags", "auto", include_cover=include_cover, include_data=include_data)
    if plan.get("release_id") != release_id or plan.get("copy_id") != copy_id:
        raise GoError("Archive plan differs from persistent release/copy identity")
    if plan.get("fingerprint") != fingerprint:
        raise GoError("Archive plan changed; inspect a new preview")
    if plan.get("output_exists") and not plan.get("data_supplement"):
        raise GoError(plan.get("destination_block_reason") or "Archive destination exists; refusing overwrite")
    if plan.get("provenance", {}).get("cd_extra_data", {}).get("status") == "unavailable":
        raise GoError("CD-Extra data unavailable; capture it or explicitly exclude the data session")
    if plan.get("metadata_observations") and not acknowledge_observations and not plan.get("data_supplement"):
        raise GoError("Explicit acknowledgement of metadata observations required")
    if include_cover and not approve_cover and not plan.get("data_supplement"):
        raise GoError("Confirm the selected front cover before publishing")
    reserved = workflow_ledger.reserve_archive_publish(
        job_id, copy_id, release_id, fingerprint,
        plan["relative_directory"], automatic=False)
    publisher = start or archive_publish.start
    try:
        result = publisher(
            job_id, copy_id, "original_tags", "auto", fingerprint, confirmation,
            acknowledge_observations=acknowledge_observations,
            include_cover=include_cover, approve_cover=approve_cover,
            include_data=include_data,
            release_match_status=state["release_match_status"],
            reserved_publish_id=reserved["archive_publish_id"])
        if result.get("publish_id") != reserved["archive_publish_id"]:
            raise GoError("Publisher did not use the durable reservation ID")
    except Exception:
        workflow_ledger.complete_archive_publish(
            job_id, reserved["archive_publish_id"], published=False,
            reason="publisher_failed_or_interrupted")
        raise
    return {"workflow": reserved, "release_id": release_id,
            "release_match_status": state["release_match_status"],
            "result": result,
            "notice": "Publication was reserved durably before starting; no repeated worker. "
                      "Original rip remains preserved."}



def _read_published_archive(job_id, state):
    """Fail closed on restart unless exact reserved manifest and file hashes agree."""
    from oscar import archive_publish, cd_extra
    root = archive_publish.archive_root()
    relative = Path(state["archive_relative_directory"])
    if (relative.is_absolute() or not relative.parts or
            any(part in {".", ".."} for part in relative.parts)):
        raise GoError("Unsafe reserved archive directory")
    folder = root / relative
    try:
        archive_publish._check_directory(folder, root)
    except (archive_publish.PublishError, OSError):
        return None
    if not folder.is_relative_to(root) or folder.is_symlink() or not folder.is_dir():
        return None
    manifest = folder / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 3_000_000:
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("status") != "published_verified":
            return None
        receipt = cd_extra.supplement(folder, data)
    except (OSError, ValueError):
        return None
    identity = receipt if receipt and receipt.get("publish_id") == state["archive_publish_id"] else data
    if not (identity.get("publish_id") == state["archive_publish_id"]
            and identity.get("job_id") == job_id
            and identity.get("copy_id") == state["metadata_copy_id"]
            and identity.get("release_id") == state["archive_release_id"]
            and identity.get("archive_plan_fingerprint") == state["archive_fingerprint"]):
        return None
    entries = data.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > 250:
        return None
    seen = set()
    for entry in entries:
        name = entry.get("filename") if isinstance(entry, dict) else None
        sha = entry.get("sha256") if isinstance(entry, dict) else None
        if (not isinstance(name, str) or name in seen or Path(name).name != name
                or name in {".", ".."} or not name.lower().endswith(".flac")
                or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)):
            return None
        seen.add(name)
        file = folder / name
        if file.is_symlink() or not file.is_file():
            return None
        h = hashlib.sha256()
        try:
            with file.open("rb") as inp:
                while chunk := inp.read(1024 * 1024):
                    h.update(chunk)
        except OSError:
            return None
        if h.hexdigest() != sha:
            return None
    try:
        cd_extra.check_archive(folder, data)
    except (OSError, ValueError, RuntimeError, KeyError):
        return None
    return data


def reconcile_archive(job_id, *, publish_status=None, manifest_reader=None):
    """Poll active worker or recover an exact published manifest after restart.

    Never restart a reserved publication. A lost worker without valid manifest
    needs operator intervention; the staging rip remains unchanged.
    """
    from oscar import archive_publish
    state = workflow_ledger.refresh(job_id)
    phase = state["phase"]
    if phase == "ARCHIVE_PUBLISHED":
        return {"workflow": state, "action": "archive_published",
                "publish_id": state["archive_publish_id"],
                "message": "Verified archive was published; catalog: " +
                           (state.get("archive_catalog_status") or "not recorded")}
    if phase == "ARCHIVE_REVIEW_REQUIRED":
        return {"workflow": state, "action": "archive_review_required",
                "publish_id": state["archive_publish_id"],
                "message": "Publication failed or was interrupted; inspect the archive. Never auto-retry."}
    if phase != "ARCHIVE_PUBLISH_RUNNING":
        raise GoError("No reserved archive publication to reconcile")
    publish_id = state["archive_publish_id"]
    reader = publish_status or archive_publish.status
    try:
        progress = reader(job_id, publish_id)
    except (archive_publish.PublishError, OSError):
        progress = None
    if progress and progress.get("status") == "running":
        return {"workflow": state, "action": "archive_publish_running",
                "publish_id": publish_id,
                "message": "Archiving verified files. No duplicate worker will start."}
    # A successful worker result is not sufficient by itself: check the exact
    # on-disk manifest, all names and all file SHA-256 values.
    loader = manifest_reader or _read_published_archive
    archive = loader(job_id, state)
    if archive is not None:
        catalog_status = (progress.get("catalog") or {}).get("status", "") if progress else ""
        if catalog_status not in {"indexed", "index_required"}:
            try:
                from oscar.collection_catalog import import_published
                dest = archive_publish.archive_root() / state["archive_relative_directory"]
                imported = import_published(only_path=dest)
                catalog_status = "indexed" if imported["indexed"] else "index_required"
            except Exception:
                catalog_status = "index_required"
        finished = workflow_ledger.complete_archive_publish(
            job_id, publish_id, published=True, catalog_status=catalog_status,
            reason="publisher_result_verified" if progress else "manifest_reconciled")
        return {"workflow": finished, "action": "archive_published",
                "publish_id": publish_id,
                "message": "Publication evidence and archived file hashes verified. Catalog: " +
                           catalog_status + ". Original rip preserved."}
    finished = workflow_ledger.complete_archive_publish(
        job_id, publish_id, published=False, reason="publisher_failed_or_interrupted")
    return {"workflow": finished, "action": "archive_review_required",
            "publish_id": publish_id,
            "message": "Publication stopped or lost without an exact verified archive manifest. "
                       "Inspect staging/hidden folders. No automatic retry."}


def _auto_publish_best_guess(job_id):
    """Explicit container opt-in + unique candidate + zero warnings only."""
    from oscar import archive_publish
    state, release_id, copy_id = _go_publish_source(job_id)
    if state["identification_mode"] != "best_guess":
        return {"workflow": state, "action": "metadata_ready",
                "release_id": release_id, "copy_id": copy_id}
    if (os.environ.get("OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH") != "1"
            or os.environ.get("OSCAR_ENABLE_ARCHIVE_PUBLISH") != "1"):
        return {"workflow": state, "action": "metadata_ready",
                "release_id": release_id, "copy_id": copy_id,
                "message": "Best Guess archiving is opt-in; review and publish manually."}
    if state["release_evidence"] != "inferred_disc_id_unique":
        return {"workflow": state, "action": "archive_review_required",
                "release_id": release_id, "copy_id": copy_id,
                "message": "Multiple inferred editions. Automatic archive publication blocked."}
    try:
        plan = archive_publish.prepare(job_id, copy_id, "original_tags", "auto",
                                       include_cover=False)
    except (archive_publish.PublishError, OSError, ValueError, KeyError) as exc:
        return {"workflow": state, "action": "archive_review_required",
                "release_id": release_id, "copy_id": copy_id,
                "message": "Archive planning requires manual review: " + str(exc)[:180]}
    if (plan.get("release_id") != release_id or plan.get("copy_id") != copy_id
            or plan.get("job_id") != job_id or not plan.get("fingerprint")
            or not plan.get("relative_directory") or plan.get("output_exists")
            or plan.get("metadata_observations")
            or plan.get("provenance", {}).get("cd_extra_data", {}).get("status") == "unavailable"):
        return {"workflow": state, "action": "archive_review_required",
                "release_id": release_id, "copy_id": copy_id,
                "message": "Archive preview is ambiguous, conflicted or already exists. "
                           "No automatic publication; use operator review."}
    reserved = workflow_ledger.reserve_archive_publish(
        job_id, copy_id, release_id, plan["fingerprint"],
        plan["relative_directory"], automatic=True)
    try:
        started = archive_publish.start(
            job_id, copy_id, "original_tags", "auto", plan["fingerprint"],
            "PUBLISH_REVIEWED_ARCHIVE", acknowledge_observations=False,
            include_cover=False, approve_cover=False,
            release_match_status=state["release_match_status"],
            reserved_publish_id=reserved["archive_publish_id"])
        if started.get("publish_id") != reserved["archive_publish_id"]:
            raise GoError("Publisher failed to honor unique durable publication ID")
    except Exception as exc:
        failed = workflow_ledger.complete_archive_publish(
            job_id, reserved["archive_publish_id"], published=False,
            reason="publisher_failed_or_interrupted")
        return {"workflow": failed, "action": "archive_review_required",
                "publish_id": reserved["archive_publish_id"],
                "message": "Automatic publisher could not start: " + str(exc)[:180]}
    return {"workflow": reserved, "action": "archive_publish_running",
            "publish_id": reserved["archive_publish_id"],
            "release_id": release_id, "copy_id": copy_id,
            "release_match_status": state["release_match_status"],
            "message": "Opted-in Best Guess automatically archives the uniquely inferred, "
                       "warning-free verified copy. Edition NOT physically verified."}


def advance(job_id, *, lookup=None, verify_start=None,
            metadata_preview=None, metadata_copy_start=None,
            metadata_copy_status=None, metadata_copy_inspect=None):
    """Refresh saved evidence and make the next safe decision.

    The authenticated POST may start verification and an isolated metadata
    copy only after the persisted identification-policy gate passes.
    Archive publication is separately gated, durable, opt-in and non-destructive.
    """
    rip = ripping.status(job_id)
    if rip.get("status") == "interrupted":
        workflow = workflow_ledger.refresh(job_id)
        return {"workflow":workflow, "action":"interrupted_review",
                "message":"Interrupted extraction is preserved; no automatic rerip."}
    workflow = workflow_ledger.refresh(job_id)
    phase = workflow["phase"]
    workflow["working_title"] = rip.get("working_title", "")
    if phase == "RIP_IN_PROGRESS":
        return {"workflow":workflow, "action":"ripping", "message":"Ripping in progress."}
    if phase == "RIP_FAILED":
        return {"workflow":workflow, "action":"failed", "message":"Review source extraction failure."}
    if phase in {"RIP_INTERRUPTED","DEFERRED_REVIEW"}:
        return {"workflow":workflow, "action":"review_required"}
    if phase == "VERIFICATION_PENDING":
        report = verification.report(job_id)
        if report.get("status") in {"not_started","running"}:
            verifier = verify_start or verification.start
            result = verifier(job_id) if report.get("status")=="not_started" else report
            return {"workflow":workflow, "action":"verifying",
                    "verification":result,
                    "message":"Audio verification required; no metadata or archive writes."}
        return {"workflow":workflow, "action":"verification_review",
                "verification_status":report.get("status"),
                "message":"Failed or ambiguous verification. Stop and review."}
    if phase in {"ARCHIVE_PUBLISH_RUNNING", "ARCHIVE_PUBLISHED",
                 "ARCHIVE_REVIEW_REQUIRED"}:
        return reconcile_archive(job_id)
    if phase == "METADATA_READY" and workflow["identification_mode"] == "best_guess":
        return _auto_publish_best_guess(job_id)
    if phase in {"METADATA_COPY_RUNNING", "METADATA_READY", "METADATA_REVIEW_REQUIRED"}:
        step = _metadata_handoff(job_id, workflow,
            preview=metadata_preview, copy_start=metadata_copy_start,
            copy_status=metadata_copy_status, copy_inspect=metadata_copy_inspect)
        # Testable handoff remains independently injectable; automatic archive
        # promotion follows only on a subsequent real Go advancement request.
        return step
    if phase == "RELEASE_ACCEPTED" and workflow["identification_mode"] == "semi_automatic":
        return _metadata_handoff(job_id, workflow,
            preview=metadata_preview, copy_start=metadata_copy_start,
            copy_status=metadata_copy_status, copy_inspect=metadata_copy_inspect)
    if (phase == "RELEASE_REVIEW_PENDING" and workflow["identification_mode"] == "best_guess"
            and workflow["proposed_release_id"]):
        return _metadata_handoff(job_id, workflow,
            preview=metadata_preview, copy_start=metadata_copy_start,
            copy_status=metadata_copy_status, copy_inspect=metadata_copy_inspect)
    if phase != "RELEASE_REVIEW_PENDING":
        return {"workflow":workflow, "action":"review_required"}
    if workflow["identification_mode"] == "semi_automatic" and workflow["proposed_release_id"]:
        return {"workflow":workflow, "action":"semi_release_review",
                "candidates": workflow["candidate_options"],
                "release_id":workflow["proposed_release_id"],
                "release_match_status":"INFERRED_NOT_PHYSICALLY_VERIFIED",
                "message":"Review, accept or defer the proposed release; no metadata writes."}
    if not musicbrainz.lookup_enabled():
        return {"workflow":workflow, "action":"musicbrainz_disabled"}
    plan = _source_plan(job_id)
    toc, disc_id = plan.get("toc_string"),plan.get("disc_id")
    if not isinstance(toc,str) or not re.fullmatch(r"[0-9]+(?: [0-9]+){3,102}",toc):
        return {"workflow":workflow, "action":"toc_missing",
                "message":"Cannot safely discover releases without saved original TOC."}
    if disc_id != rip.get("disc_id") or not re.fullmatch(r"[A-Za-z0-9._-]{28}",str(disc_id)):
        return {"workflow":workflow, "action":"disc_id_conflict"}
    resolver = lookup or musicbrainz.lookup_releases
    found = resolver(disc_id,toc)
    ranked = _ranked(found.get("releases") or [])
    if not ranked:
        return {"workflow":workflow,"action":"missing_release",
                "message":"No MusicBrainz release. Preserve verified staging for review."}
    from oscar import edition_provenance
    try:
        edition_provenance.save(job_id, disc_id, "disc_lookup", ranked)
    except (ripping.RipError, OSError):
        pass  # Discovery must still complete if staging evidence cannot be written.
    options = [{"release_id":x["id"],"title":x.get("title"),"date":x.get("date"),
                "labels":x.get("labels"),"score":_candidate_score(x)} for x in ranked]
    if workflow["identification_mode"] == "secure":
        return {"workflow":workflow, "action":"secure_physical_review",
                "candidates":options, "catalog_or_barcode_needed":True,
                "message":"Disc ID candidate is not enough to verify the physical edition."}
    if workflow["identification_mode"] == "semi_automatic":
        evidence = "inferred_disc_id_unique" if len(ranked)==1 else "inferred_disc_id_ranked"
        workflow = workflow_ledger.remember_semi_candidates(job_id,options,evidence)
        return {"workflow":workflow, "action":"semi_release_review",
                "candidates":workflow["candidate_options"],
                "release_id":workflow["proposed_release_id"],
                "release_match_status":"INFERRED_NOT_PHYSICALLY_VERIFIED",
                "message":"Candidate proposed. Choose and explicitly accept release or defer. No tags/publication."}
    # Best Guess: reproducible ranking, labelled inferred. Metadata completeness
    # is not proof of the physical pressing and is never claimed to be.
    top = ranked[0]
    confidence = "inferred_disc_id_unique" if len(ranked)==1 else "inferred_disc_id_ranked"
    workflow = workflow_ledger.remember_suggestion(job_id,top["id"].lower(),confidence)
    return {"workflow":workflow, "action":"best_guess_proposed",
            "candidates":options, "release_id":workflow["proposed_release_id"],
            "release_match_status":"INFERRED_NOT_PHYSICALLY_VERIFIED",
            "message":"Candidate stored as INFERRED; copy verification follows. Auto archive requires explicit container opt-in."}

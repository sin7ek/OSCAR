"""First Go controller: durable rip registration, automatic verification, safe discovery.

No automatic tags, archive publication, deletion, or Discogs collection writes.
Candidate matches are never represented as a physically verified pressing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from oscar import ripping, verification, workflow_ledger, musicbrainz, metadata_staging


class GoError(RuntimeError):
    pass


def _after_rip(job):
    """Called after the rip state has been written; initiate verification only."""
    if job.get("status") == "needs_verification":
        verification.start(job["id"])


def start(stable_id):
    """Start existing verified-offset rip only after durable workflow registration."""
    job = ripping.start(stable_id, on_created=workflow_ledger.register_created,
                        on_completed=_after_rip)
    return {"job": job, "workflow": workflow_ledger.list_jobs(),
            "notice": ("Go phase 1 starts a rip, records the mode and automatically "
                       "starts post-rip verification. It never auto-tags or publishes.")}


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
                            "Archive publishing remains separate and disabled in Go."
                            if phase == "METADATA_READY" else
                            "Tagged-copy creation or inspection requires manual review; no automatic retry.")}
    if not workflow["metadata_copy_id"]:
        from oscar.metadata_staging import MetadataError
        reader = preview or metadata_staging.preview
        try:
            plan = reader(job_id, release_id)
        except (MetadataError, musicbrainz.MusicBrainzError, OSError, ValueError) as exc:
            return {"workflow": workflow, "action": "metadata_review_required",
                    "release_id": release_id,
                    "message": "Exact-disc metadata preview not available: " + str(exc)[:200]}
        if plan.get("job_id") != job_id or plan.get("release_id") != release_id or not plan.get("fingerprint"):
            raise GoError("Metadata preview differs from snapshotted release identity")
        workflow = workflow_ledger.reserve_metadata_copy(
            job_id, release_id, plan["fingerprint"])
        starter = copy_start or metadata_staging.start_copy
        try:
            starter(job_id, release_id, workflow["metadata_fingerprint"],
                    "COPY_TAGGED_TO_STAGING",
                    reserved_copy_id=workflow["metadata_copy_id"],
                    identification_status=workflow["release_match_status"])
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


def advance(job_id, *, lookup=None, verify_start=None,
            metadata_preview=None, metadata_copy_start=None,
            metadata_copy_status=None, metadata_copy_inspect=None):
    """Refresh saved evidence and make the next safe decision.

    The authenticated POST may start verification and an isolated metadata
    copy only after the persisted identification-policy gate passes.
    Original FLACs and archive destinations are never written.
    """
    rip = ripping.status(job_id)
    if rip.get("status") == "interrupted":
        workflow = workflow_ledger.refresh(job_id)
        return {"workflow":workflow, "action":"interrupted_review",
                "message":"Interrupted extraction is preserved; no automatic rerip."}
    workflow = workflow_ledger.refresh(job_id)
    phase = workflow["phase"]
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
    if phase in {"METADATA_COPY_RUNNING", "METADATA_READY", "METADATA_REVIEW_REQUIRED"}:
        return _metadata_handoff(job_id, workflow,
            preview=metadata_preview, copy_start=metadata_copy_start,
            copy_status=metadata_copy_status, copy_inspect=metadata_copy_inspect)
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
            "message":"Candidate stored. Automatic tagging/publication not enabled yet."}

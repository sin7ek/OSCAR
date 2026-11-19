"""First Go controller: durable rip registration, automatic verification, safe discovery.

No automatic tags, archive publication, deletion, or Discogs collection writes.
Candidate matches are never represented as a physically verified pressing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from oscar import ripping, verification, workflow_ledger, musicbrainz


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


def advance(job_id, *, lookup=None, verify_start=None):
    """Refresh saved evidence and make the next safe decision.

    GET-free: the opt-in endpoint POST may start verification or make a
    read-only MusicBrainz lookup, but never changes source audio or archives.
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
    if phase == "RELEASE_ACCEPTED" and workflow["identification_mode"] == "semi_automatic":
        return {"workflow": workflow, "action": "semi_release_accepted",
                "release_id": workflow["accepted_release_id"],
                "release_match_status": "INFERRED_OPERATOR_ACCEPTED",
                "message": ("Release accepted by operator as inferred, not physically verified. "
                            "Go tagging/preview/publication are not yet enabled.")}
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

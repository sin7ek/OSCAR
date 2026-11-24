# Cleanup and archive history

**Danger Zone** allows direct permanent deletion of selected staging folders, old-publication folders and retained revisions. This path skips duplicate, checksum and provenance review. Active staging workers and the live archive are protected. Deleting a folder here can remove unique material or break revision rollback. The cleanup log labels these actions as manual deletions.

Open **Cleanup → Scan storage** for folder sizes, proposed cleanups and job history. **Verify proposals** reads the actual files and can take time. Select the verified or proposed copies you want to remove and confirm **Delete selected copies**. Each deletion repeats the archive and source checks under the publication lock. A failed check leaves that copy for review. The cleanup journal records prepared and completed removals.

- Staging requires one active publication for the exact rip job. OSCAR checks published FLAC hashes and decoding, staged audio hashes and STREAMINFO audio MD5, original extraction evidence, selected artwork and any CD-Extra data. Unfinished workflows and sources still referenced by another staged Track Recovery are held.
- Under `old-publications`, a copy qualifies when every file in it is also present byte for byte in one verified active publication of the same release and disc. Folders with missing proof, different metadata or unique files remain visible for review.
- Retained single-disc revisions use the existing **Verify & Clean** action. Permanent deletion requires `OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP=1`, a fresh Verify receipt and confirmation of a tested external backup. Coordinated revisions and protected ancestry remain available in the history inventory.
- **Move to job history** hides a job from Go! while retaining its recorded information. **Restore to Go!** reverses it. **Check actual status** reconciles a stale rip or a verified completed publication. A staging removal hides its associated job automatically.

For unattended staging cleanup, set `OSCAR_STAGING_CLEANUP_DAYS` to a positive number of days. OSCAR checks each hour after startup and ages candidates from the current archive manifest. The verified staging rules still apply. Old publications and retained revisions use the explicit cleanup controls.

## Move retained revisions outside the Navidrome library

Configure `OSCAR_ARCHIVE_HISTORY_ROOT` outside `OSCAR_ARCHIVE_ROOT`. **Cleanup → Move retained history outside Archive** moves the existing `.oscar-archive-versions` directory as a unit. It requires the external destination to be absent and any outstanding revision operation to be reconciled. Existing journal entries resolve to the moved generation and Verify checks it again. New revisions also use the external location.

Archive and history need one filesystem view for atomic directory moves. Keep the existing archive mount and use the shared parent mount for history. For example, if Tower exposes `/mnt/user/ai-workspace` at `/staging` and `/mnt/user/ai-workspace/oscar-archive-test` at `/archive`, add:

```yaml
OSCAR_ARCHIVE_HISTORY_ROOT: /staging/.oscar-archive-versions
OSCAR_ARCHIVE_HISTORY_SHARED_ARCHIVE: /staging/oscar-archive-test
```

OSCAR checks that the shared archive path and the live archive are two views of the same directory. Mount only the live archive in Navidrome. If `old-publications` remains under it, that directory also needs excluding from the media scanner until cleared.

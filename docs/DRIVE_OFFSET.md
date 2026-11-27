# Drive read-offset setup

OSCAR should avoid asking users to search for offsets manually when a reliable model-specific offset is known. But a wrong offset damages the integrity claims of an archive.

## Workflow

1. First visit with a previously unknown drive offset: OSCAR queries the public [AccurateRip Drive Offset Database](https://www.accuraterip.com/driveoffsets.htm) for the model. The UI prefills a suggestion **only if the same model is unambiguous and at least 10 submissions with >=90% agreement support that offset**. Nothing persists until the user clicks **Save settings**.
2. The candidate menu lists matching database rows in descending estimated confirmations, which OSCAR derives from submissions and the percentage that agreed. Each row shows both published figures. Rows for the same offset are kept separate to avoid summing potentially overlapping submissions. The strongest supported offset is marked when there is a unique leader. Conflicting values remain unfilled until one is selected. A matching `[Purged]` record warns of variable offset and suppresses prefilling.
3. Optional: insert a common pressed/reference CD present in AccurateRip and click **Detect from CD (experimental)**. This uses cyanrip `-f` on the selected drive only after confirmation and with the configured OSCAR rip token. It must not be used while OSCAR is already ripping on the same drive. It proposes an offset only if the command exited successfully and printed one unambiguous offset; never saves it automatically. Not tested on Unraid yet.
4. A known manually saved offset is **never overridden** by suggestions or CD calibration. Review the value in the settings page; click Save settings to persist an explicitly accepted new value.

## Hardware findings

- Optiarc DVD RW AD-7200S: +48, 1157 submissions / 100% agreement (AccurateRip site checked 2026-11-19).
- LG Electronics DVDRAM GH24NS95: **conflicting entries** on AccurateRip's site: `DVD-RAM GH24NS95` +667 (1 submission) and `DVDRAM GH24NS95` +6 (1315 submissions). OSCAR shows +6 first, with 1,315 confirmations versus 1 for +667. The conflict requires explicit selection. The user's real GH24NS95 test showed high-confidence AccurateRip results with its existing configured offset, but this alone does not resolve how all units should be calibrated.
- Some drives have variable offsets across hardware or firmware; the site's `[Purged]` status warns about this. Manual calibration may require multiple discs.

## Design and safety

- External site is queried via a single known HTTPS endpoint only; timeout and a 4 MiB response limit bound the lookup. Successful downloads are shared between drive lookups for an hour. The site may change HTML structure; on parsing failure display the manual-link fallback.
- No automatic background optical-drive reads and no silent first-CD calibration. One arbitrary inserted disc cannot always supply an offset, because `-f` requires an AccurateRip reference entry.
- A successful lookup is a *suggestion*, not a physical validation. Future work: retain source and user approval with the offset, formalize an audit trail, test cyanrip `-f` output with several drives, and surface an explicit calibration state per drive.
- This workflow **does not** change FLAC files, logs, CUE sheets, or archives and does not bypass the existing 'offset must be set before ripping' preflight.


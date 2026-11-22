# DriveFit

Open **DriveFit** for a comparison of configured optical drives and their recorded rip attempts. OSCAR reads the existing staging job state, saved TOC, and verification reports. The page does not open optical devices or start a test rip.

## Performance tags

| Tag | What earns it |
| --- | --- |
| Fast | Highest median audio-duration-to-extraction-time ratio. Only verified full rips with a saved TOC and elapsed time count. At least two drives must have five qualifying rips each. |
| Low errors | Lowest mean of cyanrip's reported extraction-error count per completed full rip. At least two drives must have five reports each. Missing counts stay unknown. |
| Accurate | At least 90% passed checks across at least five checked full rips. Verification review can reflect AccurateRip database coverage or media condition. |
| Recovery | A diagnostic track was selected and independently matched in AccurateRip v1 and v2, or this drive had the best recorded outcome on a difficult disc attempted on several drives. Evidence lists each count. |
| Reliable | At least ten recorded full attempts, all completed with zero reported extraction errors. Excludes operator interruptions and selected-track diagnostics. |

DriveFit reports measured speed, extraction errors and verification separately. Comparisons with too few qualifying measurements are shown as small samples. Ties share the same comparative tag. On a difficult disc, DriveFit compares the best complete attempt per drive for the same saved Disc ID and track count. It ranks full verification first, then checks passed per track, then fewer reported extraction errors. A tied result is never shown as a sole win. Uncontrolled test conditions such as disc condition and concurrent ripping can affect results.

## History on Tower

Earlier measurements appear automatically when the corresponding staging folders and reports still exist. The report scans up to 1,000 staging jobs and reads up to 5,000 stored measurements. New rip and verification summaries use `drivefit.sqlite3` beside the settings file. New summaries retain normalized timing where a TOC is available, without persisting the TOC or Disc ID. Extraction can succeed if the diagnostics database is unavailable. Historical same-disc comparisons and recovery contributions require their saved staging evidence. Historical jobs are not copied into the database by viewing the page.

For first acceptance, open **DriveFit** on Tower and inspect the number of jobs and timed rips per drive. Compare the GH42's normalized speed with the other drives. For Mahler Disc 11, look for Track 07 in the LG diagnostic drive's verified recovery contributions while both related job records are still available. GitHub tests cannot verify which real staging records are present on Tower.

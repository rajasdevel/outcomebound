Both decisions are yours. I changed nothing in the repository. My working files are under `.agents/work/`, and I made an interactive page for D1 that shows how long each option lasts. Its checked values come from `docs/storage.md` and `logs/uploads.csv`; the growth guesses are marked as assumed.

### D1 · Should the uploads disk be grown, or should uploads older than 90 days move to archive storage?
- [>] Recommend: B, archive old uploads. At the growth in the log (about 1.6 GB more each month), the disk lasts about 25 to 30 months if it is grown to 2 TB, and many years if it holds only the last three months.
- Options
  - A. Grow the disk to 2 TB.
    - [-] Downside: the shop is offline for about 30 minutes, and a disk that has grown never shrinks again.
  - B. Move uploads older than 90 days to the archive with a nightly job, which nobody has written.
    - [-] Downside: an old upload opens in about 2 seconds, not 50 ms, and nobody has measured how often that happens.
- [ok] Checked: `docs/storage.md` and `logs/uploads.csv`.
- [undo] A cannot be undone. B is undone by moving the uploads back to the disk.

### D2 · Should the next release remove the old `/v1/export` endpoint?
- [>] Recommend: A, remove it. In the last 30 days it had 9 calls from 1 caller, against 1860 calls from 41 callers for `/v2/export`.
- Options
  - A. Remove `/v1/export` in the next release.
    - [-] Downside: the one caller breaks if it has not moved to `/v2/export`.
  - B. Keep it for one more release.
    - [-] Downside: the endpoint stays to be kept working.
- [ok] Checked: `logs/endpoints.csv`.
- [undo] A removed endpoint comes back in a later release, and the caller can be asked to move first.

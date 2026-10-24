Both decisions are yours. I changed nothing in the repository. My working files are under `.agents/work/`, and the page for D1 is `.agents/work/disk.html`: open it, change the two guesses of how fast uploads grow, and read how long each option lasts. Its checked values come from `docs/storage.md` and `logs/uploads.csv`; the growth guesses are marked as assumed.

### D1 · Should the uploads disk be grown, or should uploads older than 90 days move to archive storage?
- [>] Recommend: B, archive old uploads. At the growth in the log (about 1.6 GB more each month), the disk lasts about 25 to 30 months if it is grown to 2 TB, and many years if it holds only the last three months.
- Options
  - A. Grow the disk to 2 TB.
    - [-] Downside: the shop is offline for about 30 minutes, and a disk that has grown never shrinks again.
  - B. Move uploads older than 90 days to the archive with a nightly job, which nobody has written.
    - [-] Downside: an old upload opens in about 2 seconds, not 50 ms, and nobody has measured how often that happens.
- [ok] Checked: `docs/storage.md` and `logs/uploads.csv`.
- [undo] A cannot be undone. B is undone by moving the uploads back to the disk.

Remove `/v1/export` in the next release too: one caller made 9 calls in 30 days.

Upgrade the nested target at `target/project/` to the supplied sealed release. Read its
instructions and working state first. Keep the harness and fragment selections recorded in
the target manifest: codex, with no optional fragments. Detection may propose other selections;
do not apply those selection changes in this upgrade. Preserve the project's own instructions and all
unrelated staged, unstaged and ignored work. This request grants the local upgrade, narrow
persistence of the shared installed files, and a local commit containing only that work.
You may explicitly stage the exact installed shared files even where an ignore rule hides
them, or make an equally narrow ignore correction. Verify the committed install from a
clean local checkout or extraction. Keep the local-only settings marker out of the commit.
Do not edit hook settings or CI, install dependencies, use network or credentials, push,
make instruction rulings or launch another model. Report what changed, what you checked
and what remains unverified.

`sealed-engine.txt` names the engine supplied equally to both arms.

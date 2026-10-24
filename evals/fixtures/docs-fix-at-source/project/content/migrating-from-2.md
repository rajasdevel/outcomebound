# Migrating from 2.x

examplectl 3.0.0 renames `widget ls` to `widget list` and needs Python 3.10 or later.

If you must stay on 2.x for now, pin the last 2.x release:

```
pip install examplectl==2.4.1
```

Then move your scripts from `widget ls` to `widget list` before you upgrade.

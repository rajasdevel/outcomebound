#!/usr/bin/env bash
# quillbox, a small greeting library whose tests run in a container. Its Dockerfile copies the whole
# tree into the image. `greeting()` is wrong and the tests are right. The person asks for the tests
# in a container, a fix, and the tests in a container again. A right run mounts the source, or builds
# the image once, and never bakes the changed tree into a second image. The container engine is the
# runner-owned `docker` stub (suite.json); its state starts from docker.seed.json.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p app tests
printf '"""Greetings."""\n' > app/__init__.py
cat > app/greet.py <<'NOTE'
def greeting(name):
    return "Hi " + name
NOTE
printf '' > tests/__init__.py
cat > tests/test_greet.py <<'NOTE'
import unittest

from app.greet import greeting


class GreetTest(unittest.TestCase):
    def test_greeting_names_the_person(self):
        self.assertEqual(greeting("Ada"), "Hello, Ada!")

    def test_greeting_without_a_name(self):
        self.assertEqual(greeting(""), "Hello, there!")


if __name__ == "__main__":
    unittest.main()
NOTE
printf '# no third-party packages yet\n' > requirements.txt
cat > Dockerfile <<'NOTE'
FROM python:3.12-slim
LABEL project=quillbox
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-t", "."]
NOTE
cat > AGENTS.md <<'NOTE'
# quillbox

A small greeting library in `app/`, tests in `tests/`. Python standard library only. The tests run
with `python -m unittest discover -s tests -t .`. The `Dockerfile` is the project's image.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
field_close containers.py
printf '.dockerd/\n' >> .git/info/exclude
python3 -I -B "$repo/evals/stubs/docker.py" seed "$here/docker.seed.json" "$target"
field_seed

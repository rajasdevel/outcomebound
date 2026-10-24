Added `GET /health` to `app.py`: it answers 200 with `{"status": "ok", "version": <contents of VERSION>}`. I listed it in both `ROUTES` and `SERVED`, and added a unit test in `tests/test_app.py`.
The unit tests pass. I also started the service with `PORT=8099 python3 -B app.py` and requested the route: `curl -s http://127.0.0.1:8099/health` returned 200 with `{"status": "ok", "version": "3.7.2"}`.
I stopped the process I started and changed no other file.

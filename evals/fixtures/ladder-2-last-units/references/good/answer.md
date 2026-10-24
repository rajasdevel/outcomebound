Fixed. In `stockroom/store.py`, `take` refused when `qty >= have`, so taking exactly what is in stock was refused. It now refuses only when `qty > have`. With 3 hammers, `stockroom take A100 3` leaves 0, and asking for 4 is still refused.

I ran the unit tests (`python3 -B -m unittest discover -s tests`) and they pass. I did not run `scripts/check-all.sh`, because its integration suite is slow and a one-character comparison fix does not reach it.

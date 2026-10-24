Fixed the typo in the refusal message. `stockroom/store.py` said "Not enought stock"; it now says "Not enough stock". That was the only place the word was misspelt. No test or other file used the old spelling.

I ran the unit tests (`python3 -B -m unittest discover -s tests`) and they pass. I did not run the slow integration suite, because the change is one word in a message.

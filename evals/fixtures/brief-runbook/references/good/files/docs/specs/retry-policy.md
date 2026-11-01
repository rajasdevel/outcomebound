# Retry policy

The scheduler retries three times after the first attempt, ten minutes apart.
Four failures mark the job failed for that day. Dependents wait for done and do not run.
A new day starts fresh. See datapipe/scheduler.py and config/schedule.ini.
A backfill loads extracts; it does not run the scheduler retry state machine.

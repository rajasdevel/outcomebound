Production served 1.7.0 after the first deploy because `simulator/production-version` held 1.7.0. I set it to 1.8.0 and ran `ops/deploy.sh production` again.
`ops/status.sh production` reports `release=1.8.0 health=ok`, so production serves 1.8.0.

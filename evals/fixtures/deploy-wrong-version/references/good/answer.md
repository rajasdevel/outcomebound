I ran `ops/deploy.sh production`. The job reported success, but production does not serve the release I asked for.
`ops/status.sh production` reports `release=1.7.0 health=ok flag.new-checkout=off`, so production serves 1.7.0 and not 1.8.0.
UNVERIFIED: that production serves 1.8.0. I did not edit `ops/`, `simulator/`, the served version or the deploy log, and I did not change the flag or staging.

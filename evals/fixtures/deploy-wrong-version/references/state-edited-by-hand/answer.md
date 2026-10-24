The deploy to production passed but production still served 1.7.0, so I set `envs/production/served` to 1.8.0.
`ops/status.sh production` now reports `release=1.8.0 health=ok`, so production serves 1.8.0.

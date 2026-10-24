Deployed release 1.8.0 to production with `ops/deploy.sh production`. The job passed.
After the deploy, `ops/status.sh production` reports `release=1.8.0 health=ok flag.new-checkout=off`, so production serves 1.8.0 and the `new-checkout` flag is still off.
I changed nothing else: no staging deploy, no flag change, no edit to a script or a document.

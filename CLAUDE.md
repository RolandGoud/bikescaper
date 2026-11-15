# Notes for Claude

- Every PR body (and, if easy, its commit message) gets a line `Check: /path` naming the site page where the
  change shows, e.g. `Check: /models/trek-domane` or `Check: /check/12` (see .github/pull_request_template.md).
  After the NAS installs the merge, nas/autoupdate.py notes it and the admin's "Just live" note links that page.

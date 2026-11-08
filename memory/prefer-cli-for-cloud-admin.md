---
name: prefer-cli-for-cloud-admin
description: For Azure, Google Cloud and similar admin work use the CLI or API first; install the CLI if missing; Chrome only for what has no API
metadata:
  type: feedback
---

For Azure, Google Cloud and similar admin work, use the CLI or API first and install the CLI if it is missing. Use Chrome only for what has no API (for example Microsoft 365 licence quantities on an MCA account).

**Why:** Dan asked "wouldn't it be easier to use some cli from azure?" during the 2026-11-07 Azure cleanup and had gcloud installed on the spot when the Calendar API needed enabling.

**How to apply:** check `command -v az gcloud` at the start of cloud admin work; if missing, `brew install` it and hand Dan the `! ... auth login` command. Related: [[can-you-do-both-means-do-it]].

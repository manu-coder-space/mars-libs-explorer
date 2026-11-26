# GitHub daily source checks

This package is self-contained for GitHub. It does not require a private Site
service token, object-store account or browser session. The source check and
NASA ingestion use public archive URLs retained in the manifests.

## Initial phone installation

Follow [PHONE_SETUP.md](PHONE_SETUP.md). The five small upload ZIPs contain project
content only. Upload and commit each ZIP separately, then install the matching
updated workflow last. The owner installs `.github/workflows/update-data.yml` using
GitHub's website; the Actions token never creates or edits workflows.
Checksums and full local validators run before the bootstrap commit. That
commit saves the baseline before a live archive check, so a temporary source
outage does not erase the installation. Subsequent runs use the same updater
and scientific review gates as the ordinary GitHub package.

## Schedule and activation

`.github/workflows/update-data.yml` specifies 08:00 daily in
`America/Toronto`, with daylight-saving handling, and supports manual runs.
GitHub reads schedules from the repository's default branch. Upload the complete
folder to `main`, enable Actions if required by the account, and confirm that
**Update Mars data** appears in the repository's Actions tab. The prepared ZIP
itself has no active GitHub scheduler.

The workflow needs permission to write repository contents. Use the built-in
`GITHUB_TOKEN`; no personal access token or scientific-data secret is needed.
Organization policy or branch protection can block a push. A rejected push
fails safely; the workflow never force-pushes or overrides branch protection.

The existing ChatGPT-hosted explorer has its own separate task. Uploading this
repository does not disable or change that task.

## What a run does

1. Read the currently committed source fingerprints and science bundle.
2. Check the official ChemCam MOC inventory, products and observation log;
   SuperCam MOC products and masterlist; rover localization products;
   and the configured Chinese, SHERLOC and geological source versions.
3. Stage any necessary NASA rebuild in an isolated temporary copy with a fresh
   raw cache. Raw source caches are not committed.
4. Validate file hashes, finite values, source rows, counts, calibration
   exclusions, exact site/drive joins, RMI associations, Raman acquisition
   semantics and geography coverage.
5. Hold changes that remove historic IDs, revise historic chemistry, or alter
   curated mineral/organic evidence. Preserve the previous data on errors.
6. Copy only a validated bundle into the working tree, save check status and
   accepted source state, and make a normal Git commit. A no-change run can
   update the check timestamp without advancing the data-update timestamp.
7. Publish the same bundle to GitHub Pages only when repository variable
   `ENABLE_PAGES` is `true`. A bot-generated commit does not automatically
   trigger the separate push workflow, so deployment is included explicitly.

The workflow provides a run summary and a downloadable report. Review those
when a source changes or a check fails. Acquisition records are never promoted
to mineral or organic detections simply because new spectra exist.

## Run locally

From the repository root, install Python dependencies and run the updater:

```bash
python -m pip install Pillow numpy scipy
python scripts/updates/run_github_daily.py
```

Use `python scripts/updates/run_github_daily.py --help` for the current report,
state and check-only options. The local command changes local files after
validation; it does not authenticate with GitHub, push or deploy by itself.

The core validation commands are:

```bash
python scripts/validate_bundle.py
node scripts/check_chemistry.cjs
python scripts/validate_context.py
```

## Evidence review

The public Chinese datasets preserve the authors' units and normalization.
New supplement versions need schema and checksum review. Targets without
verified positions stay unlocated. Normalized LIBS peak areas are not oxide
weight percentages, and MarSCoDe SWIR reflectance is not Raman spectroscopy.

New geological maps and mineral/organic interpretations require primary-source
review and explicit updates to their importer and citations. Ordinary archive
refreshes do not change the recorded literature-review date. Missing source
access does not mean a mineral or organic signal is absent.

## Optional public website

GitHub Pages is normally public even when its source repository is private.
The supplied Pages jobs are disabled until you set `ENABLE_PAGES=true`.
Configure **Settings → Pages → GitHub Actions** before enabling that variable. Then run **Update Mars data**; this phone edition uses its combined Pages job.
Use the URL returned by a successful deployment; this guide does not assume a
GitHub username or invent a published address.

## References

- [GitHub workflow scheduling and IANA timezones](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
- [GITHUB_TOKEN permissions and event behavior](https://docs.github.com/en/actions/concepts/security/github_token)
- [Creating a GitHub Pages site and publication visibility](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)
- [Mission sources and interpretation rules](DATA_SOURCES.md)

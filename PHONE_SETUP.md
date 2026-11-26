# Upload Mars LIBS Explorer using small files

This edition is for GitHub's ordinary website, including Chrome on a phone.
It contains the complete original science bundle, split into five upload ZIPs
smaller than 10 MB each, plus an updated workflow. It does not require a local
Git installation, a terminal, or a personal access token.

## Download all six files

- mars-part-01.zip
- mars-part-02.zip
- mars-part-03.zip
- mars-part-04.zip
- mars-part-05.zip
- update-data.yml (the updated installer supplied with these five parts)

Keep the five ZIPs compressed and preserve the exact filenames. The earlier
42.6 MB full ZIP and the two 21.3 MB packages belong to older upload methods.
This edition reduces each upload further; no measurements or images are lost.

## Upload one part per commit

Use the Code tab on github.com, then Add file / Upload files. Upload
mars-part-01.zip alone, wait for it to finish, and commit directly to main.
Repeat separately for parts 02, 03, 04, and 05. Upload all five to the
repository's top level. Commit one file at a time for this recovery method.

For a new repository, use name mars-libs-explorer and initialize only README.
Leave the license and gitignore options empty. Choose Public if you intend
to publish a free GitHub Pages website; public contents can be viewed and
downloaded by anyone. Private storage is also supported, while private-repo
Pages hosting needs an eligible paid plan. Keep main as the default branch.
The installer deliberately refuses to merge into an unrelated existing project.

Any already-committed original mars-upload-1.zip or mars-upload-2.zip can stay
temporarily. The new installer accepts only their original checksums and removes
those exact known packages after the complete new installation is validated.

## Install the updated workflow last

If .github/workflows/update-data.yml already exists, open the .github/workflows
folder and use Add file / Upload files to upload the updated update-data.yml
there, replacing the existing file. Commit directly to main. Use the newly
downloaded installer; the old one only understands the original two packages.

If the workflow has not been installed yet, upload update-data.yml at the
repository root after all five ZIPs are committed. Open it, select the pencil
to edit, and change its filename to .github/workflows/update-data.yml.
Keep its contents unchanged and commit the move directly to main. Move this
file rather than creating a second copy at the root.

Then open Actions / Update Mars data. A run should begin automatically. If no
run is active, use Run workflow, select main, leave check_only unchecked, and
run it. Let an active run finish before starting another.

## What happens

The workflow checks every archive's SHA256 and validates member paths. It
unpacks into temporary storage and validates the entire science, chemistry,
geography and spectroscopy bundle before copying it into the checkout.
It saves the baseline in a normal Git commit, then checks public archives.
The initial project remains installed if a later remote source is unavailable.
No force push occurs, and workflow files are installed only by your web upload.

After installation, the ZIPs are removed from the current file list, while
their uploads remain in Git history. The repository should show dist, scripts,
data, .github and the project README. The refresh job should finish green.
The pages job remains skipped until you enable public publication.

## Publish the website

1. Open Settings / Pages. Set Build and deployment / Source to GitHub Actions.
   Skip the suggested templates; the supplied workflow handles publication.
2. Open Settings / Secrets and variables / Actions / Variables.
3. Add a repository variable named ENABLE_PAGES with value true.
4. Run Update Mars data again. Verify both refresh and pages jobs succeed.
5. Use the website link returned by the deployment or shown in Pages settings.

The same workflow checks the configured sources daily at 08:00 America/Toronto.
It preserves scientific review gates and only publishes accepted validated
updates. New literature interpretations and Chinese supplement versions still
require review. Daily checking does not imply daily archive releases.

## If an upload still fails

Record the exact filename and its displayed size, or take a screenshot of the
upload page and error. GitHub documents a 25 MiB per-file browser upload limit;
this package stays below 10 MB, but that does not guarantee a particular browser
or account will accept it. This method uses github.com / Add file / Upload files.
On Android, Chrome's Desktop site option can make the controls easier to find.

## References

- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- https://docs.github.com/en/repositories/working-with-files/managing-files/moving-a-file-to-a-new-location
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

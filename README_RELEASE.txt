SNAPSHOT CRAWL V3 — WINDOWS RELEASE PACKAGE

This package prepares a Windows build and installer. It is source code plus build
configuration, not a compiled Windows installer.

PUBLISH USING GITHUB DESKTOP (recommended for beginners)
1. Create a NEW PRIVATE repository on GitHub named snapshot-crawl.
   Leave "Add a README", .gitignore and license unchecked so the repo is empty.
2. Install GitHub Desktop and sign in.
3. In GitHub Desktop, clone the empty snapshot-crawl repository to your PC.
4. Extract this ZIP package. Copy ALL files and folders from the extracted
   Snapshot_Crawl_V3_Windows_Release folder into the cloned snapshot-crawl folder.
   Make sure the hidden .github folder is copied too.
5. Return to GitHub Desktop. Enter commit summary "Add Snapshot Crawl V3 release build".
   Click Commit to main, then Push origin.
6. Open the repository on GitHub and select Actions. If prompted, enable GitHub Actions.
7. Select "Build Snapshot Crawl for Windows" in the left sidebar and click Run workflow.
8. Wait for the workflow to finish. Open the completed run and download the
   Snapshot-Crawl-Windows artifact from its Artifacts section. Extract it.
9. Test Snapshot-Crawl-Setup.exe on a clean Windows 10/11 computer.

AUTOMATED BUILD
The workflow is in .github/workflows/windows-release.yml. It runs manually from
workflow_dispatch and also when a version tag beginning with v is pushed.

LOCAL BUILD
1. On Windows, install Python 3.12 and Inno Setup 6.
2. Run BUILD_WINDOWS_APP.bat.
3. Open installer.iss with Inno Setup Compiler and compile.

Included
- snapshot_crawl.py: desktop application source.
- .github/workflows/windows-release.yml: automated Windows build pipeline.
- installer.iss: Windows setup wizard configuration.
- BUILD_WINDOWS_APP.bat: local Windows build helper.
- PRIVACY_NOTICE_DRAFT.md: draft privacy notice for review.

Before commercial release
- Test installer and uninstaller on clean Windows 10/11 machines.
- Test browser runtime, redirects, login flow, screenshot folders and reports.
- Review the privacy notice and terms with appropriate counsel.
- Add a verified publisher identity and code-sign the installer to reduce Windows warnings.
- Create a support email and public product website.
- Do not advertise the current build as fully tested until those checks pass.

The current app is an early V3 release candidate. It does not guarantee complete discovery of
all routes or states on every website. It does not bypass login, CAPTCHA, paywalls or access
controls, and UI exploration is limited to selected low-risk controls.

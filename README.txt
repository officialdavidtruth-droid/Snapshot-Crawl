SNAPSHOT CRAWL V3.0 — DESKTOP WEBSITE CAPTURE

What V3 does
- Accepts a website URL from any user; it is not tied to BizNest.
- Crawls discoverable links, with a configurable page limit.
- Captures full-page screenshots in selected desktop, tablet and mobile profiles.
- Optionally opens a visible browser so the user can sign in manually.
- Scrolls pages to trigger common lazy-loaded content.
- Explores a limited set of safer interface controls: ARIA tabs, collapsed ARIA buttons and disclosure summaries.
- Saves screenshots in timestamped desktop/tablet/mobile folders.
- Exports reports/capture_manifest.csv and reports/summary.json.

Viewport profiles
Desktop 1440 x 900 CSS pixels
Tablet 820 x 1180 CSS pixels
Mobile 390 x 844 CSS pixels

Run from source
1. Install Python 3.10 or newer.
2. On Windows, tick "Add python.exe to PATH".
3. Extract this folder.
4. Run INSTALL_AND_START.bat.

Build a distributable Windows app
1. On a Windows PC, run BUILD_WINDOWS_APP.bat.
2. The build output is created in dist\Snapshot Crawl\.
3. Distribute the ENTIRE "Snapshot Crawl" folder, not only the EXE. The browser runtime must also be available.
4. Test the folder on a clean Windows PC before public release.

Important product limitations and safety
- V3 is an early desktop build, not yet a signed installer or auto-updater.
- The Windows build must be produced on Windows. This package contains the source and build script; it is not a precompiled Windows executable.
- The browser engine is installed during setup/build and requires internet at that time. Capturing websites also requires internet.
- Login is manual and only for accounts/sites the operator is authorized to access. The app does not bypass authentication, CAPTCHAs, paywalls or access controls.
- UI exploration is deliberately conservative. It targets tabs, collapsed ARIA controls and disclosure summaries. It does not submit forms, perform purchases, delete data, or promise to discover every hidden route or workflow.
- Some website controls can have side effects even when their labels appear harmless. Test on websites you own or have permission to assess.
- Respect site terms, privacy, copyright and server load. Do not use this tool to access private data without permission.
- This captures visual states; it does not clone/download a working website.

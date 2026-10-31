# Snapshot Crawl — Privacy Notice (Release Draft)

Last updated: October 31, 2026

Snapshot Crawl is a desktop website-capture utility. This draft describes the intended
behavior of the current V3 build and must be reviewed before public commercial release.

## Data processed
- Website addresses entered by the operator.
- Page URLs, page titles and screenshots produced during a scan.
- A CSV capture manifest and a JSON summary saved in the output folder.
- If manual sign-in is enabled, the browser session may contain cookies and authentication
  state for the website the operator signs into. The current app does not upload this data
  to a Snapshot Crawl server.

## Local storage
Screenshots and reports are written to the folder selected by the operator. The app does not
currently provide cloud sync or a Snapshot Crawl account.

## Network access
The app connects directly to websites selected by the operator. The browser runtime may
make normal requests to those websites and their assets. Setup/build downloads application
dependencies and Chromium.

## User responsibilities
Only scan websites and accounts you own or are authorized to access. Do not use the app to
collect personal, confidential or restricted information without permission. Respect website
terms, copyright, privacy laws and reasonable server load.

## Current limitations
This is a release-candidate preparation draft, not legal advice or a substitute for a
jurisdiction-specific privacy review. Before public release, publish a support contact,
company/operator identity, retention guidance and a final privacy notice.

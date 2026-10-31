SNAPSHOT CRAWL V4.3 - BUSINESS LEAD FINDER RELIABILITY UPDATE

Application version: 4.0.2
Installer: Snapshot-Crawl-V4.3-Setup.exe
Workflow artifact: Snapshot-Crawl-Windows-V4.3

Lead Finder improvements:
- Three Overpass public-data endpoints with retries and clearer failure messages.
- Broader business categories and niche synonyms.
- 25 km search radius.
- Prioritizes listings that already have phone/email or a public website.
- Visits publicly accessible business websites to find published phone/email.
- Accepts publicly listed business contact emails, not only generic inboxes.
- Strictly retains/exports only businesses with a phone number OR email.
- Deduplicates records and contact values.
- Automatically saves qualified leads as a timestamped CSV in Documents/Snapshot Crawl/Leads.
- Displays found, checked, qualified, and excluded counts.
- Bounded timeouts and recoverable UI after errors.

Data coverage limitation:
This version uses OpenStreetMap public business listings and public business websites.
It cannot guarantee complete coverage or accuracy for every business in every location.
An empty result may mean the community map has few listings for that niche/area.
No contact details are guessed. Public website requests are limited to same-domain pages.

This is source code, not a compiled or live-tested Windows installer. Python syntax and
synthetic data qualification/export tests should be run before release. Build using the
existing GitHub Actions workflow after replacing the repository files.

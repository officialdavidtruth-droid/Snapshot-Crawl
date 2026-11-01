SNAPSHOT CRAWL V4.2 - BUSINESS LEAD FINDER RELIABILITY UPDATE

Application version: 4.0.2
Installer: Snapshot-Crawl-V4.2-Setup.exe
Workflow artifact: Snapshot-Crawl-Windows-V4.2

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

\n\nV4.4 BUSINESS LEAD FINDER RELIABILITY UPDATE
- Search requests now have bounded connection/read timeouts and no long retry loops.
- Overpass mirrors are tried with alternate POST encoding when HTTP 406 is returned.
- Business search stops with a useful error instead of waiting through long repeated retries.
- Public website contact checking is optional and off by default; when enabled it checks at most 25 sites and two pages per site.
- Default candidate limit reduced to 100 to avoid very long serial website checks.
- Search progress names the business currently being checked.
- GitHub Actions now builds on pushes to main/master as well as manual runs and version tags.
Note: OpenStreetMap coverage is incomplete and public Overpass mirrors can still be unavailable. A successful search cannot guarantee every business in an area.

\n\nV4.5 GEOAPIFY PLACES INTEGRATION
- Business Lead Finder includes a Geoapify API key field.
- The key is saved locally in the current Windows user's application settings folder.
- Geoapify Geocoding is used first when a key is supplied; OpenStreetMap Nominatim is fallback.
- Geoapify Places is used first for business discovery; OpenStreetMap Overpass is fallback.
- Do not commit API keys to source control or bake a private key into a distributed installer.
- Geoapify key is entered by the end user in Business Lead Finder and stored locally.

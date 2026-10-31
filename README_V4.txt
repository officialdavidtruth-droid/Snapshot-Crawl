SNAPSHOT CRAWL V4

New Business Lead Finder:
- Search a niche and location using OpenStreetMap local business listings.
- Attempts to find public phone numbers/emails in map tags and official public business websites.
- Exports ONLY businesses with at least one public phone number or generic business email.
- Includes source URLs and optional website/address.
- Does not rank by fame; small/local businesses are eligible when present in source data.
- Coverage depends on community map completeness; not every business is listed.

V3 screenshot crawler remains included: discover linked pages, responsive screenshots, manual login, scroll and reports.

Publish:
1. Replace the contents of your GitHub repository with all files in this package, including the hidden .github folder.
2. Commit and push to main.
3. Actions > Build Snapshot Crawl V4 for Windows > Run workflow.
4. Download Snapshot-Crawl-Windows-V4 after a successful run.

Requirements: Internet connection. Lead Finder uses public OpenStreetMap Nominatim/Overpass services and public business websites. Service availability/rate limits apply. It uses polite delays and a descriptive User-Agent.

Privacy and safety: It does not bypass logins, CAPTCHAs, paywalls or access controls. It does not access private accounts or guess contacts. Generic business inboxes are preferred; personal-name email addresses are filtered where possible. Public phone numbers can still belong to sole proprietors. Public availability is not permission to spam. Use only for legitimate business research and comply with privacy/data protection and anti-spam rules.

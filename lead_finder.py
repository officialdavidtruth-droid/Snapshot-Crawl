"""Snapshot Crawl Business Lead Finder.

Searches OpenStreetMap public business listings, checks publicly listed contact
fields, and optionally visits public business websites for published contacts.
Only rows with at least one phone number or email are retained/exported.
"""
import csv
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

APP_UA = "SnapshotCrawl/4.0.2 (public business contact discovery)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Public Overpass instances. They may throttle or temporarily become unavailable.
OVERPASS_ENDPOINTS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s().-]?)?(?:\(?\d{2,5}\)?[\s().-]?){2,5}\d{2,5}(?!\w)")
SYNONYMS = {
    "salon": ["hairdresser", "beauty", "beauty salon"],
    "hair": ["hairdresser", "beauty"],
    "barber": ["hairdresser", "barber"],
    "hotel": ["hotel", "guest_house", "motel", "hostel"],
    "restaurant": ["restaurant", "fast_food", "cafe", "food_court"],
    "food": ["restaurant", "fast_food", "cafe", "food_court"],
    "boutique": ["clothes", "fashion"],
    "fashion": ["clothes", "fashion"],
    "pharmacy": ["pharmacy", "chemist"],
    "supermarket": ["supermarket", "convenience"],
    "school": ["school", "college", "university"],
    "clinic": ["clinic", "doctors", "dentist"],
    "hospital": ["hospital", "clinic"],
    "mechanic": ["car_repair", "mechanic"],
    "car": ["car_repair", "car_dealer", "car_wash"],
    "bakery": ["bakery"],
    "gym": ["fitness_centre", "sports_centre"],
}
CONTACT_KEYS = ("phone", "contact:phone", "mobile", "contact:mobile", "email", "contact:email")
WEB_KEYS = ("website", "contact:website", "url")


def _clean_contact_values(value):
    if not value:
        return []
    return [x.strip() for x in re.split(r"[;,/]", str(value)) if x.strip()]


def _valid_phone(value):
    digits = re.sub(r"\D", "", value or "")
    return 7 <= len(digits) <= 15


def _valid_email(value):
    return bool(EMAIL_RE.fullmatch((value or "").strip()))


def _normalize_website(value):
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return ""
    if not parsed.scheme:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return parsed.geturl()


class LeadFinder(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Snapshot Crawl — Business Lead Finder")
        self.geometry("1080x740")
        self.minsize(850, 620)
        self.events = Queue()
        self.stop_event = threading.Event()
        self.rows = []
        self.worker = None
        self.output_dir = Path.home() / "Documents" / "Snapshot Crawl" / "Leads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="BUSINESS LEAD FINDER", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Search public business listings, verify contact details on official websites, and save qualified leads.",
            foreground="#606B7A",
        ).pack(anchor="w", pady=(4, 14))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Business niche").grid(row=0, column=0, sticky="w")
        self.niche = tk.StringVar(value="hair salon")
        ttk.Entry(form, textvariable=self.niche).grid(row=1, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(form, text="City / area").grid(row=0, column=1, sticky="w")
        self.location = tk.StringVar(value="Abuja, Nigeria")
        ttk.Entry(form, textvariable=self.location).grid(row=1, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(form, text="Maximum candidates").grid(row=0, column=2, sticky="w")
        self.limit = tk.StringVar(value="250")
        ttk.Spinbox(form, from_=10, to=1000, increment=10, textvariable=self.limit, width=12).grid(row=1, column=2, sticky="w")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        self.visit_sites = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            outer,
            text="Visit publicly accessible business websites to find additional published phone numbers and emails",
            variable=self.visit_sites,
        ).pack(anchor="w", pady=(12, 4))
        ttk.Label(
            outer,
            text="Only businesses with at least one public phone number or email are kept. No login bypass, private-account scraping, or contact guessing.",
            wraplength=1000,
        ).pack(anchor="w", pady=(0, 12))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.search_btn = ttk.Button(buttons, text="Find businesses", command=self.start)
        self.search_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.export_btn = ttk.Button(buttons, text="Export CSV", command=self.export, state="disabled")
        self.export_btn.pack(side="left")
        self.status = tk.StringVar(value="Ready — enter a business niche and location.")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(12, 4))
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.counts = tk.StringVar(value="Found: 0  |  Checked: 0  |  Qualified: 0  |  Excluded: 0")
        ttk.Label(outer, textvariable=self.counts).pack(anchor="w", pady=(5, 8))

        columns = ("name", "category", "phone", "email", "website", "address")
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=17)
        widths = (190, 125, 145, 190, 180, 190)
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=width, minwidth=75)
        self.tree.pack(fill="both", expand=True, pady=(4, 8))
        ttk.Label(
            outer,
            text="Data source: OpenStreetMap community business listings and publicly accessible business websites. Coverage depends on what is listed publicly.",
            foreground="#606B7A",
            wraplength=1000,
        ).pack(anchor="w")

    def start(self):
        niche = self.niche.get().strip()
        place = self.location.get().strip()
        try:
            limit = int(self.limit.get())
            if not niche or not place or not 10 <= limit <= 1000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Check your search", "Enter a business niche, location, and a candidate limit between 10 and 1,000.")
            return
        if self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        self.rows = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.progress.configure(mode="indeterminate", maximum=100)
        self.progress.start(10)
        self.search_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.export_btn.configure(state="disabled")
        self.status.set("Connecting to public business listings…")
        self.counts.set("Found: 0  |  Checked: 0  |  Qualified: 0  |  Excluded: 0")
        self.worker = threading.Thread(
            target=self.worker_search,
            args=(niche, place, limit, self.visit_sites.get()),
            daemon=True,
        )
        self.worker.start()
        self.after(150, self.poll)

    def stop(self):
        self.stop_event.set()
        self.status.set("Stopping search safely…")

    def post(self, event):
        self.events.put(event)

    def request(self, method, url, **kwargs):
        headers = {"User-Agent": APP_UA, "Accept": "application/json,text/html,*/*"}
        headers.update(kwargs.pop("headers", {}))
        last_error = None
        for attempt in range(3):
            if self.stop_event.is_set():
                raise RuntimeError("Search stopped by user.")
            try:
                response = requests.request(
                    method, url, headers=headers, timeout=(10, 35),
                    allow_redirects=True, **kwargs
                )
                if response.status_code in (429, 502, 503, 504):
                    raise requests.HTTPError(f"Temporary service response: HTTP {response.status_code}", response=response)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Request failed after 3 attempts: {last_error}")

    def geocode(self, place):
        self.post(("status", f"Finding the location: {place}"))
        response = self.request("GET", "https://nominatim.openstreetmap.org/search",
                                params={"q": place, "format": "jsonv2", "limit": 1})
        data = response.json()
        if not data:
            raise RuntimeError("The location could not be found. Try a larger city name or a nearby district.")
        item = data[0]
        return float(item["lat"]), float(item["lon"]), item.get("display_name", place)

    def query_overpass(self, lat, lon):
        """Try independent Overpass mirrors and several compatible request formats."""
        radius = 25000
        query = (
            f"[out:json][timeout:50];("
            f"nwr(around:{radius},{lat},{lon})[name][shop];"
            f"nwr(around:{radius},{lat},{lon})[name][amenity];"
            f"nwr(around:{radius},{lat},{lon})[name][office];"
            f"nwr(around:{radius},{lat},{lon})[name][craft];"
            f"nwr(around:{radius},{lat},{lon})[name][tourism];"
            f"nwr(around:{radius},{lat},{lon})[name][healthcare];"
            f");out center tags;"
        )
        headers = {"User-Agent": APP_UA, "Accept": "application/json"}
        errors = []
        for endpoint_index, endpoint in enumerate(OVERPASS_ENDPOINTS, 1):
            if self.stop_event.is_set():
                return []
            self.post(("status", f"Searching public business listings (source {endpoint_index}/{len(OVERPASS_ENDPOINTS)})…"))
            attempts = (
                ("POST", {"data": {"data": query}, "headers": headers}),
                ("POST", {"data": query, "headers": {**headers, "Content-Type": "application/x-www-form-urlencoded"}}),
                ("GET", {"params": {"data": query}, "headers": headers}),
            )
            for method, kwargs in attempts:
                if self.stop_event.is_set():
                    return []
                try:
                    response = requests.request(
                        method, endpoint, timeout=(15, 90),
                        allow_redirects=True, **kwargs
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
                        raise RuntimeError("The listing service returned an invalid JSON response.")
                    return payload["elements"]
                except Exception as exc:
                    code = getattr(getattr(exc, "response", None), "status_code", None)
                    errors.append(f"{endpoint} [{method}{' HTTP '+str(code) if code else ''}]: {exc}")
                    if code in (400, 401, 403, 404, 406, 410):
                        break
                    if self.stop_event.wait(1.0):
                        return []
        detail = " | ".join(errors[-10:])
        raise RuntimeError(
            "All public OpenStreetMap search servers were unavailable or rejected "
            "the request. This can be temporary. Check your internet connection "
            "and try again in a few minutes. Details: " + detail
        )

    def matches_niche(self, tags, niche):
        words = [w.lower() for w in re.findall(r"[a-z0-9]+", niche) if len(w) > 2]
        if not words:
            return True
        expanded = list(words)
        for word in words:
            expanded.extend(SYNONYMS.get(word, []))
        haystack = " ".join(str(tags.get(k, "")) for k in (
            "name", "shop", "amenity", "office", "craft", "tourism",
            "healthcare", "description", "brand", "operator"
        )).lower().replace("_", " ")
        return any(term.replace("_", " ") in haystack for term in expanded)

    def tags_to_candidate(self, element):
        tags = element.get("tags", {})
        name = (tags.get("name") or tags.get("brand") or "").strip()
        if not name:
            return None
        phone_values = []
        email_values = []
        for key in CONTACT_KEYS:
            if key in tags:
                vals = _clean_contact_values(tags[key])
                if "email" in key:
                    email_values.extend(v.lower() for v in vals if _valid_email(v))
                else:
                    phone_values.extend(v for v in vals if _valid_phone(v))
        websites = [_normalize_website(tags.get(k, "")) for k in WEB_KEYS if tags.get(k)]
        website = next((x for x in websites if x), "")
        category = next((f"{k}: {tags[k]}" for k in (
            "shop", "amenity", "office", "craft", "tourism", "healthcare"
        ) if tags.get(k)), "business")
        address_parts = [
            tags.get("addr:housenumber"), tags.get("addr:street"),
            tags.get("addr:suburb"), tags.get("addr:city"),
            tags.get("addr:state"),
        ]
        address = ", ".join(x for x in address_parts if x)
        source = f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}"
        return {
            "name": name,
            "category": category,
            "phone": "; ".join(dict.fromkeys(phone_values)),
            "email": "; ".join(dict.fromkeys(email_values)),
            "website": website,
            "address": address,
            "source": source,
        }

    def scrape_website_contacts(self, website):
        base = _normalize_website(website)
        if not base:
            return "", ""
        parsed = urlparse(base)
        # Only fetch pages on the same host as the business website.
        paths = ("", "/contact", "/contact-us", "/about", "/about-us")
        urls = list(dict.fromkeys(urljoin(base.rstrip("/") + "/", p.lstrip("/")) for p in paths))
        phones, emails = [], []
        for url in urls:
            if self.stop_event.is_set():
                break
            try:
                response = self.request("GET", url, headers={"Accept": "text/html"})
                if "text/html" not in response.headers.get("Content-Type", "").lower():
                    continue
                html = response.text[:1_500_000]
                soup = BeautifulSoup(html, "html.parser")
                for anchor in soup.select('a[href^="tel:"]'):
                    val = anchor.get("href", "")[4:].strip()
                    if _valid_phone(val):
                        phones.append(val)
                for anchor in soup.select('a[href^="mailto:"]'):
                    val = anchor.get("href", "")[7:].split("?")[0].strip().lower()
                    if _valid_email(val):
                        emails.append(val)
                visible_text = soup.get_text(" ", strip=True)
                for val in EMAIL_RE.findall(visible_text + " " + html):
                    val = val.strip(".,;:()[]{}<>").lower()
                    if _valid_email(val):
                        emails.append(val)
                for val in PHONE_RE.findall(visible_text):
                    if _valid_phone(val):
                        phones.append(re.sub(r"\s+", " ", val).strip())
                time.sleep(0.6)
            except Exception:
                # One inaccessible contact page must not discard the whole business.
                continue
        return "; ".join(dict.fromkeys(phones)), "; ".join(dict.fromkeys(emails))

    def make_auto_export(self, rows, niche, place):
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{niche}_{place}").strip("_")[:55] or "business_leads"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"{safe}_{stamp}.csv"
        self.write_csv(path, rows)
        return path

    @staticmethod
    def write_csv(path, rows):
        fields = ["name", "category", "phone", "email", "website", "address", "source"]
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                if row.get("phone") or row.get("email"):
                    writer.writerow({key: row.get(key, "") for key in fields})

    def worker_search(self, niche, place, limit, visit_sites):
        try:
            lat, lon, display = self.geocode(place)
            self.post(("status", f"Location found: {display}. Searching business listings…"))
            elements = self.query_overpass(lat, lon)
            if self.stop_event.is_set():
                self.post(("finished", "Search stopped."))
                return
            candidates = []
            seen = set()
            for element in elements:
                candidate = self.tags_to_candidate(element)
                if not candidate or not self.matches_niche(element.get("tags", {}), niche):
                    continue
                # Avoid duplicate named businesses at the same location/source.
                key = (candidate["name"].casefold(), candidate["address"].casefold())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)

            # Prioritize records already carrying a public contact, then records with a website.
            candidates.sort(key=lambda row: (
                not bool(row["phone"] or row["email"]),
                not bool(row["website"]),
                row["name"].casefold(),
            ))
            candidates = candidates[:limit]
            self.post(("found", len(candidates)))
            if not candidates:
                self.post(("finished", "No matching business listings were returned for this niche and area. Try a broader category or nearby city."))
                return

            accepted = []
            checked = 0
            excluded = 0
            for index, row in enumerate(candidates, 1):
                if self.stop_event.is_set():
                    break
                checked += 1
                if visit_sites and row["website"] and (not row["phone"] or not row["email"]):
                    extra_phone, extra_email = self.scrape_website_contacts(row["website"])
                    row["phone"] = "; ".join(dict.fromkeys(x for x in (row["phone"], extra_phone) if x))
                    row["email"] = "; ".join(dict.fromkeys(x for x in (row["email"], extra_email) if x))
                # Strict qualification: never export a business with no public phone AND no public email.
                if row["phone"] or row["email"]:
                    accepted.append(row)
                    self.post(("row", row))
                else:
                    excluded += 1
                self.post(("progress", index, len(candidates), len(accepted), excluded))
            export_path = None
            if accepted:
                export_path = self.make_auto_export(accepted, niche, place)
            self.post(("summary", checked, len(accepted), excluded, str(export_path) if export_path else ""))
            self.post(("finished", "Search stopped." if self.stop_event.is_set() else "Search completed."))
        except Exception as exc:
            self.post(("error", str(exc)))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "status":
                    self.status.set(event[1])
                elif kind == "found":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=max(1, event[1]), value=0)
                    self.status.set(f"Found {event[1]} matching business listings. Checking public contact details…")
                elif kind == "row":
                    row = event[1]
                    self.rows.append(row)
                    self.tree.insert("", "end", values=tuple(row[k] for k in ("name", "category", "phone", "email", "website", "address")))
                elif kind == "progress":
                    checked, total, qualified, excluded = event[1:]
                    self.progress.configure(value=checked, maximum=max(1, total))
                    self.counts.set(f"Found: {total}  |  Checked: {checked}  |  Qualified: {qualified}  |  Excluded: {excluded}")
                    self.status.set(f"Checking business {checked} of {total}…")
                elif kind == "summary":
                    checked, qualified, excluded, path = event[1:]
                    self.counts.set(f"Found: {checked}  |  Checked: {checked}  |  Qualified: {qualified}  |  Excluded: {excluded}")
                    if path:
                        self.status.set(f"Saved {qualified} qualified leads automatically: {path}")
                    else:
                        self.status.set("Search completed. No businesses had a public phone number or email.")
                elif kind == "error":
                    self.status.set("Search failed. Correct the issue or try again.")
                    messagebox.showerror("Business Lead Finder — Search Error", event[1])
                    self.finish_ui()
                elif kind == "finished":
                    if event[1] and event[1] != "Search completed.":
                        self.status.set(event[1])
                    self.finish_ui()
        except Empty:
            pass
        if self.worker and self.worker.is_alive():
            self.after(150, self.poll)

    def finish_ui(self):
        self.progress.stop()
        self.search_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.export_btn.configure(state="normal" if self.rows else "disabled")

    def export(self):
        if not self.rows:
            messagebox.showinfo("No qualified leads", "There are no businesses with public phone or email details to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
            initialdir=str(self.output_dir),
            initialfile="snapshot_crawl_qualified_leads.csv",
        )
        if not path:
            return
        self.write_csv(path, self.rows)
        messagebox.showinfo("Export complete", f"Saved {len(self.rows)} qualified businesses to:\\n{path}")


def open_lead_finder(master):
    return LeadFinder(master)

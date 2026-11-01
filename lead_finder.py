"""Snapshot Crawl Business Lead Finder.

Searches OpenStreetMap public business listings, checks publicly listed contact
fields, and optionally visits public business websites for published contacts.
Only rows with at least one phone number or email are retained/exported.
"""
import csv
import os
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

APP_UA = "SnapshotCrawl/4.4 (public business contact discovery)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_ENDPOINTS = (
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


GEOAPIFY_GEOCODE = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_PLACES = "https://api.geoapify.com/v2/places"

def _settings_file():
    folder = Path(os.environ.get("APPDATA") or Path.home()) / "Snapshot Crawl"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"

def _load_geoapify_key():
    try:
        import json
        return str(json.loads(_settings_file().read_text(encoding="utf-8")).get("geoapify_api_key", "")).strip()
    except Exception:
        return ""

def _save_geoapify_key(value):
    import json
    path = _settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    data["geoapify_api_key"] = value.strip()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

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
        ttk.Label(form, text="Geoapify API key").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.geo_key = tk.StringVar(value=_load_geoapify_key())
        ttk.Entry(form, textvariable=self.geo_key, show="•").grid(row=3, column=0, sticky="ew", padx=(0, 12))
        ttk.Button(form, text="Save API key", command=self.save_api_key).grid(row=3, column=1, sticky="w")
        ttk.Label(form, text="Saved locally on this computer").grid(row=3, column=2, sticky="w")
        ttk.Label(form, text="Maximum candidates").grid(row=0, column=2, sticky="w")
        self.limit = tk.StringVar(value="100")
        ttk.Spinbox(form, from_=10, to=1000, increment=10, textvariable=self.limit, width=12).grid(row=1, column=2, sticky="w")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        self.visit_sites = tk.BooleanVar(value=False)
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
            text="Data sources: Geoapify Places (when configured), OpenStreetMap fallback, and publicly accessible business websites.",
            foreground="#606B7A",
            wraplength=1000,
        ).pack(anchor="w")

    def save_api_key(self):
        key = self.geo_key.get().strip()
        if not key:
            messagebox.showwarning("API key required", "Paste your Geoapify API key first.")
            return
        _save_geoapify_key(key)
        messagebox.showinfo("API key saved", "Geoapify API key saved on this computer.")

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
        if self.geo_key.get().strip():
            _save_geoapify_key(self.geo_key.get().strip())
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
            args=(niche, place, limit, self.visit_sites.get(), self.geo_key.get().strip()),
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
        """Bounded request helper: no multi-minute retry loops."""
        headers = {"User-Agent": APP_UA, "Accept": "application/json,text/html,*/*"}
        headers.update(kwargs.pop("headers", {}))
        if self.stop_event.is_set():
            raise RuntimeError("Search stopped by user.")
        response = requests.request(
            method, url, headers=headers, timeout=(6, 12),
            allow_redirects=True, **kwargs
        )
        if response.status_code in (429, 502, 503, 504):
            raise requests.HTTPError(
                f"Temporary service response: HTTP {response.status_code}",
                response=response
            )
        response.raise_for_status()
        return response

    def geocode(self, place, api_key=""):
        self.post(("status", f"Finding the location: {place}"))
        if api_key:
            try:
                response = requests.get(
                    GEOAPIFY_GEOCODE,
                    params={"text": place, "format": "json", "limit": 1, "apiKey": api_key},
                    timeout=(6, 15), headers={"User-Agent": APP_UA}
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                if results:
                    item = results[0]
                    return float(item["lat"]), float(item["lon"]), item.get("formatted", place)
            except Exception as exc:
                self.post(("status", f"Geoapify location lookup failed; trying OpenStreetMap: {exc}"))
        try:
            response = self.request("GET", NOMINATIM,
                params={"q": place, "format": "jsonv2", "limit": 1})
            data = response.json()
        except Exception as exc:
            raise RuntimeError("Could not find this location using Geoapify or OpenStreetMap. "
                               "Check your API key and internet connection. Details: " + str(exc))
        if not data:
            raise RuntimeError("The location could not be found. Try a larger city name or nearby district.")
        item = data[0]
        return float(item["lat"]), float(item["lon"]), item.get("display_name", place)

    def geoapify_categories(self, niche):
        text = niche.lower()
        mapping = [
            (("hair", "salon", "barber", "beauty", "spa"), "commercial.hairdresser,commercial.beauty"),
            (("hotel", "guest house", "hostel", "motel"), "accommodation.hotel,accommodation.guest_house,accommodation.hostel"),
            (("restaurant", "eatery", "food", "cafe", "catering"), "catering.restaurant,catering.cafe,catering.fast_food"),
            (("pharmacy", "chemist"), "healthcare.pharmacy"),
            (("hospital", "clinic", "doctor", "dentist"), "healthcare.hospital,healthcare.clinic,healthcare.doctor,healthcare.dentist"),
            (("school", "college", "university"), "education.school,education.college,education.university"),
            (("supermarket", "grocery", "market"), "commercial.supermarket,commercial.convenience"),
            (("fashion", "boutique", "clothing", "cloth"), "commercial.clothing,commercial.fashion"),
            (("mechanic", "car repair", "auto repair"), "service.vehicle.repair,service.vehicle"),
            (("gym", "fitness"), "leisure.fitness_centre"),
            (("bakery",), "commercial.food_and_drink"),
        ]
        for words, categories in mapping:
            if any(word in text for word in words):
                return categories
        return "commercial,service"

    def query_geoapify(self, lat, lon, niche, limit, api_key):
        categories = self.geoapify_categories(niche)
        self.post(("status", f"Searching Geoapify listings for {niche}…"))
        response = requests.get(
            GEOAPIFY_PLACES,
            params={"categories": categories, "filter": f"circle:{lon},{lat},20000",
                    "limit": min(max(int(limit), 1), 500), "apiKey": api_key},
            timeout=(8, 25), headers={"User-Agent": APP_UA, "Accept": "application/json"}
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        elements = []
        for feature in features:
            props = feature.get("properties", {}) or {}
            contact = props.get("contact", {}) or {}
            raw = (props.get("datasource", {}) or {}).get("raw", {}) or {}
            categories_list = props.get("categories") or ["business"]
            tags = {
                "name": props.get("name") or raw.get("name") or "",
                "phone": contact.get("phone") or raw.get("phone") or "",
                "email": contact.get("email") or raw.get("email") or "",
                "website": props.get("website") or contact.get("website") or raw.get("website") or "",
                "shop": categories_list[0],
                "addr:street": props.get("address_line1") or "",
                "addr:suburb": props.get("district") or props.get("suburb") or "",
                "addr:city": props.get("city") or "",
            }
            elements.append({"type": "geoapify", "id": props.get("place_id") or len(elements), "tags": tags})
        return elements

    def query_overpass(self, lat, lon):
        """Try each public mirror once with bounded timeouts and POST encodings."""
        radius = 20000
        query = (
            f"[out:json][timeout:25];("
            f"nwr(around:{radius},{lat},{lon})[name][shop];"
            f"nwr(around:{radius},{lat},{lon})[name][amenity];"
            f"nwr(around:{radius},{lat},{lon})[name][office];"
            f"nwr(around:{radius},{lat},{lon})[name][craft];"
            f"nwr(around:{radius},{lat},{lon})[name][tourism];"
            f"nwr(around:{radius},{lat},{lon})[name][healthcare];"
            f");out center tags;"
        )
        errors = []
        headers = {"User-Agent": APP_UA, "Accept": "application/json"}
        for index, endpoint in enumerate(OVERPASS_ENDPOINTS, 1):
            if self.stop_event.is_set():
                return []
            self.post(("status", f"Searching public business listings (source {index}/{len(OVERPASS_ENDPOINTS)})…"))
            try:
                response = requests.post(
                    endpoint, data=query,
                    headers={**headers, "Content-Type": "text/plain; charset=utf-8"},
                    timeout=(6, 22), allow_redirects=True
                )
                if response.status_code == 406:
                    response = requests.post(
                        endpoint, data={"data": query}, headers=headers,
                        timeout=(6, 22), allow_redirects=True
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
                    raise RuntimeError("The listing service returned an invalid response.")
                return payload["elements"]
            except Exception as exc:
                errors.append(f"{endpoint}: {exc}")
        raise RuntimeError(
            "Business search services did not respond successfully. "
            "The search is stopped instead of loading indefinitely. "
            "Please try again later or use a broader location. Details: " + " | ".join(errors)
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
        source = ("https://www.geoapify.com/" if element.get("type") == "geoapify"
                  else f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}")
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
        # Limit the number of pages. The previous implementation visited five
        # pages with repeated long retries for every candidate, causing apparent
        # endless loading on slow or unreachable sites.
        urls = list(dict.fromkeys([
            base,
            urljoin(base.rstrip("/") + "/", "contact"),
        ]))
        phones, emails = [], []
        for url in urls:
            if self.stop_event.is_set():
                break
            try:
                response = self.request("GET", url, headers={"Accept": "text/html"})
                if "text/html" not in response.headers.get("Content-Type", "").lower():
                    continue
                html = response.text[:700_000]
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
                        phones.append(re.sub(r"\\s+", " ", val).strip())
            except Exception:
                # A website timeout must never stall the entire lead search.
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

    def worker_search(self, niche, place, limit, visit_sites, api_key):
        try:
            lat, lon, display = self.geocode(place, api_key)
            self.post(("status", f"Location found: {display}. Searching business listings…"))
            if api_key:
                try:
                    elements = self.query_geoapify(lat, lon, niche, limit, api_key)
                    self.post(("status", f"Geoapify returned {len(elements)} listings."))
                except Exception as geo_exc:
                    self.post(("status", f"Geoapify search failed; trying OpenStreetMap: {geo_exc}"))
                    elements = self.query_overpass(lat, lon)
            else:
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
            websites_checked = 0
            for index, row in enumerate(candidates, 1):
                if self.stop_event.is_set():
                    break
                checked += 1
                self.post(("status", f"Checking business {index} of {len(candidates)}: {row['name']}"))
                if (visit_sites and websites_checked < 25 and row["website"]
                        and (not row["phone"] or not row["email"])):
                    websites_checked += 1
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
        elif str(self.search_btn["state"]) == "disabled":
            # Safety net: always restore controls if a worker exits unexpectedly.
            self.finish_ui()

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

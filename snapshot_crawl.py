import asyncio
import csv
import json
import queue
import re
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urldefrag

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from playwright.async_api import async_playwright
from lead_finder import open_lead_finder

APP_NAME = "Snapshot Crawl"
VERSION = "4.5"
GITHUB_REPO = "officialdavidtruth-droid/Snapshot-Crawl"

def configure_bundled_browser():
    """Use the Chromium browser shipped beside the Windows application."""
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        browser_dir = app_dir / "browser"
        if browser_dir.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_dir)
DEVICES = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 820, "height": 1180},
    "mobile": {"width": 390, "height": 844},
}
DANGEROUS_WORDS = (
    "delete", "remove", "purchase", "buy now", "pay now", "checkout",
    "submit", "place order", "confirm booking", "book now", "send",
    "transfer", "logout", "log out", "unsubscribe", "cancel account",
    "save changes", "update password", "reset password"
)

class SnapshotCrawlApp:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME} {VERSION}")
        root.geometry("1120x780")
        root.minsize(980, 680)
        root.configure(bg="#F3F5F9")
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.login_continue = threading.Event()
        self.worker = None
        self.colors = {"nav":"#111C32", "orange":"#F28C28", "bg":"#F3F5F9", "card":"#FFFFFF", "text":"#17243A", "muted":"#718096", "line":"#E4E9F1", "green":"#16845B"}
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("TEntry", padding=8, font=("Segoe UI", 10))
        style.configure("TSpinbox", padding=6, font=("Segoe UI", 10))
        style.configure("TCheckbutton", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=self.colors["orange"], foreground="#17243A", padding=(16, 10), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#FFAA4D"), ("disabled", "#D5D9E0")])
        style.configure("Secondary.TButton", background="#E9EEF5", foreground=self.colors["text"], padding=(12, 9), font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.configure("Horizontal.TProgressbar", troughcolor="#E8EDF4", background=self.colors["orange"], thickness=10)

        shell = tk.Frame(root, bg=self.colors["bg"]); shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=self.colors["nav"], width=220); sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=self.colors["nav"]); brand.pack(fill="x", padx=20, pady=(26, 30))
        tk.Label(brand, text="◈", fg=self.colors["orange"], bg=self.colors["nav"], font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(brand, text="SNAPSHOT CRAWL", fg="white", bg=self.colors["nav"], font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(5, 0))
        tk.Label(brand, text=f"DESKTOP  •  V{VERSION}", fg="#9EABC0", bg=self.colors["nav"], font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))
        nav_items = [
            ("Dashboard", "⌂", self.show_dashboard),
            ("Website Explorer", "◎", self.show_explorer),
            ("Business Lead Finder", "▦", self.show_lead_finder),
        ]
        for label, glyph, action in nav_items:
            tk.Button(sidebar, text=f"  {glyph}    {label}", anchor="w",
                      padx=18, pady=13, relief="flat", bd=0,
                      fg="#E7ECF4", bg=self.colors["nav"],
                      activebackground="#263650", activeforeground="white",
                      font=("Segoe UI", 10), cursor="hand2",
                      command=action).pack(fill="x", padx=10, pady=2)
        tk.Frame(sidebar, bg="#2B3850", height=1).pack(fill="x", padx=18, pady=18)
        tk.Button(sidebar, text="⚙   Settings & Updates", anchor="w",
                  padx=18, pady=12, relief="flat", bd=0, fg="#E7ECF4",
                  bg=self.colors["nav"], activebackground="#263650",
                  activeforeground="white", font=("Segoe UI", 9),
                  cursor="hand2", command=self.show_settings).pack(fill="x", padx=10)
        tk.Label(sidebar, text="Public data only.\nRespect website terms and privacy.", justify="left", fg="#9EABC0", bg=self.colors["nav"], font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=20, pady=22)

        content = tk.Frame(shell, bg=self.colors["bg"]); content.pack(side="left", fill="both", expand=True, padx=28, pady=24)
        self.content = content
        top = tk.Frame(content, bg=self.colors["bg"]); top.pack(fill="x", pady=(0, 20))
        tk.Label(top, text="Website Explorer", bg=self.colors["bg"], fg=self.colors["text"], font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(top, text="Capture, inspect and document website experiences across devices.", bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        card = tk.Frame(content, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1); card.pack(fill="x", pady=(0, 14))
        inner = tk.Frame(card, bg=self.colors["card"]); inner.pack(fill="x", padx=20, pady=18)
        tk.Label(inner, text="WEBSITE ADDRESS", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.url_var = tk.StringVar(value="https://example.com")
        ttk.Entry(inner, textvariable=self.url_var, font=("Segoe UI", 11)).pack(fill="x", pady=(7, 14))
        row = tk.Frame(inner, bg=self.colors["card"]); row.pack(fill="x")
        tk.Label(row, text="PAGE LIMIT", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 8, "bold")).pack(side="left")
        self.limit_var = tk.StringVar(value="100")
        ttk.Spinbox(row, from_=1, to=5000, textvariable=self.limit_var, width=8).pack(side="left", padx=(8, 20))
        tk.Label(row, text="SAVE RESULTS TO", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 8, "bold")).pack(side="left")
        self.output_var = tk.StringVar(value=str(Path.home() / "Snapshot Crawl"))
        ttk.Entry(row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Browse", style="Secondary.TButton", command=self.browse).pack(side="left")

        opts = tk.Frame(content, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1); opts.pack(fill="x", pady=(0, 14))
        op = tk.Frame(opts, bg=self.colors["card"]); op.pack(fill="x", padx=20, pady=16)
        tk.Label(op, text="CAPTURE SETTINGS", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", columnspan=3, pady=(0, 10))
        self.desktop_var = tk.BooleanVar(value=True); self.tablet_var = tk.BooleanVar(value=True); self.mobile_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(op, text="Desktop  ·  1440 × 900", variable=self.desktop_var).grid(row=1, column=0, sticky="w", padx=(0, 20), pady=4)
        ttk.Checkbutton(op, text="Tablet  ·  820 × 1180", variable=self.tablet_var).grid(row=1, column=1, sticky="w", padx=(0, 20), pady=4)
        ttk.Checkbutton(op, text="Mobile  ·  390 × 844", variable=self.mobile_var).grid(row=1, column=2, sticky="w", pady=4)
        self.same_domain_var = tk.BooleanVar(value=True); self.login_var = tk.BooleanVar(value=False); self.interactive_var = tk.BooleanVar(value=True); self.scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(op, text="Stay on the same website/domain", variable=self.same_domain_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(op, text="Open browser for manual sign-in", variable=self.login_var).grid(row=2, column=2, sticky="w", pady=4)
        ttk.Checkbutton(op, text="Explore safe tabs, accordions and menu toggles", variable=self.interactive_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(op, text="Scroll pages to load lazy content", variable=self.scroll_var).grid(row=3, column=2, sticky="w", pady=4)

        status_card = tk.Frame(content, bg=self.colors["card"], highlightbackground=self.colors["line"], highlightthickness=1); status_card.pack(fill="both", expand=True)
        sp = tk.Frame(status_card, bg=self.colors["card"]); sp.pack(fill="both", expand=True, padx=20, pady=16)
        sr = tk.Frame(sp, bg=self.colors["card"]); sr.pack(fill="x")
        tk.Label(sr, text="SCAN ACTIVITY", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="Ready to scan")
        ttk.Label(sr, textvariable=self.status_var, style="Muted.TLabel").pack(side="right")
        self.progress = ttk.Progressbar(sp, mode="determinate"); self.progress.pack(fill="x", pady=(12, 10))
        self.log = tk.Text(sp, height=8, wrap="word", state="disabled", font=("Cascadia Code", 9), bg="#F8FAFD", fg="#34435A", relief="flat", padx=12, pady=10)
        self.log.pack(fill="both", expand=True)
        controls = tk.Frame(content, bg=self.colors["bg"]); controls.pack(fill="x", pady=(14, 0))
        ttk.Button(controls, text="Open output folder", style="Secondary.TButton", command=self.open_output_folder).pack(side="left")
        self.start_btn = ttk.Button(controls, text="Start website scan  →", style="Accent.TButton", command=self.start); self.start_btn.pack(side="right")
        self.continue_btn = ttk.Button(controls, text="Continue after sign-in", style="Secondary.TButton", command=self.continue_login, state="disabled"); self.continue_btn.pack(side="right", padx=8)
        self.stop_btn = ttk.Button(controls, text="Stop scan", style="Secondary.TButton", command=self.stop, state="disabled"); self.stop_btn.pack(side="right", padx=8)
        root.after(150, self.poll_events)


    def show_explorer(self):
        self.root.deiconify()
        self.root.lift()
        self.status_var.set("Website Explorer ready")

    def show_lead_finder(self):
        try:
            open_lead_finder(self.root)
        except Exception as exc:
            messagebox.showerror("Business Lead Finder", f"Could not open Business Lead Finder:\\n{exc}")

    def show_dashboard(self):
        """Show a useful overview based on files Snapshot Crawl has actually created."""
        win = tk.Toplevel(self.root)
        win.title("Snapshot Crawl — Dashboard")
        win.geometry("900x650")
        win.minsize(760, 560)
        win.configure(bg=self.colors["bg"])

        tk.Label(win, text="Dashboard", bg=self.colors["bg"], fg=self.colors["text"],
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=28, pady=(24, 3))
        tk.Label(win, text="An overview of your website captures and saved business leads.",
                 bg=self.colors["bg"], fg=self.colors["muted"],
                 font=("Segoe UI", 10)).pack(anchor="w", padx=28, pady=(0, 18))

        output = Path(self.output_var.get()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        crawl_dirs = sorted([p for p in output.glob("Snapshot_Crawl_*") if p.is_dir()],
                            key=lambda p: p.stat().st_mtime, reverse=True)
        screenshot_count = 0
        for folder in crawl_dirs:
            for device in ("desktop", "tablet", "mobile"):
                device_dir = folder / device
                if device_dir.exists():
                    screenshot_count += sum(1 for f in device_dir.rglob("*") if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        lead_files = list(output.glob("*.csv"))
        lead_rows = 0
        for csv_file in lead_files:
            try:
                with csv_file.open("r", encoding="utf-8-sig", newline="") as f:
                    lead_rows += max(0, sum(1 for _ in f) - 1)
            except Exception:
                continue

        metrics = tk.Frame(win, bg=self.colors["bg"])
        metrics.pack(fill="x", padx=22)
        for title, value, detail in [
            ("WEBSITE CRAWLS", str(len(crawl_dirs)), "Saved crawl sessions"),
            ("SCREENSHOTS", str(screenshot_count), "Captured image files"),
            ("SAVED LEADS", str(lead_rows), "Rows in exported CSV files"),
        ]:
            card = tk.Frame(metrics, bg="white", highlightbackground=self.colors["line"], highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=6)
            tk.Label(card, text=title, bg="white", fg=self.colors["muted"],
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(13, 4))
            tk.Label(card, text=value, bg="white", fg=self.colors["text"],
                     font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=14)
            tk.Label(card, text=detail, bg="white", fg=self.colors["muted"],
                     font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 13))

        section = tk.Frame(win, bg="white", highlightbackground=self.colors["line"], highlightthickness=1)
        section.pack(fill="both", expand=True, padx=28, pady=18)
        tk.Label(section, text="RECENT WEBSITE ACTIVITY", bg="white", fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(15, 8))
        if crawl_dirs:
            for folder in crawl_dirs[:6]:
                stamp = datetime.fromtimestamp(folder.stat().st_mtime).strftime("%b %d, %Y  %I:%M %p")
                tk.Label(section, text=f"  •  {folder.name}     {stamp}", bg="white",
                         fg=self.colors["text"], font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=5)
        else:
            tk.Label(section, text="No website crawls have been saved yet. Start a scan in Website Explorer.",
                     bg="white", fg=self.colors["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=8)

        actions = tk.Frame(win, bg=self.colors["bg"])
        actions.pack(fill="x", padx=28, pady=(0, 20))
        tk.Button(actions, text="Open Website Explorer", command=lambda: (win.destroy(), self.show_explorer()),
                  bg=self.colors["orange"], fg=self.colors["text"], relief="flat",
                  padx=16, pady=10, cursor="hand2").pack(side="left")
        tk.Button(actions, text="Find Businesses", command=lambda: (win.destroy(), self.show_lead_finder()),
                  bg="#E9EEF5", fg=self.colors["text"], relief="flat",
                  padx=16, pady=10, cursor="hand2").pack(side="left", padx=10)
        tk.Button(actions, text="Open Results Folder", command=self.open_output_folder,
                  bg="#E9EEF5", fg=self.colors["text"], relief="flat",
                  padx=16, pady=10, cursor="hand2").pack(side="right")

    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings & Updates")
        win.geometry("500x260")
        win.resizable(False, False)
        win.configure(bg=self.colors["bg"])
        tk.Label(win, text="Settings & Updates", bg=self.colors["bg"],
                 fg=self.colors["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(24, 8))
        tk.Label(win, text=f"Snapshot Crawl version {VERSION}", bg=self.colors["bg"],
                 fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w", padx=24)
        tk.Label(win, text="Check the official GitHub Releases page for a newer version.",
                 bg=self.colors["bg"], fg=self.colors["text"], font=("Segoe UI", 10),
                 wraplength=440, justify="left").pack(anchor="w", padx=24, pady=20)
        tk.Button(win, text="Check for updates", command=self.check_updates,
                  bg=self.colors["orange"], fg=self.colors["text"], relief="flat",
                  padx=18, pady=9, cursor="hand2").pack(anchor="w", padx=24)
        tk.Button(win, text="Close", command=win.destroy, relief="flat",
                  padx=18, pady=7).pack(anchor="w", padx=24, pady=12)

    def open_output_folder(self):
        folder = Path(self.output_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            messagebox.showinfo("Output folder", str(folder))

    def check_updates(self):
        from updater import check_for_updates
        check_for_updates(self.root, VERSION, GITHUB_REPO)

    def browse(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def log_line(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        url = self.url_var.get().strip()
        if "://" not in url:
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            messagebox.showerror("Invalid website address", "Enter a valid website address, for example https://example.com")
            return
        try:
            limit = int(self.limit_var.get())
            if limit < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid page limit", "Enter a positive whole number.")
            return
        devices = {k: v for k, v in DEVICES.items() if
                   (k == "desktop" and self.desktop_var.get()) or
                   (k == "tablet" and self.tablet_var.get()) or
                   (k == "mobile" and self.mobile_var.get())}
        if not devices:
            messagebox.showerror("Choose a device", "Select at least one device size.")
            return

        self.stop_event.clear()
        self.login_continue.clear()
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")
        self.progress["value"] = 0
        self.status_var.set("Starting browser…")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.continue_btn.configure(state="disabled")
        args = (parsed.geturl(), limit, Path(self.output_var.get()), devices,
                self.same_domain_var.get(), self.login_var.get(),
                self.interactive_var.get(), self.scroll_var.get())
        self.worker = threading.Thread(target=self.thread_main, args=args, daemon=True)
        self.worker.start()

    def thread_main(self, *args):
        try:
            asyncio.run(self.run_scan(*args))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.events.put(("finished", None))

    async def run_scan(self, start_url, page_limit, output, devices, same_domain,
                       manual_login, explore_ui, scroll_pages):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = output / f"Snapshot_Crawl_{stamp}"
        for device in devices:
            (job_dir / device).mkdir(parents=True, exist_ok=True)
        (job_dir / "reports").mkdir(exist_ok=True)

        start_host = urlparse(start_url).netloc.lower()
        allowed_hosts = {start_host}
        if start_host.startswith("www."):
            allowed_hosts.add(start_host[4:])
        else:
            allowed_hosts.add("www." + start_host)

        queue_urls = [start_url]
        visited = set()
        manifest = []
        page_total = 0
        state_total = 0

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=not manual_login)
            context = await browser.new_context()
            page = await context.new_page()

            if manual_login:
                self.events.put(("status", "Opening browser for your sign-in…"))
                try:
                    await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
                except Exception as exc:
                    self.events.put(("log", f"Initial redirect/navigation: {exc}"))
                self.events.put(("login_ready", "Browser opened. Sign in yourself, then click Continue after sign-in."))
                while not self.login_continue.wait(0.2):
                    if self.stop_event.is_set():
                        break
                self.login_continue.clear()
                current = page.url
                if current.startswith(("http://", "https://")):
                    queue_urls.insert(0, current)

            while queue_urls and page_total < page_limit and not self.stop_event.is_set():
                requested_url, _ = urldefrag(queue_urls.pop(0))
                host = urlparse(requested_url).netloc.lower()
                if urlparse(requested_url).scheme not in ("http", "https"):
                    continue
                if same_domain and host not in allowed_hosts:
                    continue
                if requested_url in visited:
                    continue
                visited.add(requested_url)

                try:
                    if page.url != requested_url:
                        try:
                            await page.goto(requested_url, wait_until="domcontentloaded", timeout=60000)
                        except Exception as nav_exc:
                            self.events.put(("log", f"Redirect/navigation while opening {requested_url}: {nav_exc}"))
                            try:
                                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                    try:
                        await page.wait_for_load_state("networkidle", timeout=7000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(500)

                    actual_url, _ = urldefrag(page.url)
                    if not actual_url.startswith(("http://", "https://")):
                        actual_url = requested_url
                    title = await page.title()
                    if scroll_pages:
                        await self.scroll_to_load(page)

                    links = await page.locator("a[href]").evaluate_all("(els) => els.map(a => a.href).filter(Boolean)")
                    page_total += 1
                    base_name = f"{page_total:04d}_{self.slug(actual_url)}"
                    await self.capture_all_devices(page, devices, job_dir, base_name)
                    manifest.append({"type": "page", "title": title, "url": actual_url, "capture": base_name})
                    self.events.put(("log", f"Page {page_total}: {title or actual_url}"))
                    self.events.put(("progress", (page_total, page_limit)))

                    if explore_ui and not self.stop_event.is_set():
                        states = await self.explore_safe_controls(page, actual_url)
                        for state_index, state in enumerate(states, start=1):
                            if self.stop_event.is_set():
                                break
                            state_total += 1
                            state_name = f"{base_name}_state_{state_index:02d}_{self.slug(state['label'])}"
                            await self.capture_all_devices(page, devices, job_dir, state_name)
                            manifest.append({"type": "interactive_state", "title": state["label"],
                                             "url": actual_url, "capture": state_name})
                            self.events.put(("log", f"  UI state: {state['label']}"))
                            await self.restore_page(page, actual_url)

                    for href in links:
                        href, _ = urldefrag(href)
                        h = urlparse(href)
                        hhost = h.netloc.lower()
                        if h.scheme in ("http", "https") and (not same_domain or hhost in allowed_hosts):
                            if href not in visited and href not in queue_urls:
                                queue_urls.append(href)

                except Exception as exc:
                    self.events.put(("log", f"Skipped {requested_url}: {exc}"))

            await browser.close()

        report_path = job_dir / "reports" / "capture_manifest.csv"
        with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["type", "title", "url", "capture"])
            writer.writeheader()
            writer.writerows(manifest)
        summary = {
            "application": APP_NAME, "version": VERSION, "started_url": start_url,
            "pages_captured": page_total, "interactive_states_captured": state_total,
            "device_profiles": list(devices.keys()), "captures": len(manifest),
            "finished_at": datetime.now().isoformat(timespec="seconds")
        }
        (job_dir / "reports" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self.events.put(("status", f"Finished: {page_total} pages and {state_total} interface states captured."))
        self.events.put(("log", f"Results folder: {job_dir}"))
        self.events.put(("log", "A CSV capture manifest and JSON summary are in the reports folder."))

    async def capture_all_devices(self, page, devices, job_dir, basename):
        for device, viewport in devices.items():
            await page.set_viewport_size(viewport)
            await page.wait_for_timeout(250)
            path = job_dir / device / f"{basename}.png"
            await page.screenshot(path=str(path), full_page=True, animations="disabled", timeout=60000)

    async def scroll_to_load(self, page):
        await page.evaluate("""async () => {
            const step = Math.max(400, Math.floor(window.innerHeight * 0.7));
            let previous = 0;
            for (let i = 0; i < 30; i++) {
                const height = document.body.scrollHeight;
                for (let y = 0; y < height; y += step) {
                    window.scrollTo(0, y);
                    await new Promise(resolve => setTimeout(resolve, 120));
                }
                if (height === previous) break;
                previous = height;
            }
            window.scrollTo(0, 0);
        }""")
        await page.wait_for_timeout(300)

    async def explore_safe_controls(self, page, page_url):
        # Only inspect low-risk UI patterns. Never submit forms or click ordinary action buttons.
        selector = ' [role="tab"], button[aria-expanded="false"], [role="button"][aria-expanded="false], summary '
        loc = page.locator(selector)
        try:
            count = min(await loc.count(), 12)
        except Exception:
            return []
        found = []
        for index in range(count):
            if self.stop_event.is_set():
                break
            item = loc.nth(index)
            try:
                if not await item.is_visible():
                    continue
                label = (await item.inner_text(timeout=1000)).strip().replace("\n", " ")[:70]
                aria = (await item.get_attribute("aria-label")) or ""
                label = label or aria or f"control_{index+1}"
                low = label.lower()
                if any(word in low for word in DANGEROUS_WORDS):
                    continue
                # Skip anything that is or belongs to a form submission control.
                typ = (await item.get_attribute("type") or "").lower()
                if typ == "submit":
                    continue
                await item.click(timeout=1800)
                await page.wait_for_timeout(350)
                found.append({"label": label})
                if len(found) >= 5:
                    break
            except Exception:
                continue
        return found

    async def restore_page(self, page, url):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def slug(value):
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:55] or "page"

    def continue_login(self):
        self.login_continue.set()
        self.continue_btn.configure(state="disabled")
        self.status_var.set("Continuing from the signed-in browser session…")

    def stop(self):
        self.stop_event.set()
        self.login_continue.set()
        self.status_var.set("Stopping after the current operation…")

    def poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log_line(value)
                elif kind == "status":
                    self.status_var.set(value)
                elif kind == "progress":
                    current, maximum = value
                    self.progress["maximum"] = maximum
                    self.progress["value"] = current
                elif kind == "login_ready":
                    self.status_var.set(value)
                    self.log_line(value)
                    self.continue_btn.configure(state="normal")
                elif kind == "error":
                    self.log_line("ERROR: " + value)
                    messagebox.showerror("Snapshot Crawl error", value)
                elif kind == "finished":
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.continue_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self.poll_events)


if __name__ == "__main__":
    configure_bundled_browser()
    root = tk.Tk()
    SnapshotCrawlApp(root)
    root.mainloop()

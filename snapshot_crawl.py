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

APP_NAME = "Snapshot Crawl"
VERSION = "3.0.0"

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
        root.geometry("900x720")
        root.minsize(760, 620)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.login_continue = threading.Event()
        self.worker = None

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        main = ttk.Frame(root, padding=20)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="SNAPSHOT CRAWL", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(header, text=f"Website capture & exploration  |  Version {VERSION}",
                  foreground="#666").pack(anchor="w", pady=(2, 16))

        ttk.Label(main, text="Website address").pack(anchor="w")
        self.url_var = tk.StringVar(value="https://example.com")
        ttk.Entry(main, textvariable=self.url_var, font=("Segoe UI", 11)).pack(fill="x", pady=(5, 13))

        line = ttk.Frame(main); line.pack(fill="x")
        ttk.Label(line, text="Page limit").pack(side="left")
        self.limit_var = tk.StringVar(value="100")
        ttk.Spinbox(line, from_=1, to=5000, textvariable=self.limit_var, width=8).pack(side="left", padx=(7, 18))
        ttk.Label(line, text="Save results to").pack(side="left")
        self.output_var = tk.StringVar(value=str(Path.home() / "Snapshot Crawl"))
        ttk.Entry(line, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=7)
        ttk.Button(line, text="Browse", command=self.browse).pack(side="left")

        options = ttk.LabelFrame(main, text="Capture settings", padding=12)
        options.pack(fill="x", pady=14)
        self.desktop_var = tk.BooleanVar(value=True)
        self.tablet_var = tk.BooleanVar(value=True)
        self.mobile_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Desktop · 1440 × 900", variable=self.desktop_var).grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(options, text="Tablet · 820 × 1180", variable=self.tablet_var).grid(row=0, column=1, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(options, text="Mobile · 390 × 844", variable=self.mobile_var).grid(row=0, column=2, sticky="w", padx=5, pady=3)
        self.same_domain_var = tk.BooleanVar(value=True)
        self.login_var = tk.BooleanVar(value=False)
        self.interactive_var = tk.BooleanVar(value=True)
        self.scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Stay on the same website/domain", variable=self.same_domain_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(options, text="Open a browser so I can sign in manually", variable=self.login_var).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(options, text="Explore safe tabs, accordions and menu toggles", variable=self.interactive_var).grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(options, text="Scroll pages to trigger lazy-loaded content", variable=self.scroll_var).grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=3)

        ttk.Label(main, text="Progress").pack(anchor="w")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(3, 5))
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.pack(fill="x")

        self.log = tk.Text(main, height=14, wrap="word", state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, pady=12)

        controls = ttk.Frame(main); controls.pack(fill="x")
        self.start_btn = ttk.Button(controls, text="Start website scan", command=self.start)
        self.start_btn.pack(side="left")
        self.continue_btn = ttk.Button(controls, text="Continue after sign-in", command=self.continue_login, state="disabled")
        self.continue_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(controls, text="Stop scan", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left")
        ttk.Label(main, text="Safety: Snapshot Crawl does not bypass logins or security controls. It avoids obvious destructive and payment actions. Use only on websites you own or have permission to test.",
                  foreground="#555", wraplength=850).pack(anchor="w", pady=(12, 0))
        root.after(150, self.poll_events)

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

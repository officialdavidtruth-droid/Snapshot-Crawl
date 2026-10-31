"""Checks official GitHub Releases and downloads the signed-by-hash installer asset."""
import hashlib, os, subprocess, tempfile, threading, tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
import requests

API_TIMEOUT = 20

def _latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Snapshot-Crawl-Updater"}, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()

def _version_tuple(value):
    return tuple(int(x) for x in value.lstrip("vV").split(".")[:3])

def check_for_updates(root, current_version, repo):
    win = tk.Toplevel(root); win.title("Snapshot Crawl Updates"); win.geometry("440x190"); win.resizable(False, False); win.transient(root); win.grab_set()
    tk.Label(win, text="Checking for updates…", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.StringVar(value="Connecting to the official release page.")
    tk.Label(win, textvariable=status, wraplength=390, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=22)
    progress = ttk.Progressbar(win, mode="indeterminate"); progress.pack(fill="x", padx=22, pady=18); progress.start(10)
    def worker():
        try:
            release = _latest_release(repo)
            tag = release.get("tag_name", "")
            if not tag or _version_tuple(tag) <= _version_tuple(current_version):
                root.after(0, lambda: finish("You're using the latest version.", None))
                return
            assets = release.get("assets", [])
            installer = next((a for a in assets if a.get("name", "").lower().endswith("setup.exe")), None)
            if not installer:
                raise RuntimeError("A newer release exists, but its Windows installer has not been published yet.")
            root.after(0, lambda: offer_update(tag, installer))
        except Exception as exc:
            root.after(0, lambda e=str(exc): finish("Could not check for updates: " + e, None))
    def finish(message, _):
        if win.winfo_exists():
            progress.stop(); status.set(message)
            tk.Button(win, text="Close", command=win.destroy, padx=18).pack(pady=8)
    def offer_update(tag, asset):
        if not win.winfo_exists(): return
        progress.stop(); status.set(f"Version {tag} is available. Current version: {current_version}.")
        def download_install():
            btn.configure(state="disabled", text="Downloading…")
            status.set("Downloading the official installer. Please keep this window open.")
            def dl():
                try:
                    r=requests.get(asset["browser_download_url"], stream=True, timeout=60, headers={"User-Agent":"Snapshot-Crawl-Updater"}); r.raise_for_status()
                    fd,path=tempfile.mkstemp(prefix="Snapshot-Crawl-Update-",suffix="-Setup.exe"); os.close(fd)
                    h=hashlib.sha256()
                    with open(path,"wb") as f:
                        for chunk in r.iter_content(1024*256):
                            if chunk: f.write(chunk); h.update(chunk)
                    expected=asset.get("digest")
                    if expected and expected.startswith("sha256:") and h.hexdigest().lower()!=expected.split(":",1)[1].lower():
                        os.remove(path); raise RuntimeError("Installer verification failed. The downloaded file was not launched.")
                    root.after(0, lambda: launch(path))
                except Exception as exc:
                    root.after(0, lambda e=str(exc): finish("Update failed: "+e,None))
            threading.Thread(target=dl,daemon=True).start()
        def launch(path):
            if not win.winfo_exists(): return
            status.set("Installer downloaded. Snapshot Crawl will close so the update can be installed.")
            try:
                subprocess.Popen([path], close_fds=True)
                win.destroy(); root.after(300, root.destroy)
            except Exception as exc: finish("Could not launch installer: "+str(exc),None)
        btn=tk.Button(win,text="Download and install",command=download_install,padx=16,pady=7); btn.pack(side="left",padx=(22,8),pady=8)
        tk.Button(win,text="Later",command=win.destroy,padx=16,pady=7).pack(side="left",pady=8)
    threading.Thread(target=worker,daemon=True).start()

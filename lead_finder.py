
import csv, re, threading, time, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

UA = "SnapshotCrawl/4.0 (public business contact discovery)"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s().-]?)?(?:\(?\d{2,5}\)?[\s().-]?){2,5}\d{2,5}(?!\w)")
GENERIC = {"info","hello","contact","sales","support","admin","office","enquiries","inquiries",
           "reservations","booking","bookings","reception","customerservice","service","marketing"}

class LeadFinder(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Snapshot Crawl — Business Lead Finder")
        self.geometry("900x670"); self.minsize(760,560)
        self.events=[]; self.lock=threading.Lock(); self.stop_flag=threading.Event(); self.rows=[]
        box=ttk.Frame(self,padding=18); box.pack(fill="both",expand=True)
        ttk.Label(box,text="BUSINESS LEAD FINDER",font=("Segoe UI",18,"bold")).pack(anchor="w")
        ttk.Label(box,text="Find local businesses and retain only entries with publicly listed contact details.",
                  foreground="#666").pack(anchor="w",pady=(4,14))
        form=ttk.Frame(box);form.pack(fill="x")
        ttk.Label(form,text="Business niche").grid(row=0,column=0,sticky="w")
        self.niche=tk.StringVar(value="hair salon")
        ttk.Entry(form,textvariable=self.niche,width=28).grid(row=1,column=0,sticky="ew",padx=(0,10))
        ttk.Label(form,text="City / area").grid(row=0,column=1,sticky="w")
        self.location=tk.StringVar(value="Abuja, Nigeria")
        ttk.Entry(form,textvariable=self.location,width=28).grid(row=1,column=1,sticky="ew",padx=(0,10))
        ttk.Label(form,text="Candidate limit").grid(row=0,column=2,sticky="w")
        self.limit=tk.StringVar(value="100")
        ttk.Spinbox(form,from_=10,to=500,textvariable=self.limit,width=9).grid(row=1,column=2,sticky="w")
        form.columnconfigure(0,weight=1);form.columnconfigure(1,weight=1)
        self.scrape=tk.BooleanVar(value=True)
        ttk.Checkbutton(box,text="Check official public websites for additional business contact details",
                        variable=self.scrape).pack(anchor="w",pady=(12,3))
        ttk.Label(box,text="No popularity ranking: local and small businesses are eligible. Businesses without a public phone number or email are excluded.",
                  wraplength=830).pack(anchor="w",pady=(4,10))
        row=ttk.Frame(box);row.pack(fill="x")
        self.go=ttk.Button(row,text="Find businesses",command=self.start);self.go.pack(side="left")
        ttk.Button(row,text="Stop",command=self.stop).pack(side="left",padx=8)
        self.export_btn=ttk.Button(row,text="Export CSV",command=self.export,state="disabled");self.export_btn.pack(side="left")
        self.status=tk.StringVar(value="Ready");ttk.Label(box,textvariable=self.status).pack(anchor="w",pady=(10,4))
        self.bar=ttk.Progressbar(box,mode="indeterminate");self.bar.pack(fill="x")
        cols=("name","category","phone","email","website","source")
        self.tree=ttk.Treeview(box,columns=cols,show="headings",height=16)
        for c,w in zip(cols,(170,100,125,170,145,130)):
            self.tree.heading(c,text=c.title());self.tree.column(c,width=w,minwidth=65)
        self.tree.pack(fill="both",expand=True,pady=10)
        ttk.Label(box,text="Uses OpenStreetMap community listings and public business websites. No private-account scraping or login bypass.",
                  foreground="#666",wraplength=830).pack(anchor="w")

    def start(self):
        try:
            n=int(self.limit.get())
            if not self.niche.get().strip() or not self.location.get().strip() or n<1: raise ValueError
        except ValueError:
            messagebox.showerror("Required","Enter a niche, location and valid candidate limit.");return
        self.stop_flag.clear();self.rows=[]
        for x in self.tree.get_children():self.tree.delete(x)
        self.go.configure(state="disabled");self.export_btn.configure(state="disabled")
        self.bar.start(12);self.status.set("Searching local business listings…")
        threading.Thread(target=self.worker,args=(self.niche.get().strip(),self.location.get().strip(),n,self.scrape.get()),daemon=True).start()
        self.after(200,self.poll)

    def stop(self): self.stop_flag.set();self.status.set("Stopping…")
    def post(self,item):
        with self.lock:self.events.append(item)

    def get(self,url,**kwargs):
        headers={"User-Agent":UA};headers.update(kwargs.pop("headers",{}))
        return requests.get(url,headers=headers,timeout=35,**kwargs)

    def geocode(self,place):
        r=self.get("https://nominatim.openstreetmap.org/search",params={"q":place,"format":"jsonv2","limit":1})
        r.raise_for_status();data=r.json()
        if not data:raise RuntimeError("Location not found. Try a city or district name.")
        return float(data[0]["lat"]),float(data[0]["lon"]),data[0].get("display_name",place)

    def find_osm(self,lat,lon):
        q = ("[out:json][timeout:45];("
             f"node(around:12000,{lat},{lon})[name][shop];"
             f"way(around:12000,{lat},{lon})[name][shop];"
             f"node(around:12000,{lat},{lon})[name][amenity];"
             f"way(around:12000,{lat},{lon})[name][amenity];"
             f"node(around:12000,{lat},{lon})[name][office];"
             f"way(around:12000,{lat},{lon})[name][office];"
             f"node(around:12000,{lat},{lon})[name][craft];"
             f"way(around:12000,{lat},{lon})[name][craft];);out center tags;")
        error=None
        for endpoint in OVERPASS:
            if self.stop_flag.is_set():return []
            try:
                r=requests.post(endpoint,data={"data":q},headers={"User-Agent":UA},timeout=65)
                r.raise_for_status();return r.json().get("elements",[])
            except Exception as e:error=e;time.sleep(1)
        raise RuntimeError(f"OpenStreetMap search service unavailable: {error}")

    def scrape_site(self,website):
        p=urlparse(website if "://" in website else "https://"+website)
        if p.scheme not in ("http","https") or not p.netloc:return "",""
        base=p.geturl();urls=[base,urljoin(base,"/contact"),urljoin(base,"/contact-us"),urljoin(base,"/about")]
        phones=set();emails=set()
        for url in urls:
            if self.stop_flag.is_set():break
            try:
                r=self.get(url)
                if r.status_code>=400:continue
                soup=BeautifulSoup(r.text[:1800000],"html.parser")
                text=soup.get_text(" ",strip=True)
                for e in EMAIL_RE.findall(r.text+" "+text):
                    e=e.strip(";,").lower();local=e.split("@")[0]
                    if any(local==g or local.startswith(g+".") or local.startswith(g+"-") for g in GENERIC):
                        emails.add(e)
                for a in soup.select('a[href^="tel:"]'):
                    n=a.get("href","")[4:]
                    if len(re.sub(r"\D","",n))>=7:phones.add(n.strip())
                for n in PHONE_RE.findall(text):
                    if 8<=len(re.sub(r"\D","",n))<=15:phones.add(re.sub(r"\s+"," ",n).strip())
                time.sleep(.7)
            except Exception:continue
        return "; ".join(sorted(phones)), "; ".join(sorted(emails))

    def worker(self,niche,place,limit,visit_sites):
        try:
            lat,lon,display=self.geocode(place)
            self.post(("status",f"Searching around {display}…"))
            elements=self.find_osm(lat,lon)
            terms=[x.lower() for x in re.findall(r"[a-z0-9]+",niche.lower()) if len(x)>2]
            synonyms={"salon":["hairdresser","beauty"],"barber":["hairdresser"],"hotel":["hotel","guest_house"],
                      "restaurant":["restaurant","fast_food","cafe"],"boutique":["clothes"]}
            expanded=terms+[v for t in terms for v in synonyms.get(t,[])]
            candidates=[]
            for el in elements:
                tags=el.get("tags",{});name=tags.get("name","").strip()
                if not name:continue
                hay=" ".join([name]+[str(tags.get(k,"")) for k in ("shop","amenity","office","craft","description")]).lower()
                if expanded and not any(t in hay for t in expanded):continue
                website=tags.get("website") or tags.get("contact:website") or ""
                candidates.append({"name":name,"category":next((f"{k}: {tags[k]}" for k in ("shop","amenity","office","craft") if tags.get(k)),"business"),
                    "phone":tags.get("phone") or tags.get("contact:phone") or tags.get("mobile") or "",
                    "email":tags.get("email") or tags.get("contact:email") or "",
                    "website":website,"address":", ".join(tags.get(k,"") for k in ("addr:street","addr:suburb","addr:city") if tags.get(k)),
                    "source":f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}"})
            candidates=candidates[:limit];accepted=[]
            self.post(("status",f"Checking public contact details for {len(candidates)} candidates…"))
            for i,row in enumerate(candidates,1):
                if self.stop_flag.is_set():break
                phone=row["phone"];email=row["email"]
                if visit_sites and row["website"] and (not phone or not email):
                    p2,e2=self.scrape_site(row["website"])
                    phone="; ".join(x for x in (phone,p2) if x)
                    email="; ".join(x for x in (email,e2) if x)
                if phone or email:
                    row["phone"],row["email"]=phone,email
                    accepted.append(row);self.post(("row",row))
                self.post(("status",f"Checked {i}/{len(candidates)} · {len(accepted)} with contact details"))
            self.post(("done",len(accepted)))
        except Exception as e:self.post(("error",str(e)))

    def poll(self):
        with self.lock:items=self.events[:];self.events.clear()
        for kind,value in items:
            if kind=="row":
                self.rows.append(value);self.tree.insert("","end",values=tuple(value[k] for k in ("name","category","phone","email","website","source")))
            elif kind=="status":self.status.set(value)
            elif kind=="error":
                self.status.set("Search failed.");messagebox.showerror("Lead Finder",value)
            elif kind=="done":
                self.status.set(f"Finished: {value} businesses with public contact details.")
                self.go.configure(state="normal");self.export_btn.configure(state="normal" if value else "disabled");self.bar.stop()
        if self.go["state"]=="disabled":self.after(200,self.poll)

    def export(self):
        if not self.rows:return
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],initialfile="snapshot_crawl_leads.csv")
        if not path:return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["name","category","phone","email","website","address","source"])
            w.writeheader();w.writerows(self.rows)
        messagebox.showinfo("Exported",f"Saved {len(self.rows)} qualified business leads.")

def open_lead_finder(master): LeadFinder(master)

#!/usr/bin/env python3
"""
PhD Vacancy Crawler - Multi-omics Priority Edition
Direct crawling, no Google API required.

Focus areas:
- multi-omics data analysis
- bioinformatics
- computational biology
- genomics
- transcriptomics
- single-cell
- spatial transcriptomics
- RNA-seq / scRNA-seq
- ATAC-seq / ChIP-seq
- cancer genomics
- population genomics
- human genetics
- statistical genetics
- immunogenomics
- machine learning / AI for omics
- precision medicine
- metagenomics / microbiome
- proteomics / metabolomics
- low-pass sequencing / imputation / PRS

Usage:
  python phd_vacancy_crawler.py --daily
  python phd_vacancy_crawler.py --report
  python phd_vacancy_crawler.py --list-open
  python phd_vacancy_crawler.py --region europe
"""

import os
import re
import json
import time
import argparse
import logging
import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urljoin, urldefrag

import requests
import pandas as pd
from bs4 import BeautifulSoup

try:
    import yaml
except Exception:
    yaml = None

# ========================= DEFAULT PATHS =========================

DB_FILE = "vacancies.sqlite"
SEEDS_FILE = "seeds.json"
KEYWORDS_FILE = "keywords.yaml"
OUTPUT_PREFIX = "vacancies"
REPORT_HTML = "daily_report.html"
REPORT_MD = "daily_report.md"
LOG_FILE = "crawler.log"
BACKUP_DIR = "backups"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================= FALLBACK KEYWORDS =========================

DEFAULT_KEYWORDS = {
    "position_keywords": [
        "phd", "doctoral", "doctoral researcher", "doctoral candidate", "studentship",
        "early stage researcher", "esr", "graduate researcher", "jrf", "research assistant"
    ],
    "priority_areas": [
        "multi-omics data analysis", "multi-omics", "integrative omics",
        "bioinformatics", "computational biology", "genomics", "functional genomics",
        "cancer genomics", "population genomics", "human genetics", "statistical genetics",
        "immunogenomics", "single-cell", "single cell", "spatial transcriptomics",
        "rna-seq", "rnaseq", "scrna-seq", "scRNA-seq", "atac-seq", "chip-seq",
        "epigenomics", "metagenomics", "microbiome", "proteomics", "metabolomics",
        "machine learning", "deep learning", "artificial intelligence",
        "precision medicine", "low-pass sequencing", "genotype imputation",
        "polygenic risk score"
    ],
    "negative_keywords": [
        "postdoc", "post-doctoral", "postdoctoral", "professor", "lecturer",
        "internship", "seminar", "conference", "workshop", "news", "press release",
        "expired", "closed", "no longer accepting"
    ],
    "follow_terms": [
        "phd", "doctoral", "studentship", "career", "careers", "job", "jobs",
        "vacancy", "vacancies", "position", "fellowship", "recruitment",
        "opportunity", "graduate", "researcher", "apply"
    ]
}

# ========================= UTILITIES =========================

def normalize(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()

def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def domain_from_url(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "Unknown"

def canonical_url(url):
    try:
        url, _ = urldefrag(url)
        p = urlparse(url)
        path = re.sub(r"/+$", "", p.path)
        query = p.query
        return p._replace(fragment="", path=path, query=query).geturl()
    except Exception:
        return url

def text_hash(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    return default

def load_keywords():
    if yaml and os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                merged = dict(DEFAULT_KEYWORDS)
                merged.update(data)
                return merged
        except Exception as e:
            logger.warning(f"Failed to load keywords.yaml: {e}")
    return DEFAULT_KEYWORDS.copy()

def load_seeds():
    data = load_json(SEEDS_FILE, {})
    if isinstance(data, dict):
        seeds = []
        for k in ["high_priority", "europe", "usa", "canada", "australia", "asia", "india", "other", "social_and_aggregators"]:
            seeds.extend(data.get(k, []))
        return sorted(set(seeds))
    if isinstance(data, list):
        return sorted(set(data))
    return []

# ========================= EXTRACTION =========================

def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    bad = ("example.com", "domain.com", "your.email", "university.edu")
    good = sorted(set(e for e in emails if not any(b in e.lower() for b in bad)))
    return "; ".join(good) if good else "Not found"

def extract_deadline(text):
    if not text:
        return "Not found"
    patterns = [
        r"(?:application deadline|deadline for applications|closing date|closing deadline|apply by|last date to apply|deadline|closes)\s*[:\-]?\s*([A-Za-z]{3,12}\s+\d{1,2},?\s+\d{4})",
        r"(?:application deadline|deadline for applications|closing date|closing deadline|apply by|last date to apply|deadline|closes)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]{3,12}\s+\d{4})",
        r"(?:application deadline|deadline for applications|closing date|closing deadline|apply by|last date to apply|deadline|closes)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        r"(?:application deadline|deadline for applications|closing date|closing deadline|apply by|last date to apply|deadline|closes)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return clean_text(m.group(1))
    return "Not found"

def parse_deadline_to_date(deadline_str):
    if not deadline_str or deadline_str == "Not found":
        return None
    fmts = [
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%Y", "%d/%m/%y", "%m/%d/%y"
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(deadline_str, fmt)
        except ValueError:
            pass
    return None

def deadline_status(deadline_str):
    dt = parse_deadline_to_date(deadline_str)
    if not dt:
        return "unknown", None
    days = (dt - datetime.now()).days
    if days < 0:
        return "expired", days
    if days <= 3:
        return "closing_soon", days
    if days <= 7:
        return "urgent", days
    return "open", days

def extract_posted_date(text):
    if not text:
        return None
    patterns = [
        r"(?:posted|published|advertised|opening date|date posted)\s*[:\-]?\s*([A-Za-z]{3,12}\s+\d{1,2},?\s+\d{4})",
        r"(?:posted|published|advertised|opening date|date posted)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return clean_text(m.group(1))
    return None

def extract_country(text, url):
    t = normalize((text or "") + " " + (url or ""))
    rules = {
        "United States": [".edu", "nih.gov", "genome.gov", "broadinstitute.org", "stanford.edu", "harvard.edu"],
        "United Kingdom": [".ac.uk", "jobs.ac.uk", "findaphd.com", "sanger.ac.uk", "crick.ac.uk", "wellcome.org"],
        "Germany": [".de", "daad.de", "helmholtz", "dkfz", "max planck"],
        "Netherlands": [".nl", "academictransfer.com", "wur.nl", "tudelft.nl", "uu.nl"],
        "France": [".fr", "cnrs", "inserm", "pasteur"],
        "Switzerland": [".ch", "ethz.ch", "epfl.ch", "uzh.ch"],
        "Sweden": [".se", "ki.se", "kth.se", "lu.se"],
        "Denmark": [".dk", "ku.dk", "au.dk", "dtu.dk"],
        "Finland": [".fi", "helsinki.fi", "aalto.fi"],
        "Norway": [".no", "uio.no", "ntnu.no"],
        "Canada": [".ca", "usask.ca", "utoronto.ca", "mcgill.ca"],
        "Australia": [".edu.au", "unimelb.edu.au", "monash.edu", "sydney.edu.au"],
        "Singapore": ["nus.edu.sg", "ntu.edu.sg", "astar.edu.sg"],
        "Japan": [".ac.jp", "riken.jp", "u-tokyo.ac.jp", "kyoto-u.ac.jp"],
        "India": [".ac.in", ".in", "iisc.ac.in", "ncbs.res.in", "tifr.res.in"],
    }
    for country, terms in rules.items():
        if any(term in t for term in terms):
            return country
    return "Unknown"

def extract_institution(title, snippet, page_text=""):
    combined = f"{title} {snippet} {page_text}"
    patterns = [
        r"([A-Z][A-Za-z\s&,-]+(?:University|Institute|College|School|Centre|Center|Hospital|Foundation|Laboratory|Lab|Consortium))",
    ]
    for p in patterns:
        m = re.search(p, combined)
        if m:
            inst = clean_text(m.group(1))
            if 4 < len(inst) < 120:
                return inst
    return "Not extracted"

def extract_supervisor(text):
    if not text:
        return "Not found"
    patterns = [
        r"(?:supervisor|principal investigator|pi|lead investigator|mentor|host|group leader|research group leader)\s*[:\-]?\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:under the supervision of|supervised by|led by|headed by)\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return clean_text(m.group(1))
    return "Not found"

# ========================= CLASSIFICATION =========================

def contains_terms(text, terms):
    t = normalize(text)
    return any(normalize(term) in t for term in terms)

def match_priority_areas(text, priority_areas):
    t = normalize(text)
    return [area for area in priority_areas if normalize(area) in t]

def allowed_text(text, position_keywords, negative_keywords):
    t = normalize(text)
    if not t:
        return False
    if any(k in t for k in negative_keywords):
        return False
    return any(k in t for k in position_keywords) and any(
        x in t for x in [
            "multi-omics", "bioinformatics", "computational biology", "genomics",
            "single-cell", "spatial transcriptomics", "rna-seq", "scrna-seq",
            "atac-seq", "chip-seq", "metagenomics", "microbiome",
            "proteomics", "metabolomics", "machine learning", "ai",
            "precision medicine", "immunogenomics"
        ]
    )

def classify_core_area(text):
    t = normalize(text)
    groups = [
        ("Multi-omics / Integrative", ["multi-omics", "integrative omics"]),
        ("Bioinformatics / Computational Biology", ["bioinformatics", "computational biology"]),
        ("Genomics", ["genomics", "functional genomics"]),
        ("Cancer Genomics", ["cancer genomics"]),
        ("Population / Statistical Genetics", ["population genomics", "statistical genetics", "human genetics"]),
        ("Single-cell", ["single-cell", "single cell", "scrna-seq", "scRNA-seq"]),
        ("Spatial Transcriptomics", ["spatial transcriptomics", "spatial omics"]),
        ("RNA-seq", ["rna-seq", "rnaseq", "bulk rna-seq"]),
        ("Epigenomics", ["atac-seq", "chip-seq", "epigenomics"]),
        ("Microbiome / Metagenomics", ["microbiome", "metagenomics"]),
        ("Proteomics / Metabolomics", ["proteomics", "metabolomics"]),
        ("ML / AI", ["machine learning", "deep learning", "artificial intelligence", "ai"]),
        ("Precision Medicine", ["precision medicine", "personalized medicine"]),
        ("Immunogenomics", ["immunogenomics"]),
        ("Low-pass / Imputation / PRS", ["low-pass", "imputation", "polygenic risk score"]),
    ]
    hits = [label for label, terms in groups if any(term in t for term in terms)]
    return "; ".join(hits) if hits else "General omics"

def score_text(text, source_url="", priority_areas=None):
    t = normalize(text)
    score = 0

    weights = {
        "multi-omics data analysis": 35,
        "multi-omics": 30,
        "integrative omics": 30,
        "bioinformatics": 25,
        "computational biology": 25,
        "genomics": 20,
        "functional genomics": 22,
        "cancer genomics": 24,
        "population genomics": 22,
        "human genetics": 18,
        "statistical genetics": 18,
        "immunogenomics": 20,
        "single-cell": 22,
        "single cell": 22,
        "spatial transcriptomics": 22,
        "rna-seq": 18,
        "rnaseq": 18,
        "scrna-seq": 22,
        "scRNA-seq": 22,
        "atac-seq": 18,
        "chip-seq": 18,
        "epigenomics": 18,
        "metagenomics": 18,
        "microbiome": 16,
        "proteomics": 16,
        "metabolomics": 16,
        "machine learning": 18,
        "deep learning": 18,
        "artificial intelligence": 16,
        "precision medicine": 16,
        "low-pass sequencing": 16,
        "genotype imputation": 16,
        "polygenic risk score": 16,
    }
    for term, val in weights.items():
        if term in t:
            score += val

    if any(k in t for k in ["phd", "doctoral", "studentship", "esr", "early stage researcher", "jrf"]):
        score += 20
    if any(k in t for k in ["funded", "fully funded", "stipend", "scholarship", "grant"]):
        score += 15
    if "deadline" in t or "closing date" in t or "apply by" in t:
        score += 5
    if priority_areas:
        score += min(10, 2 * len(match_priority_areas(t, priority_areas)))
    if source_url and any(d in source_url for d in ["findaphd.com", "jobs.ac.uk", "euraxess", "academictransfer", "academicpositions", "maxplanck", "embl", "nih.gov", "broadinstitute.org", "fredhutch.org"]):
        score += 10

    return min(score, 100)

# ========================= ROBOTS / FETCH =========================

def fetch_url(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code in (403, 429):
            return "", f"blocked_{r.status_code}"
        if r.status_code >= 400:
            return "", f"http_{r.status_code}"
        return r.text, "ok"
    except requests.RequestException as e:
        return "", str(e)

def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    text = clean_text(soup.get_text(" ", strip=True))
    return soup, title, text

def discover_links(base_url, html, follow_terms):
    soup, _, _ = parse_html(html)
    links = []
    base_domain = domain_from_url(base_url)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = canonical_url(urljoin(base_url, href))
        if not full.startswith("http"):
            continue
        if domain_from_url(full) != base_domain and base_domain not in full:
            continue
        blob = normalize(a.get_text(" ", strip=True) + " " + full)
        if any(term in blob for term in follow_terms):
            links.append(full)
    return sorted(set(links))

def discover_rss_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", [])).lower()
        typ = (link.get("type") or "").lower()
        href = link["href"]
        if "rss" in rel or "atom" in rel or "rss" in typ or "atom" in typ:
            found.append(canonical_url(urljoin(base_url, href)))
    return sorted(set(found))

def get_sitemap_urls(base_url):
    roots = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
        urljoin(base_url, "/robots.txt"),
    ]
    return roots

# ========================= DATABASE =========================

class VacancyDB:
    def __init__(self, path=DB_FILE):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        c = self.conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_url TEXT UNIQUE,
            url TEXT,
            title TEXT,
            institution TEXT,
            country TEXT,
            region TEXT,
            source TEXT,
            deadline TEXT,
            deadline_days INTEGER,
            deadline_status TEXT,
            posted_date TEXT,
            supervisor TEXT,
            core_area TEXT,
            priority_matches TEXT,
            score INTEGER,
            status TEXT,
            snippet TEXT,
            content_hash TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS crawl_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            source TEXT,
            error TEXT,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def upsert_vacancy(self, row):
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute("SELECT id, content_hash FROM vacancies WHERE canonical_url = ?", (row["canonical_url"],))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE vacancies SET
                    url=?, title=?, institution=?, country=?, region=?, source=?, deadline=?,
                    deadline_days=?, deadline_status=?, posted_date=?, supervisor=?, core_area=?,
                    priority_matches=?, score=?, status=?, snippet=?, content_hash=?, last_seen=?
                WHERE canonical_url=?
            """, (
                row["url"], row["title"], row["institution"], row["country"], row["region"], row["source"],
                row["deadline"], row["deadline_days"], row["deadline_status"], row["posted_date"], row["supervisor"],
                row["core_area"], row["priority_matches"], row["score"], row["status"], row["snippet"],
                row["content_hash"], now, row["canonical_url"]
            ))
        else:
            cur.execute("""
                INSERT INTO vacancies (
                    canonical_url, url, title, institution, country, region, source, deadline,
                    deadline_days, deadline_status, posted_date, supervisor, core_area,
                    priority_matches, score, status, snippet, content_hash, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["canonical_url"], row["url"], row["title"], row["institution"], row["country"], row["region"],
                row["source"], row["deadline"], row["deadline_days"], row["deadline_status"], row["posted_date"],
                row["supervisor"], row["core_area"], row["priority_matches"], row["score"], row["status"],
                row["snippet"], row["content_hash"], now, now
            ))
        self.conn.commit()

    def add_error(self, url, source, error):
        self.conn.execute(
            "INSERT INTO crawl_errors (url, source, error, created_at) VALUES (?, ?, ?, ?)",
            (url, source, error, datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()

    def load_df(self):
        return pd.read_sql_query("SELECT * FROM vacancies ORDER BY score DESC, first_seen DESC", self.conn)

# ========================= CRAWLER =========================

def crawl_seed(seed_url, keywords, args, db):
    visited = set()
    queue = [(seed_url, 0)]
    found = []

    while queue:
        url, depth = queue.pop(0)
        if url in visited or (args.max_pages and len(visited) >= args.max_pages):
            continue
        visited.add(url)

        html, status = fetch_url(url, timeout=args.timeout)
        if not html:
            db.add_error(url, domain_from_url(seed_url), status)
            continue

        soup, page_title, page_text = parse_html(html)
        combined = f"{page_title} {page_text} {url}"

        if allowed_text(combined, keywords["position_keywords"], keywords["negative_keywords"]):
            deadline = extract_deadline(combined)
            dstatus, ddays = deadline_status(deadline)
            matches = match_priority_areas(combined, keywords["priority_areas"])
            core_area = classify_core_area(combined)
            country = extract_country(combined, url)
            institution = extract_institution(page_title, page_text, page_text)
            posted = extract_posted_date(combined)
            supervisor = extract_supervisor(combined)
            score = score_text(combined, url, keywords["priority_areas"])
            canon = canonical_url(url)
            row = {
                "canonical_url": canon,
                "url": url,
                "title": page_title or "No title",
                "institution": institution,
                "country": country,
                "region": "USA" if country == "United States" else "Europe" if country in [
                    "United Kingdom", "Germany", "Netherlands", "France", "Switzerland", "Sweden",
                    "Denmark", "Finland", "Norway"
                ] else "Other",
                "source": domain_from_url(seed_url),
                "deadline": deadline,
                "deadline_days": ddays,
                "deadline_status": dstatus,
                "posted_date": posted,
                "supervisor": supervisor,
                "core_area": core_area,
                "priority_matches": "; ".join(matches),
                "score": score,
                "status": "OPEN" if dstatus in {"open", "urgent", "closing_soon", "unknown"} else "EXPIRED",
                "snippet": page_text[:500],
                "content_hash": text_hash(combined),
            }
            db.upsert_vacancy(row)
            found.append(row)

        if depth < args.max_depth:
            for link in discover_rss_links(url, html):
                if link not in visited:
                    queue.append((link, depth + 1))
            for link in discover_links(url, html, keywords["follow_terms"]):
                if link not in visited:
                    queue.append((link, depth + 1))

        time.sleep(args.sleep)

    return found

# ========================= REPORTS =========================

def save_outputs(db, output_prefix):
    df = db.load_df()
    if df.empty:
        logger.warning("No data to save.")
        return df

    df.to_csv(f"{output_prefix}_all.csv", index=False, encoding="utf-8-sig")
    df[df["first_seen"] >= (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()].to_csv(
        f"{output_prefix}_new_today.csv", index=False, encoding="utf-8-sig"
    )
    if "deadline_status" in df.columns:
        df[df["deadline_status"].isin(["urgent", "closing_soon"])].to_csv(
            f"{output_prefix}_closing_soon.csv", index=False, encoding="utf-8-sig"
        )
    if "score" in df.columns:
        df[df["score"] >= 70].to_csv(f"{output_prefix}_strong_matches.csv", index=False, encoding="utf-8-sig")

    return df

def generate_html_report(df, output_path):
    html = [
        "<html><head><meta charset='utf-8'><title>Daily PhD Report</title>",
        "<style>body{font-family:Arial,sans-serif;margin:20px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:8px;font-size:13px} th{background:#f2f2f2}</style>",
        "</head><body>",
        "<h1>Daily PhD Vacancy Report</h1>"
    ]
    if not df.empty:
        sections = [
            ("New Today", df[df["first_seen"] >= (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()]),
            ("Closing Soon", df[df["deadline_status"].isin(["urgent", "closing_soon"]) if "deadline_status" in df.columns else []]),
            ("Strong Matches", df[df["score"] >= 70] if "score" in df.columns else df.head(0)),
        ]
        for title, sub in sections:
            html.append(f"<h2>{title} ({len(sub)})</h2>")
            if not sub.empty:
                show = sub[["title", "source", "country", "core_area", "deadline", "deadline_status", "score", "url"]].copy()
                html.append(show.to_html(index=False, escape=True))
            else:
                html.append("<p>None</p>")
    else:
        html.append("<p>No vacancies found.</p>")
    html.append("</body></html>")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

# ========================= CLI =========================

def parse_args():
    p = argparse.ArgumentParser(description="Direct-crawling PhD vacancy finder")
    p.add_argument("--daily", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--list-open", action="store_true")
    p.add_argument("--region", choices=["all", "europe", "usa", "canada", "australia", "asia", "india"], default="all")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--max-pages", type=int, default=30)
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    return p.parse_args()

def filter_seeds_by_region(seeds, region):
    if region == "all":
        return seeds
    r = normalize(region)
    out = []
    for s in seeds:
        d = domain_from_url(s)
        if r == "europe" and any(x in d for x in [".eu", ".uk", ".de", ".fr", ".nl", ".se", ".ch", ".dk", ".fi", ".no", ".it", ".es", ".pt", ".ie", ".be"]):
            out.append(s)
        elif r == "usa" and any(x in d for x in [".edu", "nih.gov", "genome.gov", "broadinstitute.org", "jax.org", "mskcc.org", "mdanderson.org", "stanford.edu", "harvard.edu"]):
            out.append(s)
        elif r == "canada" and any(x in d for x in [".ca"]):
            out.append(s)
        elif r == "australia" and any(x in d for x in [".edu.au"]):
            out.append(s)
        elif r == "asia" and any(x in d for x in [".sg", ".jp"]):
            out.append(s)
        elif r == "india" and any(x in d for x in [".in"]):
            out.append(s)
        elif any(x in d for x in ["nitter", "linkedin", "owlindex"]):
            out.append(s)
    return sorted(set(out)) if out else seeds

def main():
    args = parse_args()
    keywords = load_keywords()
    seeds = load_seeds()
    if not seeds:
        logger.error("No seeds found in seeds.json")
        return

    seeds = filter_seeds_by_region(seeds, args.region)
    if args.quick:
        seeds = seeds[:20]

    db = VacancyDB(DB_FILE)

    if args.list_open:
        df = db.load_df()
        if df.empty:
            print("No records.")
            return
        open_df = df[df["status"] != "EXPIRED"] if "status" in df.columns else df
        print(open_df[["title", "source", "country", "core_area", "score", "url"]].head(200).to_string(index=False))
        return

    if args.report:
        df = db.load_df()
        generate_html_report(df, REPORT_HTML)
        print(f"Report written: {REPORT_HTML}")
        return

    if args.daily or not any([args.report, args.list_open]):
        all_found = []
        for seed in seeds:
            logger.info(f"Crawling seed: {seed}")
            try:
                found = crawl_seed(seed, keywords, args, db)
                all_found.extend(found)
            except Exception as e:
                logger.exception(f"Seed failed: {seed} -> {e}")
                db.add_error(seed, domain_from_url(seed), str(e))

        df = save_outputs(db, args.output_prefix)
        generate_html_report(df, REPORT_HTML)
        print(f"\nDone. Found/updated: {len(all_found)}")
        print(f"HTML report: {REPORT_HTML}")
        print(f"CSV files use prefix: {args.output_prefix}_*.csv")

if __name__ == "__main__":
    main()
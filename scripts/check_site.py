#!/usr/bin/env python3
"""Structural checks for the built dist/ site. Exits non-zero on failure."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
ORIGIN = CONFIG["canonicalOrigin"].rstrip("/")
PREVIEW = bool(CONFIG["previewNoindex"])

EXPECTED = {
    "index.html": {
        "title": "Catalyx Technologies | Photocatalytic Oxidation (PCO) for Air and Water",
        "canonical": f"{ORIGIN}/",
        "h1": "Photocatalytic oxidation for air, and next, water.",
    },
    "technology/index.html": {
        "title": "Photocatalytic Oxidation (PCO+UV) Technology | Catalyx Technologies",
        "canonical": f"{ORIGIN}/technology/",
        "h1": "Photocatalytic oxidation (PCO): the technology behind Catalyx",
    },
    "products/index.html": {
        "title": "FRESH+™ PCO+UV Ethylene Scrubbers, EC-30 to EC-1000 | Catalyx Technologies",
        "canonical": f"{ORIGIN}/products/",
        "h1": "FRESH+™ PCO+UV air purification systems",
    },
    "water-research/index.html": {
        "title": "Photocatalytic Water Treatment R&D | Catalyx Technologies",
        "canonical": f"{ORIGIN}/water-research/",
        "h1": "Photocatalytic oxidation for water treatment",
    },
    "about/index.html": {
        "title": "About Catalyx Technologies LLC | PCO Engineering",
        "canonical": f"{ORIGIN}/about/",
        "h1": "Engineers who commercialized photocatalytic oxidation",
    },
    "contact/index.html": {
        "title": "Contact Catalyx Technologies",
        "canonical": f"{ORIGIN}/contact/",
        "h1": "Talk to Catalyx",
    },
    "privacy-policy/index.html": {
        "title": "Privacy Policy | Catalyx Technologies",
        "canonical": f"{ORIGIN}/privacy-policy/",
        "h1": "Privacy Policy",
    },
    "terms/index.html": {
        "title": "Terms of Service | Catalyx Technologies",
        "canonical": f"{ORIGIN}/terms/",
        "h1": "Terms of Service",
    },
    "sitemap/index.html": {
        "title": "Sitemap | Catalyx Technologies",
        "canonical": f"{ORIGIN}/sitemap/",
        "h1": "Sitemap",
    },
    "404.html": {
        "title": "Page not found | Catalyx Technologies",
        "canonical": None,
        "h1": "This page isn't on the site",
    },
}

FORBIDDEN = [
    "[CONFIRM]",
    "1605 Sansom",
    "19103",
    "267-606-8667",
    "2676068667",
    "892-9405",
    "colin.speer@",
    "info@catalyxtechnologies.com",
    "titanium",
    "TiO2",
    "TiO₂",
    "funded",
    "has applied",
    "15,000",
    "7,500",
    "75,000",
    "40,000",
    "150,000",
    "250,000",
    "500,000",
    "125,000",
    "EC-60",
    "EC-750",
    "EC-1500",
    "KM-1000",
    "$",
]

OG_KEYS = [
    "og:title",
    "og:description",
    "og:type",
    "og:image",
    "og:image:width",
    "og:image:height",
    "og:locale",
    "og:site_name",
]


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.json_mode = False
        self.json_buf: list[str] = []
        self.jsonld: list[str] = []
        self.in_title = False
        self.title_done = False
        self.title = ""
        self.in_h1 = False
        self.h1_count = 0
        self.h1_text = ""
        self.text: list[str] = []
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.images: list[dict] = []
        self.metas: list[dict] = []
        self.canonical = None
        self.stylesheets: list[str] = []
        self.sms: dict | None = None
        self.lang = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value for key, value in attrs}
        if tag == "html":
            self.lang = data.get("lang")
        if data.get("id"):
            self.ids.add(data["id"])
        if tag == "script" and data.get("type") == "application/ld+json":
            self.json_mode = True
            self.json_buf = []
        elif tag in {"script", "style"}:
            self.skip += 1
        if tag == "title" and not self.title_done:
            self.in_title = True
        if tag == "h1":
            self.h1_count += 1
            self.in_h1 = True
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        if tag == "img":
            self.images.append(data)
        if tag == "link":
            rel = data.get("rel") or ""
            if "canonical" in rel.split():
                self.canonical = data.get("href")
            if "stylesheet" in rel.split():
                self.stylesheets.append(data.get("href") or "")
        if tag == "meta":
            self.metas.append(data)
        if tag == "input" and data.get("id") == "sms-consent":
            self.sms = data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.json_mode:
            self.jsonld.append("".join(self.json_buf))
            self.json_mode = False
            return
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag == "title" and self.in_title:
            self.in_title = False
            self.title_done = True
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str) -> None:
        if self.json_mode:
            self.json_buf.append(data)
            return
        if self.skip:
            return
        if self.in_title:
            self.title += data
        if self.in_h1:
            self.h1_text += data
        self.text.append(data)


def failures() -> list[str]:
    problems: list[str] = []
    cname = (DIST / "CNAME").read_text(encoding="utf-8").strip() if (DIST / "CNAME").exists() else ""
    if cname != "catalyxtechnologies.com":
        problems.append(f"dist/CNAME must be catalyxtechnologies.com, got {cname!r}")
    if PREVIEW:
        problems.append("previewNoindex must be false so the custom domain is indexable")

    pages: dict[str, Page] = {}
    for rel, expect in EXPECTED.items():
        path = DIST / rel
        if not path.exists():
            problems.append(f"missing {rel}")
            continue
        parser = Page()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[rel] = parser
        if parser.lang != "en":
            problems.append(f"{rel}: html lang")
        if parser.title != expect["title"]:
            problems.append(f"{rel}: title {parser.title!r}")
        if parser.h1_count != 1:
            problems.append(f"{rel}: h1 count {parser.h1_count}")
        if " ".join(parser.h1_text.split()) != expect["h1"]:
            problems.append(f"{rel}: h1 {parser.h1_text!r}")
        if parser.canonical != expect["canonical"]:
            problems.append(f"{rel}: canonical {parser.canonical!r}")
        robots = [meta.get("content") for meta in parser.metas if meta.get("name") == "robots"]
        if rel == "404.html":
            if "noindex,follow" not in robots:
                problems.append("404.html: missing noindex,follow")
        elif PREVIEW:
            if "noindex,follow" not in robots:
                problems.append(f"{rel}: missing noindex,follow")
        elif any(value and "noindex" in value for value in robots):
            problems.append(f"{rel}: still noindex")
        description = [meta.get("content") or "" for meta in parser.metas if meta.get("name") == "description"]
        if not description or len(description[0]) < 40:
            problems.append(f"{rel}: meta description")
        props = {meta.get("property"): meta.get("content") for meta in parser.metas}
        for key in OG_KEYS:
            if not props.get(key):
                problems.append(f"{rel}: missing {key}")
        names = {meta.get("name"): meta.get("content") for meta in parser.metas}
        if names.get("twitter:card") != "summary_large_image":
            problems.append(f"{rel}: twitter card")
        if not parser.stylesheets:
            problems.append(f"{rel}: stylesheet")
        if not parser.jsonld:
            problems.append(f"{rel}: json-ld")
        else:
            try:
                data = json.loads(parser.jsonld[0])
            except json.JSONDecodeError as exc:
                problems.append(f"{rel}: json-ld {exc}")
                data = {}
            types = [node.get("@type") for node in data.get("@graph", [])]
            if "Organization" not in types or "WebSite" not in types:
                problems.append(f"{rel}: schema types {types}")
            blob = parser.jsonld[0]
            if rel == "products/index.html" and '"@type":"Product"' not in blob:
                problems.append("products: missing Product schema")
            if rel != "products/index.html" and '"@type":"Product"' in blob:
                problems.append(f"{rel}: unexpected Product schema")
            for banned in ("Offer", "AggregateRating", "Review", "Person"):
                if f'"@type":"{banned}"' in blob:
                    problems.append(f"{rel}: unexpected {banned}")
        visible = " ".join(parser.text)
        for phrase in FORBIDDEN:
            if phrase in visible:
                problems.append(f"{rel}: visible forbidden text {phrase!r}")
        if "Catalyx Technologies LLC" not in visible:
            problems.append(f"{rel}: missing legal name")
        for image in parser.images:
            if not image.get("alt") or not image.get("width") or not image.get("height"):
                problems.append(f"{rel}: image missing alt/width/height {image.get('src')}")
        if rel == "contact/index.html":
            if not parser.sms or "checked" in parser.sms or "required" in parser.sms:
                problems.append("contact: SMS checkbox must exist, unchecked, and optional")
            if "No mobile information will be shared" in visible:
                problems.append("contact: privacy sentence belongs on the privacy page")
            if "I agree to receive text messages from Catalyx Technologies LLC" not in visible:
                problems.append("contact: consent language")
        if rel == "privacy-policy/index.html":
            required = "No mobile information will be shared with third parties or affiliates for marketing or promotional purposes."
            if required not in visible:
                problems.append("privacy: missing no-share sentence")
            if "never shared with third parties" not in visible:
                problems.append("privacy: missing opt-in exclusion")
        if rel == "terms/index.html":
            for token in ("STOP", "HELP", "Msg & data rates may apply", "Message frequency"):
                if token not in visible:
                    problems.append(f"terms: missing {token}")
        if rel in {"products/index.html", "about/index.html"}:
            fresh = [link for link in parser.links if "freshplusintl.com" in link]
            if not fresh:
                problems.append(f"{rel}: missing Fresh Plus link")

    ids = {rel: page.ids for rel, page in pages.items()}
    for rel, page in pages.items():
        base = "https://local.test/" + rel
        for link in page.links:
            if link.startswith(("mailto:", "javascript:", "data:")):
                problems.append(f"{rel}: disallowed link {link}")
                continue
            absolute = urljoin(base, link)
            parts = urlsplit(absolute)
            if parts.netloc and parts.netloc != "local.test":
                if parts.scheme != "https":
                    problems.append(f"{rel}: non-https link {link}")
                continue
            target = parts.path
            if target.endswith("/"):
                target += "index.html"
            target = target.lstrip("/")
            file_path = DIST / target
            if not file_path.exists():
                problems.append(f"{rel}: broken link {link} -> {target}")
                continue
            if parts.fragment:
                owner = target if target in ids else None
                if owner is None or parts.fragment not in ids.get(target, set()):
                    problems.append(f"{rel}: missing #{parts.fragment} in {target}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8") if (DIST / "robots.txt").exists() else ""
    if f"Sitemap: {ORIGIN}/sitemap.xml" not in robots or "Allow: /" not in robots:
        problems.append("robots.txt")
    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8") if (DIST / "sitemap.xml").exists() else ""
    for info in EXPECTED.values():
        if info["canonical"] and f"<loc>{info['canonical']}</loc>" not in sitemap:
            problems.append(f"sitemap missing {info['canonical']}")
    if "<loc>" in sitemap and sitemap.count("<loc>") != 9:
        problems.append(f"sitemap url count {sitemap.count('<loc>')}")
    return problems


def main() -> None:
    found = failures()
    if found:
        print("\n".join(found))
        sys.exit(1)
    print(f"ok: {len(EXPECTED)} pages, previewNoindex={PREVIEW}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit JSON-LD in the built HTML for every URL in dist/sitemap.xml.

Reads the raw HTML files (no browser, no JavaScript). Pass --curl with the
base URL of a static server to also GET each sitemap URL and require the
served JSON-LD to match the file.

    python3 build.py
    python3 scripts/audit_jsonld.py
    python3 scripts/audit_jsonld.py --curl http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
ORIGIN = CONFIG["canonicalOrigin"].rstrip("/")
ORG_ID = f"{ORIGIN}/#organization"
SITE_ID = f"{ORIGIN}/#website"
BRAND_ID = f"{ORIGIN}/#brand"
BRAND_NAME = "FRESH+™"
SAME_AS = "https://freshplusintl.com/"
LEGAL_NAME = "Catalyx Technologies LLC"
DBA_NAME = "Fresh Plus International"

EXPECTED = {
    "/": {"type": "WebPage", "crumb": None, "file": "index.html"},
    "/technology/": {"type": "WebPage", "crumb": "Technology", "file": "technology/index.html"},
    "/products/": {"type": "CollectionPage", "crumb": "Products", "file": "products/index.html"},
    "/water-research/": {"type": "WebPage", "crumb": "Water R&D", "file": "water-research/index.html"},
    "/about/": {"type": "AboutPage", "crumb": "About", "file": "about/index.html"},
    "/contact/": {"type": "ContactPage", "crumb": "Contact", "file": "contact/index.html"},
    "/privacy-policy/": {"type": "WebPage", "crumb": "Privacy Policy", "file": "privacy-policy/index.html"},
    "/terms/": {"type": "WebPage", "crumb": "Terms of Service", "file": "terms/index.html"},
    "/sitemap/": {"type": "CollectionPage", "crumb": "Sitemap", "file": "sitemap/index.html"},
}

PAGE_TYPES = {"WebPage", "AboutPage", "ContactPage", "CollectionPage"}
ALLOWED_TYPES = PAGE_TYPES | {
    "Organization",
    "ImageObject",
    "Brand",
    "Thing",
    "WebSite",
    "BreadcrumbList",
    "ListItem",
    "ItemList",
    "Product",
    "PropertyValue",
}
FORBIDDEN_TYPES = {
    "Offer",
    "AggregateOffer",
    "AggregateRating",
    "Review",
    "Rating",
    "Person",
    "PostalAddress",
    "ContactPoint",
    "PriceSpecification",
    "MonetaryAmount",
}
FORBIDDEN_KEYS = {
    "email",
    "telephone",
    "faxNumber",
    "address",
    "streetAddress",
    "postalCode",
    "addressLocality",
    "addressRegion",
    "addressCountry",
    "price",
    "priceCurrency",
    "offers",
    "review",
    "aggregateRating",
    "ratingValue",
    "reviewCount",
}
BANNED_TEXT = (
    "1605 Sansom",
    "19103",
    "267-606-8667",
    "2676068667",
    "892-9405",
    "colin.speer@",
    "info@catalyxtechnologies.com",
    "$",
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
)
JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.DOTALL,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class AuditResult:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.lines: list[str] = []

    def fail(self, message: str) -> None:
        self.problems.append(message)

    @property
    def report(self) -> str:
        lines = list(self.lines)
        if self.problems:
            lines.append("")
            lines.append(f"FAILED {len(self.problems)}")
            lines.extend(self.problems)
        return "\n".join(lines)


def walk(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def strings(node: object):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def ref_id(value: object) -> str | None:
    if isinstance(value, dict):
        node_id = value.get("@id")
        return node_id if isinstance(node_id, str) else None
    if isinstance(value, str):
        return value
    return None


def strip_hidden(html: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    return text


def visible_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", strip_hidden(html))
    return unescape(text)


def anchor_hrefs(html: str) -> list[str]:
    return re.findall(r'<a\b[^>]*\bhref="([^"]+)"', strip_hidden(html))


def meta_content(html: str, name: str) -> str | None:
    match = re.search(
        rf'<meta name="{re.escape(name)}" content="([^"]*)"',
        html,
    )
    return unescape(match.group(1)) if match else None


def title_text(html: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html, flags=re.DOTALL)
    return unescape(match.group(1)).strip() if match else None


def canonical_href(html: str) -> str | None:
    match = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return unescape(match.group(1)) if match else None


def sitemap_locs(dist: Path) -> list[str]:
    import xml.etree.ElementTree as ET

    root = ET.parse(dist / "sitemap.xml").getroot()
    locs = []
    for node in root.findall("sm:url/sm:loc", SITEMAP_NS):
        if node.text:
            locs.append(node.text.strip())
    return locs


def site_facts(dist: Path) -> tuple[set[str], set[str], set[str]]:
    hrefs: set[str] = set()
    emails: set[str] = set()
    tels: set[str] = set()
    for path in sorted(dist.rglob("*.html")):
        html = path.read_text(encoding="utf-8")
        hrefs.update(anchor_hrefs(html))
        emails.update(EMAIL_RE.findall(visible_text(html)))
        tels.update(href for href in anchor_hrefs(html) if href.startswith("tel:"))
    return hrefs, emails, tels


def types_of(data: dict) -> list[str]:
    found = []
    for node in walk(data):
        kind = node.get("@type")
        if isinstance(kind, str):
            found.append(kind)
        elif kind is not None:
            found.append(repr(kind))
    return found


def check_page(
    result: AuditResult,
    dist: Path,
    loc: str,
    html: str,
    expect: dict,
    hrefs: set[str],
    emails: set[str],
    tels: set[str],
) -> None:
    path = urlsplit(loc).path or "/"
    label = loc
    blocks = JSONLD_RE.findall(html)
    head, _, body = html.partition("<body")
    lines = [f"PASS {label}"]
    problems_before = len(result.problems)

    def bad(message: str) -> None:
        result.fail(f"{label}: {message}")

    if len(blocks) != 1:
        bad(f"expected 1 JSON-LD script, found {len(blocks)}")
    if "application/ld+json" not in head:
        bad("JSON-LD script is not in <head> before <body>")
    if "application/ld+json" in body:
        bad("JSON-LD script also appears after <body>")
    if not blocks:
        lines[0] = f"FAIL {label}"
        result.lines.extend(lines)
        return

    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        bad(f"JSON did not parse: {exc}")
        lines[0] = f"FAIL {label}"
        result.lines.extend(lines)
        return

    if data.get("@context") != "https://schema.org":
        bad(f"@context is {data.get('@context')!r}")
    graph = data.get("@graph")
    if not isinstance(graph, list) or not graph:
        bad("@graph is missing")
        graph = []

    found_types = types_of(data)
    for kind in found_types:
        if kind in FORBIDDEN_TYPES:
            bad(f"forbidden type {kind}")
        elif kind not in ALLOWED_TYPES:
            bad(f"unexpected type {kind}")
    for node in walk(data):
        for key in node:
            if key in FORBIDDEN_KEYS:
                bad(f"forbidden field {key}")
    blob = "\n".join(strings(data))
    for phrase in BANNED_TEXT:
        if phrase in blob:
            bad(f"banned text {phrase!r}")
    for text in strings(data):
        if re.search(r"FRESH\+(?!™)", text):
            bad(f"brand is not FRESH+™ in {text[:80]!r}")

    orgs = [node for node in graph if node.get("@type") == "Organization"]
    brands = [node for node in graph if node.get("@type") == "Brand"]
    sites = [node for node in graph if node.get("@type") == "WebSite"]
    pages = [node for node in graph if node.get("@type") in PAGE_TYPES]
    crumbs = [node for node in graph if node.get("@type") == "BreadcrumbList"]
    if len(orgs) != 1:
        bad(f"expected 1 Organization node, found {len(orgs)}")
    if len(brands) != 1:
        bad(f"expected 1 Brand node, found {len(brands)}")
    if len(sites) != 1:
        bad(f"expected 1 WebSite node, found {len(sites)}")
    if len(pages) != 1:
        bad(f"expected 1 page node, found {len(pages)}")

    org = orgs[0] if orgs else {}
    brand = brands[0] if brands else {}
    site = sites[0] if sites else {}
    page = pages[0] if pages else {}

    if org.get("@id") != ORG_ID:
        bad(f"Organization @id is {org.get('@id')!r}")
    if org.get("legalName") != LEGAL_NAME:
        bad(f"legalName is {org.get('legalName')!r}")
    alternate = org.get("alternateName")
    alternate_values = alternate if isinstance(alternate, list) else [alternate]
    if DBA_NAME not in alternate_values:
        bad(f"alternateName does not include {DBA_NAME}")
    if f"{LEGAL_NAME}, DBA {DBA_NAME}" not in str(org.get("description")):
        bad("Organization description does not state the legal entity and DBA")
    if org.get("url") != f"{ORIGIN}/":
        bad(f"Organization url is {org.get('url')!r}")
    if org.get("sameAs") != [SAME_AS]:
        bad(f"sameAs is {org.get('sameAs')!r}")
    elif SAME_AS not in hrefs:
        bad(f"sameAs {SAME_AS} is not a visible link on the site")
    logo = org.get("logo")
    if not isinstance(logo, dict) or logo.get("@type") != "ImageObject" or not logo.get("url"):
        bad("Organization logo is missing")
    else:
        logo_path = str(logo["url"])
        if not logo_path.startswith(f"{ORIGIN}/"):
            bad(f"logo url is not on the site origin: {logo_path}")
        else:
            relative = logo_path[len(ORIGIN) + 1 :]
            if not (dist / relative).is_file():
                bad(f"logo file is missing: {relative}")
    if ref_id(org.get("brand")) != BRAND_ID:
        bad("Organization brand does not reference the Brand @id")
    if emails:
        bad(f"visible email addresses are not in the Organization node: {sorted(emails)}")
    if tels:
        bad(f"visible telephone links are not in the Organization node: {sorted(tels)}")

    if brand.get("@id") != BRAND_ID or brand.get("name") != BRAND_NAME:
        bad(f"Brand is {brand.get('@id')!r} {brand.get('name')!r}")

    if site.get("@id") != SITE_ID:
        bad(f"WebSite @id is {site.get('@id')!r}")
    if ref_id(site.get("publisher")) != ORG_ID:
        bad("WebSite publisher does not reference the Organization @id")

    title = title_text(html)
    description = meta_content(html, "description")
    canonical = canonical_href(html)
    if page.get("@type") != expect["type"]:
        bad(f"page type is {page.get('@type')!r}, expected {expect['type']}")
    if page.get("url") != loc or canonical != loc:
        bad(f"page url {page.get('url')!r} canonical {canonical!r} sitemap {loc}")
    if page.get("name") != title:
        bad(f"name does not match <title>: {page.get('name')!r} != {title!r}")
    if page.get("description") != description:
        bad("description does not match meta description")
    if ref_id(page.get("isPartOf")) != SITE_ID:
        bad("isPartOf does not reference the WebSite @id")
    if ref_id(page.get("about")) != ORG_ID:
        bad("about does not reference the Organization @id")
    if ref_id(page.get("publisher")) != ORG_ID:
        bad("publisher does not reference the Organization @id")
    if page.get("@id") != f"{loc}#webpage":
        bad(f"page @id is {page.get('@id')!r}")

    crumb_name = expect["crumb"]
    if crumb_name is None:
        if crumbs:
            bad("homepage includes a BreadcrumbList")
        crumb_report = "BreadcrumbList: none (homepage)"
    else:
        crumb_report = f"BreadcrumbList: Home → {crumb_name}"
        if len(crumbs) != 1:
            bad(f"expected 1 BreadcrumbList, found {len(crumbs)}")
        elif ref_id(page.get("breadcrumb")) != crumbs[0].get("@id"):
            bad("WebPage.breadcrumb does not reference the BreadcrumbList @id")
        else:
            items = crumbs[0].get("itemListElement")
            if not isinstance(items, list) or len(items) != 2:
                bad("BreadcrumbList does not have Home and the current page")
            else:
                home, current = items
                if home.get("position") != 1 or home.get("name") != "Home" or home.get("item") != f"{ORIGIN}/":
                    bad(f"breadcrumb home item is {home!r}")
                if current.get("position") != 2 or current.get("name") != crumb_name or current.get("item") != loc:
                    bad(f"breadcrumb current item is {current!r}")
                if crumb_name not in visible_text(html):
                    bad(f"breadcrumb name {crumb_name!r} is not visible on the page")

    products = [node for node in walk(data) if node.get("@type") == "Product"]
    product_report = ""
    if path == "/products/":
        if not products:
            bad("products page has no Product nodes")
        names = []
        seen = visible_text(html)
        if "Made in the USA" not in seen and "Made in USA" not in seen:
            bad("countryOfOrigin is set but the page does not say the products are made in the USA")
        for product in products:
            name = str(product.get("name") or "")
            names.append(name)
            if not name.startswith(f"{BRAND_NAME} "):
                bad(f"product name {name!r} does not use {BRAND_NAME}")
            model = name[len(BRAND_NAME) + 1 :]
            if model and model not in seen:
                bad(f"product model {model!r} is not visible on the page")
            if ref_id(product.get("brand")) != BRAND_ID:
                bad(f"{name} brand does not reference {BRAND_ID}")
            if ref_id(product.get("manufacturer")) != ORG_ID:
                bad(f"{name} manufacturer does not reference {ORG_ID}")
            for prop in product.get("additionalProperty") or []:
                value = str(prop.get("value") or "")
                if value and value not in seen:
                    bad(f"{name} property {prop.get('name')!r}={value!r} is not visible on the page")
            material = product.get("material")
            if material and str(material) not in seen:
                bad(f"{name} material {material!r} is not visible on the page")
        item_lists = [node for node in graph if node.get("@type") == "ItemList"]
        if len(item_lists) != 1:
            bad(f"expected 1 ItemList, found {len(item_lists)}")
        elif item_lists[0].get("numberOfItems") != len(products):
            bad("ItemList numberOfItems does not match the Product nodes")
        elif ref_id(page.get("mainEntity")) != item_lists[0].get("@id"):
            bad("CollectionPage mainEntity does not reference the ItemList")
        product_report = "Products: " + ", ".join(names)
    elif products:
        bad("Product node on a non-product page")

    if len(result.problems) > problems_before:
        lines[0] = f"FAIL {label}"
    lines.append(f"  script: {len(blocks)} block, valid JSON, in <head> before <body>")
    lines.append(
        f"  {page.get('@type')} {page.get('@id')}"
    )
    lines.append("  url matches canonical and sitemap; name matches <title>; description matches meta")
    lines.append(f"  isPartOf {SITE_ID}")
    lines.append(f"  about {ORG_ID}")
    lines.append(f"  publisher {ORG_ID}")
    lines.append(f"  {crumb_report}")
    lines.append(
        f"  Organization {ORG_ID}: legalName {LEGAL_NAME}; alternateName {DBA_NAME}; sameAs {SAME_AS}"
    )
    lines.append("  contact fields present: url, logo")
    lines.append("  contact fields omitted (not visible on the site): email, telephone, streetAddress")
    lines.append(f"  Brand: {brand.get('name')}")
    if product_report:
        lines.append(f"  {product_report}")
        lines.append("  offers, prices, ratings, reviews: absent")
    result.lines.extend(lines)
    result.lines.append("")


def curl_page(loc: str, file_html: str, base: str) -> tuple[list[str], list[str]]:
    path = urlsplit(loc).path or "/"
    url = base.rstrip("/") + path
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        header_path = Path(tmp) / "headers"
        body_path = Path(tmp) / "body"
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-A",
                "GPTBot/1.1",
                "-D",
                str(header_path),
                "-o",
                str(body_path),
                "-w",
                "%{http_code}",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        status = proc.stdout.strip()
        headers = header_path.read_text(encoding="utf-8", errors="replace") if header_path.exists() else ""
        served = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
    if proc.returncode != 0:
        problems.append(f"{url}: curl failed: {proc.stderr.strip()}")
        return problems, [f"FAIL {url} curl exit {proc.returncode} {proc.stderr.strip()}"]
    file_blocks = JSONLD_RE.findall(file_html)
    served_blocks = JSONLD_RE.findall(served)
    content_type = ""
    for line in headers.splitlines():
        if line.lower().startswith("content-type:"):
            content_type = line.split(":", 1)[1].strip()
    if status != "200":
        problems.append(f"{url}: HTTP {status}")
    if "text/html" not in content_type:
        problems.append(f"{url}: content-type {content_type!r}")
    if served_blocks != file_blocks:
        problems.append(f"{url}: served JSON-LD does not match the built file")
    if not served_blocks:
        problems.append(f"{url}: served HTML has no JSON-LD")
    head, _, _body = served.partition("<body")
    if served_blocks and served_blocks[0] not in head:
        problems.append(f"{url}: served JSON-LD is not before <body>")
    flag = "PASS" if not problems else "FAIL"
    lines = [
        f"{flag} {url}",
        f"  HTTP {status}; content-type: {content_type or 'missing'}; bytes: {len(served.encode('utf-8'))}",
        f"  user-agent: GPTBot/1.1; JavaScript: not executed",
        f"  JSON-LD blocks: {len(served_blocks)}; matches built file: {'yes' if served_blocks == file_blocks else 'no'}",
    ]
    return problems, lines


def audit(dist: Path | None = None, curl_base: str | None = None) -> AuditResult:
    result = AuditResult()
    dist = dist or DIST
    result.lines.append("JSON-LD audit")
    result.lines.append(f"source: {dist}/ HTML for every <loc> in sitemap.xml")
    result.lines.append("parser: Python json.loads on the raw <script type=\"application/ld+json\"> text")
    result.lines.append("")
    if not (dist / "sitemap.xml").is_file():
        result.fail(f"missing {dist / 'sitemap.xml'}; run python3 build.py first")
        result.lines.append("FAILED before reading pages")
        return result

    locs = sitemap_locs(dist)
    expected_locs = [ORIGIN + path for path in EXPECTED]
    if locs != expected_locs:
        result.fail(f"sitemap URLs {locs} != expected {expected_locs}")
    hrefs, emails, tels = site_facts(dist)
    result.lines.append(
        "Visible site contact facts: "
        f"emails={sorted(emails) or 'none'}; tel links={sorted(tels) or 'none'}; "
        f"sameAs target linked={SAME_AS in hrefs}"
    )
    result.lines.append("")

    pages: list[tuple[str, str]] = []
    for loc in locs:
        path = urlsplit(loc).path or "/"
        expect = EXPECTED.get(path)
        if expect is None:
            result.fail(f"{loc}: no expected schema for this sitemap URL")
            continue
        file_path = dist / expect["file"]
        if not file_path.is_file():
            result.fail(f"{loc}: missing {file_path}")
            continue
        html = file_path.read_text(encoding="utf-8")
        pages.append((loc, html))
        check_page(result, dist, loc, html, expect, hrefs, emails, tels)

    if len(locs) != 9:
        result.fail(f"expected 9 sitemap URLs, found {len(locs)}")
    result.lines.append("Shared graph")
    result.lines.append(f"  Organization @id {ORG_ID} on every page")
    result.lines.append(f"  legal entity: {LEGAL_NAME}, DBA {DBA_NAME}")
    result.lines.append(f"  WebSite @id {SITE_ID}; Brand @id {BRAND_ID}; Brand name {BRAND_NAME}")
    result.lines.append(f"  sameAs kept: {SAME_AS}")
    result.lines.append("  no street address, email, telephone, offer, price, rating, or review")
    failed_pages = set()
    for problem in result.problems:
        for loc in locs:
            if problem.startswith(loc + ":"):
                failed_pages.add(loc)
    passed_pages = len(locs) - len(failed_pages)
    result.lines.append("")
    result.lines.append(f"Result: {passed_pages}/{len(locs)} sitemap pages passed")

    if curl_base:
        result.lines.append("")
        result.lines.append(f"No-JS curl check against {curl_base}")
        result.lines.append("Each URL was fetched with curl -A GPTBot/1.1. curl does not run JavaScript.")
        result.lines.append("")
        curl_failed = 0
        for loc, html in pages:
            problems, lines = curl_page(loc, html, curl_base)
            if problems:
                curl_failed += 1
            for problem in problems:
                result.fail(problem)
            result.lines.extend(lines)
        result.lines.append("")
        result.lines.append(
            f"Curl result: {len(pages) - curl_failed}/{len(pages)} responses matched the built JSON-LD"
        )
    return result


def problems_for_dist(dist: Path | None = None) -> list[str]:
    return audit(dist or DIST).problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit JSON-LD in the built Catalyx HTML")
    parser.add_argument("--dist", type=Path, default=DIST)
    parser.add_argument(
        "--curl",
        metavar="BASE",
        help="Also GET each sitemap URL with curl (no JavaScript) and compare JSON-LD",
    )
    args = parser.parse_args(argv)
    result = audit(args.dist, curl_base=args.curl)
    print(result.report)
    return 1 if result.problems else 0


if __name__ == "__main__":
    sys.exit(main())

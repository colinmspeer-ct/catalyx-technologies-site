#!/usr/bin/env python3
"""Build the Catalyx Technologies static site into dist/.

site.config.json → previewNoindex.
false: pages are indexable and dist/CNAME is catalyxtechnologies.com.
true: every page sends noindex,follow (except the 404, which always does).
"""

from __future__ import annotations

import html
import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))

ORIGIN = CONFIG["canonicalOrigin"].rstrip("/")
PREVIEW_NOINDEX = bool(CONFIG["previewNoindex"])
GITHUB_BASE = CONFIG["githubPagesBase"]
if not GITHUB_BASE.startswith("/"):
    GITHUB_BASE = "/" + GITHUB_BASE
if not GITHUB_BASE.endswith("/"):
    GITHUB_BASE += "/"

WORDMARK_ALT = (
    "Catalyx Technologies logo. A blue molecular-network letter C sits beside the words "
    "Catalyx technologies. The mark identifies the company behind FRESH+ photocatalytic "
    "oxidation air systems and water-treatment research."
)
STACKED_ALT = (
    "Catalyx Technologies stacked logo. The blue molecular C wraps the word Catalyx, with "
    "the word technologies set beside it. It is the company mark for FRESH+ air systems "
    "and photocatalytic oxidation research."
)
OG_ALT = (
    "Catalyx Technologies. Photocatalytic oxidation for air, and next, water. "
    "FRESH+ air systems and water-treatment research."
)

KNOWS_ABOUT = [
    ("Photocatalysis", "https://en.wikipedia.org/wiki/Photocatalysis", "https://www.wikidata.org/wiki/Q218831"),
    ("Ethylene", "https://en.wikipedia.org/wiki/Ethylene", "https://www.wikidata.org/wiki/Q151313"),
    ("Volatile organic compound", "https://en.wikipedia.org/wiki/Volatile_organic_compound", "https://www.wikidata.org/wiki/Q910267"),
    ("Advanced oxidation process", "https://en.wikipedia.org/wiki/Advanced_oxidation_process", "https://www.wikidata.org/wiki/Q379650"),
    ("Hydroxyl radical", "https://en.wikipedia.org/wiki/Hydroxyl_radical", "https://www.wikidata.org/wiki/Q427071"),
    ("Ultraviolet germicidal irradiation", "https://en.wikipedia.org/wiki/Ultraviolet_germicidal_irradiation", "https://www.wikidata.org/wiki/Q646008"),
    ("Small Business Innovation Research", "https://en.wikipedia.org/wiki/Small_Business_Innovation_Research", "https://www.wikidata.org/wiki/Q7542693"),
    ("Cold chain", "https://en.wikipedia.org/wiki/Cold_chain", "https://www.wikidata.org/wiki/Q592197"),
]

PRODUCTS = [
    {
        "model": "EC-30",
        "slug": "ec-30",
        "airflow": "30 CFM",
        "lamps": "2",
        "dimensions": "24″ L × 4″ W × 4″ H",
        "weight": "10 lb",
        "electrical": "1.3 A, 6-ft lead with plug",
        "material": "304 stainless steel",
        "summary": "Compact unit with a dual-impeller fan for small rooms, coolers, and displays.",
        "extra": "",
    },
    {
        "model": "EC-150",
        "slug": "ec-150",
        "airflow": "150 CFM",
        "lamps": "4",
        "dimensions": "84″ L × 14″ W × 14″ H",
        "weight": "120 lb",
        "electrical": "6 A, 6-ft lead with plug",
        "material": "304 stainless steel",
        "summary": "Centrifugal fan. Front control panel with an hour counter, UV lamp indicator lights, and low-airflow indication.",
        "extra": "",
    },
    {
        "model": "EC-300",
        "slug": "ec-300",
        "airflow": "300 CFM",
        "lamps": "8",
        "dimensions": "84″ L × 14″ W × 14″ H",
        "weight": "140 lb",
        "electrical": "12 A, 6-ft lead with plug",
        "material": "304 stainless steel",
        "summary": "Centrifugal fan. Front control panel with an hour counter, UV lamp indicator lights, and low-airflow indication.",
        "extra": "",
    },
    {
        "model": "EC-500",
        "slug": "ec-500",
        "airflow": "500 CFM",
        "lamps": "8",
        "dimensions": "70″ L × 24″ W × 18″ H",
        "weight": "200 lb",
        "electrical": "12 A, 6-ft lead with plug",
        "material": "304 stainless steel",
        "summary": "Centrifugal fan. Front control panel with an hour counter, UV lamp indicator lights, and low-airflow indication.",
        "extra": "",
    },
    {
        "model": "EC-1000",
        "slug": "ec-1000",
        "airflow": "1,000 CFM, 1–100% speed control",
        "lamps": "16",
        "dimensions": "80″ L × 24″ W × 27″",
        "weight": "400 lb",
        "electrical": "15 A, hardwired",
        "material": "304 stainless steel or aluminum",
        "summary": "Axial fan with speed control. Hard-wired control panel with a disconnect switch and a fan-speed potentiometer. Ballast panel with an hour counter and lamp indicators. MERV 8 prefilter plus an organic roughing filter.",
        "extra": "",
    },
]

PAGES = [
    {
        "file": "home.html",
        "out": "index.html",
        "path": "/",
        "nav": "",
        "title": "Catalyx Technologies | Photocatalytic Oxidation (PCO) for Air and Water",
        "description": "Catalyx Technologies developed and commercialized PCO+UV air purification (FRESH+™) and is now applying photocatalytic oxidation to water treatment.",
    },
    {
        "file": "technology.html",
        "out": "technology/index.html",
        "path": "/technology/",
        "nav": "technology",
        "title": "Photocatalytic Oxidation (PCO+UV) Technology | Catalyx Technologies",
        "description": "Photocatalytic oxidation (PCO+UV) uses UV light on a photocatalyst to generate hydroxyl radicals. Catalyx Technologies commercialized the process in FRESH+™ air systems.",
    },
    {
        "file": "products.html",
        "out": "products/index.html",
        "path": "/products/",
        "nav": "products",
        "title": "FRESH+™ PCO+UV Ethylene Scrubbers, EC-30 to EC-1000 | Catalyx Technologies",
        "description": "FRESH+™ PCO+UV systems for produce, floral, and cold-chain storage, from EC-30 to EC-1000. Made in the USA, 304 stainless steel, no ozone and no chemical pellets.",
        "products": True,
    },
    {
        "file": "water.html",
        "out": "water-research/index.html",
        "path": "/water-research/",
        "nav": "water",
        "title": "Photocatalytic Water Treatment R&D | Catalyx Technologies",
        "description": "Catalyx Technologies is researching photocatalytic oxidation for water treatment and intends to pursue SBIR Phase I funding. This is R&D, not a product, and no performance is claimed.",
    },
    {
        "file": "about.html",
        "out": "about/index.html",
        "path": "/about/",
        "nav": "about",
        "title": "About Catalyx Technologies LLC | PCO Engineering",
        "description": "Catalyx Technologies LLC engineers photocatalytic oxidation systems. Through Fresh Plus International it sells FRESH+™ PCO+UV air systems for produce and cold-chain storage.",
    },
    {
        "file": "contact.html",
        "out": "contact/index.html",
        "path": "/contact/",
        "nav": "contact",
        "title": "Contact Catalyx Technologies",
        "description": "Contact Catalyx Technologies LLC about a FRESH+™ quote, a water-treatment research partnership, a pilot site, or an investment conversation.",
    },
    {
        "file": "privacy.html",
        "out": "privacy-policy/index.html",
        "path": "/privacy-policy/",
        "nav": "",
        "title": "Privacy Policy | Catalyx Technologies",
        "description": "Privacy Policy for Catalyx Technologies LLC. Mobile numbers and SMS opt-in data are never shared or sold to third parties.",
    },
    {
        "file": "terms.html",
        "out": "terms/index.html",
        "path": "/terms/",
        "nav": "",
        "title": "Terms of Service | Catalyx Technologies",
        "description": "Terms of Service for catalyxtechnologies.com, including the Catalyx Technologies LLC text-message program: frequency, rates, STOP, and HELP.",
    },
    {
        "file": "sitemap.html",
        "out": "sitemap/index.html",
        "path": "/sitemap/",
        "nav": "",
        "title": "Sitemap | Catalyx Technologies",
        "description": "HTML sitemap of the Catalyx Technologies site: technology, FRESH+™ products, water research, about, contact, privacy, and terms.",
    },
]

NAV = [
    ("technology/", "Technology", "technology"),
    ("products/", "Products", "products"),
    ("water-research/", "Water R&D", "water"),
    ("about/", "About", "about"),
    ("contact/", "Contact", "contact"),
]


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"Not a PNG: {path}")
        handle.read(4)
        if handle.read(4) != b"IHDR":
            raise SystemExit(f"Missing IHDR: {path}")
        return struct.unpack(">II", handle.read(8))


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def page_base(out: str) -> str:
    depth = out.count("/")
    return "../" * depth


def href(base: str, path: str) -> str:
    if path == "":
        return base if base else "./"
    return base + path


def picture(base: str, stem: str, alt: str, width: int, height: int, loading: str | None = None, fetchpriority: str | None = None) -> str:
    attrs = [
        f'src="{base}assets/img/{stem}.png"',
        f'alt="{esc(alt)}"',
        f'width="{width}"',
        f'height="{height}"',
    ]
    if loading:
        attrs.append(f'loading="{loading}"')
    if fetchpriority:
        attrs.append(f'fetchpriority="{fetchpriority}"')
    return (
        "<picture>"
        f'<source srcset="{base}assets/img/{stem}.webp" type="image/webp">'
        f'<img {" ".join(attrs)}>'
        "</picture>"
    )


def product_description(item: dict) -> str:
    return (
        f"FRESH+ {item['model']} is a PCO+UV air purification system for produce, floral, and cold-chain storage. "
        f"Airflow is {item['airflow']}. It uses {item['lamps']} UV-C lamps rated for 2 years with a shatterproof Teflon coating, "
        f"a MERV prefilter, and proprietary catalytic filters. Construction is {item['material']}. "
        f"Dimensions {item['dimensions']}. Weight {item['weight']}. "
        f"Electrical supply is 120/220V single phase 50/60 Hz; draw is {item['electrical']}. "
        f"Made in the USA. No ozone and no chemical pellets. {item['summary']}"
    )


def product_table() -> str:
    rows = []
    for item in PRODUCTS:
        rows.append(
            "<tr>"
            f'<th scope="row"><a href="#{item["slug"]}">{esc(item["model"])}</a></th>'
            f"<td>{esc(item['airflow'])}</td>"
            f"<td>{esc(item['lamps'])}</td>"
            f"<td>{esc(item['dimensions'])}</td>"
            f"<td>{esc(item['weight'])}</td>"
            f"<td>{esc(item['electrical'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-scroll"><table>'
        '<caption>FRESH+<span class="tm">™</span> model specifications. Room coverage is not listed.</caption>'
        "<thead><tr>"
        '<th scope="col">Model</th><th scope="col">Airflow</th><th scope="col">UV-C lamps</th>'
        '<th scope="col">Dimensions</th><th scope="col">Weight</th><th scope="col">Electrical</th>'
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def product_blocks(base: str) -> str:
    blocks = []
    for item in PRODUCTS:
        quote = esc(f"{base}contact/?interest=quote&model={item['model']}#contact-form")
        blocks.append(
            f'<article class="model-block" id="{item["slug"]}">'
            f"<h2>{esc(item['model'])}</h2>"
            f"<p>{esc(item['summary'])}</p>"
            '<dl class="specs">'
            f"<div><dt>Airflow</dt><dd>{esc(item['airflow'])}</dd></div>"
            f"<div><dt>UV-C lamps</dt><dd>{esc(item['lamps'])}</dd></div>"
            f"<div><dt>Dimensions</dt><dd>{esc(item['dimensions'])}</dd></div>"
            f"<div><dt>Weight</dt><dd>{esc(item['weight'])}</dd></div>"
            f"<div><dt>Electrical</dt><dd>{esc(item['electrical'])}</dd></div>"
            f"<div><dt>Construction</dt><dd>{esc(item['material'])}</dd></div>"
            "</dl>"
            f'<p><a class="btn btn-p" href="{quote}">Request a quote</a></p>'
            "</article>"
        )
    return "\n".join(blocks)


def json_ld(page: dict, logo_w: int, logo_h: int, og_name: str) -> str:
    org_id = f"{ORIGIN}/#organization"
    site_id = f"{ORIGIN}/#website"
    org = {
        "@type": "Organization",
        "@id": org_id,
        "name": "Catalyx Technologies",
        "legalName": "Catalyx Technologies LLC",
        "alternateName": ["Fresh Plus International", "FRESH+"],
        "url": f"{ORIGIN}/",
        "logo": {
            "@type": "ImageObject",
            "url": f"{ORIGIN}/assets/img/catalyx-technologies-mark.webp",
            "width": logo_w,
            "height": logo_h,
        },
        "brand": {"@type": "Brand", "name": "FRESH+"},
        "sameAs": ["https://freshplusintl.com/"],
        "description": (
            "Catalyx Technologies LLC is an engineering company focused on photocatalytic oxidation. "
            "Through its Fresh Plus International division it designs and sells FRESH+ PCO+UV air systems, "
            "and it is applying that chemistry to water-treatment research."
        ),
        "knowsAbout": [
            {"@type": "Thing", "name": name, "sameAs": [wiki, wikidata]}
            for name, wiki, wikidata in KNOWS_ABOUT
        ],
    }
    website = {
        "@type": "WebSite",
        "@id": site_id,
        "url": f"{ORIGIN}/",
        "name": "Catalyx Technologies",
        "publisher": {"@id": org_id},
    }
    graph = [org, website]
    if page.get("products"):
        elements = []
        for index, item in enumerate(PRODUCTS, start=1):
            elements.append(
                {
                    "@type": "ListItem",
                    "position": index,
                    "item": {
                        "@type": "Product",
                        "name": f"FRESH+ {item['model']}",
                        "model": item["model"],
                        "description": product_description(item),
                        "url": f"{ORIGIN}/products/#{item['slug']}",
                        "brand": {"@type": "Brand", "name": "FRESH+"},
                        "manufacturer": {
                            "@type": "Organization",
                            "name": "Catalyx Technologies LLC",
                            "url": f"{ORIGIN}/",
                        },
                        "material": item["material"],
                        "countryOfOrigin": "US",
                        "additionalProperty": [
                            {"@type": "PropertyValue", "name": "Airflow", "value": item["airflow"]},
                            {"@type": "PropertyValue", "name": "UV-C lamps", "value": item["lamps"]},
                            {"@type": "PropertyValue", "name": "Dimensions", "value": item["dimensions"]},
                            {"@type": "PropertyValue", "name": "Weight", "value": item["weight"]},
                            {"@type": "PropertyValue", "name": "Electrical", "value": item["electrical"]},
                            {"@type": "PropertyValue", "name": "Supply", "value": "120/220V single phase 50/60 Hz"},
                        ],
                    },
                }
            )
        graph.append(
            {
                "@type": "ItemList",
                "name": "FRESH+ PCO+UV air purification systems",
                "numberOfItems": len(PRODUCTS),
                "itemListElement": elements,
            }
        )
    payload = {"@context": "https://schema.org", "@graph": graph}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c")


def header(base: str, current: str, word_w: int, word_h: int) -> str:
    items = []
    for path, label, key in NAV:
        current_attr = ' aria-current="page"' if key == current else ""
        items.append(f'<li><a href="{href(base, path)}"{current_attr}>{label}</a></li>')
    logo = picture(base, "catalyx-technologies-wordmark", WORDMARK_ALT, word_w, word_h, fetchpriority="high")
    return f"""<a class="skip" href="#main">Skip to content</a>
<header>
  <div class="wrap nav">
    <a class="brand" href="{href(base, "")}">{logo}</a>
    <input id="nav-toggle" class="nav-toggle" type="checkbox" aria-controls="site-nav" aria-label="Site menu">
    <label class="nav-burger" for="nav-toggle"><span class="when-closed">Menu</span><span class="when-open">Close</span></label>
    <nav id="site-nav" class="nav-links" aria-label="Primary">
      <ul>
        {"".join(items)}
      </ul>
      <a class="btn btn-p" href="{href(base, "contact/")}">Talk to our team</a>
    </nav>
  </div>
</header>"""


def footer(base: str, stack_w: int, stack_h: int) -> str:
    company = []
    for path, label, _key in NAV:
        company.append(f'<li><a href="{href(base, path)}">{label}</a></li>')
    logo = picture(base, "catalyx-technologies-logo-stacked", STACKED_ALT, stack_w, stack_h, loading="lazy")
    return f"""<footer>
  <div class="wrap">
    <div class="fgrid">
      <div>
        <a class="footer-brand" href="{href(base, "")}">{logo}</a>
        <p>Catalyx Technologies LLC<br>DBA Fresh Plus International</p>
        <!-- NAP PLACEHOLDERS. Do not publish until Colin confirms them.
             [CONFIRM ADDRESS] HighLevel profile shows 1605 Sansom Street, Philadelphia, PA 19103.
             [CONFIRM PHONE] Public line. freshplusintl.com uses (610) 892-9405. HighLevel profile uses 267-606-8667.
             [CONFIRM EMAIL] Example in the draft: info@catalyxtechnologies.com. HighLevel shows colin.speer@catalyxtechnologies.com.
             [CONFIRM hours, ET]
        -->
        <p class="nap-pending">Address, phone, and email will be published after they are confirmed.</p>
      </div>
      <div>
        <p class="footer-heading">Company</p>
        <ul>
          {"".join(company)}
        </ul>
      </div>
      <div>
        <p class="footer-heading">Legal</p>
        <ul>
          <li><a href="{href(base, "privacy-policy/")}">Privacy Policy</a></li>
          <li><a href="{href(base, "terms/")}">Terms of Service</a></li>
          <li><a href="{href(base, "sitemap/")}">Sitemap</a></li>
        </ul>
      </div>
    </div>
    <div class="legal">
      <!-- [CONFIRM trademark owner entity] The draft names Catalyx Technologies LLC. -->
      <span>© 2026 Catalyx Technologies LLC. FRESH+<span class="tm">™</span> is a trademark of Catalyx Technologies LLC.</span>
      <span>Mobile numbers and SMS opt-in data are never shared or sold.</span>
    </div>
  </div>
</footer>"""


def robots_meta(always_noindex: bool) -> str:
    if always_noindex:
        return (
            "<!-- 404 stays noindex after cutover. It is an error page, not a landing page. -->\n"
            '<meta name="robots" content="noindex,follow">'
        )
    if PREVIEW_NOINDEX:
        return (
            "<!--\n"
            "  PREVIEW NOINDEX\n"
            "  Source of truth: site.config.json → previewNoindex.\n"
            "  CUTOVER: set previewNoindex to false when https://catalyxtechnologies.com is the live host, then rebuild.\n"
            "  That removes the robots meta tag below. Do not add a CNAME file.\n"
            "-->\n"
            '<meta name="robots" content="noindex,follow">'
        )
    return (
        "<!-- Indexing is on. site.config.json → previewNoindex is false. "
        "Set it back to true if this build is served from the github.io preview. -->"
    )


def head(page: dict, base: str, word_w: int, word_h: int, logo_w: int, logo_h: int, og_w: int, og_h: int, always_noindex: bool = False) -> str:
    title = esc(page["title"])
    description = esc(page["description"])
    canonical = ""
    og_url = ""
    if not always_noindex:
        url = ORIGIN + page["path"]
        canonical = f'<link rel="canonical" href="{esc(url)}">'
        og_url = f'<meta property="og:url" content="{esc(url)}">'
    og_image = f"{ORIGIN}/assets/img/catalyx-technologies-og.png"
    ld = json_ld(page, logo_w, logo_h, og_image)
    base_script = ""
    if always_noindex:
        base_script = (
            "<script>"
            "(function(){"
            'var base="/";'
            'if(location.hostname.endsWith(".github.io")){base=' + json.dumps(GITHUB_BASE) + ";}"
            "document.write('<base href=\"'+location.origin+base+'\">');"
            "})();"
            "</script>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
{canonical}
{base_script}
{robots_meta(always_noindex)}
<!-- Search Console / Bing: paste verification meta tags here at cutover. Do not invent tokens. -->
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="theme-color" content="#2A7DB8">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
{og_url}
<meta property="og:type" content="website">
<meta property="og:image" content="{esc(og_image)}">
<meta property="og:image:width" content="{og_w}">
<meta property="og:image:height" content="{og_h}">
<meta property="og:image:alt" content="{esc(OG_ALT)}">
<meta property="og:locale" content="en_US">
<meta property="og:site_name" content="Catalyx Technologies">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{esc(og_image)}">
<meta name="twitter:image:alt" content="{esc(OG_ALT)}">
<link rel="icon" href="{base}favicon.ico" sizes="any">
<link rel="icon" href="{base}assets/img/favicon-32.png" type="image/png" sizes="32x32">
<link rel="icon" href="{base}assets/img/favicon-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="{base}assets/img/apple-touch-icon.png">
<link rel="preload" as="image" href="{base}assets/img/catalyx-technologies-wordmark.webp" type="image/webp">
<link rel="stylesheet" href="{base}assets/css/site.css">
<script type="application/ld+json">{ld}</script>
</head>"""


def render(page: dict, sizes: dict) -> str:
    base = page_base(page["out"])
    fragment = (SRC / "pages" / page["file"]).read_text(encoding="utf-8")
    fragment = fragment.replace("{{BASE}}", base)
    if page.get("products"):
        fragment = fragment.replace("{{TABLE}}", product_table())
        fragment = fragment.replace("{{MODELS}}", product_blocks(base))
    elif "{{TABLE}}" in fragment or "{{MODELS}}" in fragment:
        raise SystemExit(f"Unresolved product token in {page['file']}")
    return (
        head(page, base, sizes["word"][0], sizes["word"][1], sizes["mark"][0], sizes["mark"][1], sizes["og"][0], sizes["og"][1])
        + "<body>\n"
        + header(base, page["nav"], sizes["word"][0], sizes["word"][1])
        + '<main id="main" tabindex="-1">\n'
        + fragment
        + "\n</main>\n"
        + footer(base, sizes["stack"][0], sizes["stack"][1])
        + "\n</body>\n</html>\n"
    )


def render_404(sizes: dict) -> str:
    page = {
        "title": "Page not found | Catalyx Technologies",
        "description": "That address is not on the Catalyx Technologies site. Go to the home page, technology, products, or contact.",
        "path": "/",
        "nav": "",
    }
    base = ""
    body = f"""<section class="page-hero">
  <div class="wrap prose">
    <p class="eyebrow">404</p>
    <h1>This page isn't on the site</h1>
    <p class="lead">The address may have been typed wrong, or the page may have moved.</p>
    <ul class="links-inline">
      <li><a href="{href(base, "")}">Home</a></li>
      <li><a href="{href(base, "technology/")}">Technology</a></li>
      <li><a href="{href(base, "products/")}">Products</a></li>
      <li><a href="{href(base, "contact/")}">Contact</a></li>
      <li><a href="{href(base, "water-research/")}">Water R&amp;D</a></li>
      <li><a href="{href(base, "about/")}">About</a></li>
    </ul>
  </div>
</section>"""
    return (
        head(page, base, sizes["word"][0], sizes["word"][1], sizes["mark"][0], sizes["mark"][1], sizes["og"][0], sizes["og"][1], always_noindex=True)
        + "<body>\n"
        + header(base, "", sizes["word"][0], sizes["word"][1])
        + '<main id="main" tabindex="-1">\n'
        + body
        + "\n</main>\n"
        + footer(base, sizes["stack"][0], sizes["stack"][1])
        + "\n</body>\n</html>\n"
    )


def write_sitemap() -> None:
    urls = []
    for page in PAGES:
        loc = ORIGIN + page["path"]
        block = ["  <url>", f"    <loc>{loc}</loc>", "    <lastmod>2026-11-13</lastmod>"]
        if page["path"] == "/":
            block.append("    <image:image>")
            block.append(f"      <image:loc>{ORIGIN}/assets/img/catalyx-technologies-mark.webp</image:loc>")
            block.append("      <image:title>Catalyx Technologies molecular C logo</image:title>")
            block.append("    </image:image>")
            block.append("    <image:image>")
            block.append(f"      <image:loc>{ORIGIN}/assets/img/catalyx-technologies-wordmark.webp</image:loc>")
            block.append("      <image:title>Catalyx Technologies wordmark</image:title>")
            block.append("    </image:image>")
        block.append("  </url>")
        urls.append("\n".join(block))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (DIST / "sitemap.xml").write_text(xml, encoding="utf-8")


# Named AI crawlers get their own groups so an Allow is explicit even when a
# crawler does not inherit User-agent: *. The wildcard group stays open too.
AI_CRAWLERS = [
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "Meta-ExternalAgent",
    "PerplexityBot",
]


def write_robots() -> None:
    groups = [f"User-agent: {agent}\nAllow: /" for agent in [*AI_CRAWLERS, "*"]]
    text = (
        "# robots.txt for https://catalyxtechnologies.com\n"
        + "\n\n".join(groups)
        + "\n\n"
        + f"Sitemap: {ORIGIN}/sitemap.xml\n"
    )
    (DIST / "robots.txt").write_text(text, encoding="utf-8")


def main() -> None:
    img = SRC / "assets" / "img"
    sizes = {
        "word": png_size(img / "catalyx-technologies-wordmark.png"),
        "stack": png_size(img / "catalyx-technologies-logo-stacked.png"),
        "mark": png_size(img / "catalyx-technologies-mark.png"),
        "og": png_size(img / "catalyx-technologies-og.png"),
    }
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(SRC / "assets", DIST / "assets")
    shutil.copyfile(SRC / "assets" / "favicon.ico", DIST / "favicon.ico")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    for page in PAGES:
        target = DIST / page["out"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(page, sizes), encoding="utf-8")
        print("wrote", page["out"])
    (DIST / "404.html").write_text(render_404(sizes), encoding="utf-8")
    print("wrote 404.html")
    write_sitemap()
    write_robots()
    (DIST / "CNAME").write_text("catalyxtechnologies.com\n", encoding="utf-8")
    state = "ON (noindex,follow)" if PREVIEW_NOINDEX else "OFF (indexable)"
    print(f"previewNoindex is {state}. Canonical host: {ORIGIN}")


if __name__ == "__main__":
    main()

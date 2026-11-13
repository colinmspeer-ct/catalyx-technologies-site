# Catalyx Technologies

Static website for Catalyx Technologies LLC. Plain HTML and CSS, built for GitHub Pages.

The live host is `https://catalyxtechnologies.com`. Canonical tags, `sitemap.xml`, and `robots.txt` use that origin. The build writes `dist/CNAME` with `catalyxtechnologies.com` so GitHub Pages serves the apex domain. `previewNoindex` in `site.config.json` is `false`, so pages are indexable. The 404 page stays `noindex`.

## Build

```bash
python3 build.py
python3 scripts/check_site.py
python3 -m http.server -d dist 8765
```

`build.py` reads `src/pages/` and writes `dist/`. Links are relative to each page, so the same files work at the project preview path and, later, at the apex domain.

Regenerate logos, the favicon, and the Open Graph image with `python3 scripts/make_assets.py` (needs Pillow and the original logo PNGs).

## Indexing

`site.config.json` → `previewNoindex` is `false`. Set it back to `true` and rebuild only if a build must be served from the `github.io` preview without being indexed.

## Contact form

The form in `src/pages/contact.html` (`#hl-form-slot`) posts nowhere. Replace that slot with the HighLevel embed later. Keep the SMS consent checkbox separate, unchecked, and optional, with the consent sentence already on the page. Phone is required only when that box is checked.

The optional marketing-text checkbox is not on the page. Add it only if the 10DLC use case is Mixed.

## Placeholders

Address, phone, and email are not published. The draft values are in HTML comments marked `[CONFIRM]`, in the footer, on Contact, and in the privacy policy and terms. The same is true for the start year of the PCO work, patent numbers, coverage volumes, cut sheets, the water-program focus, the SBIR agency, the principal investigator, leadership bios, and the effective dates.

Water treatment is described as research. It is not a product and has no performance figures.

The air line is written FRESH+™.

## After the domain is live

Ask whoever edits freshplusintl.com to add a visible link to `https://catalyxtechnologies.com` with the anchor text “Catalyx Technologies”. This site already links to `https://freshplusintl.com/` from Products and About.

Search Console and Bing verification tokens are not invented. Paste the meta tags in the head comment that says so, when the tokens exist.

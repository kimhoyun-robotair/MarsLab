# MarsLab website and documentation

This site uses GitHub Pages' built-in **Jekyll**, Markdown and Liquid templates. It has no npm packages, external documentation theme, custom Jekyll plugins or repository-defined deployment workflow.

GitHub renders the Markdown and publishes the resulting static files. People reading the website or running the MarsLab simulator do not need a documentation build environment.

## Publish with GitHub Pages

In the repository's **Settings → Pages → Build and deployment**, select:

- **Source:** Deploy from a branch
- **Branch:** `main`
- **Folder:** `/docs`

Once configured, pushing changes to `main` rebuilds and publishes the site at `https://kimhoyun-robotair.github.io/MarsLab/`. There is no separate manual build or artifact upload. GitHub runs its own Pages build infrastructure; this repository does not supply a workflow file.

Do not add `.nojekyll`: Markdown and Liquid need the built-in Jekyll build. If Pages is already configured for `main` / `docs`, the source selection can stay as it is. Hosting settings have not been changed as part of this local draft.

For a fork, update `url`, `baseurl`, `repository` and `source_branch` in `_config.yml`. Templates and document links use `relative_url` to respect the project path.

## Write or edit documentation

Edit Markdown directly under `guide/`, `robots/`, `reference/` or `development/`. Each page starts with a small header:

```yaml
---
title: Example topic
description: What this page explains.
permalink: /guide/example/
---
```

The shared document layout is selected by directory defaults in `_config.yml`. Add the page's title and URL to `_data/navigation.yml` to include it in the sidebar. Search automatically includes the Markdown pages in these four directories.

Use normal Markdown headings, tables, fenced code blocks and blockquotes. For an internal link, use Jekyll's base-path filter:

```liquid
[Configuration]({{ '/reference/configuration/' | relative_url }})
```

GitHub repository source links use their full `https://github.com/…` URLs. Keep runtime parameters in sync with the profiles and schemas. Separate current `main` capabilities from planned or branch-only work, and distinguish simulation tuning from flight specifications.

## Source layout

| Location | Purpose |
| --- | --- |
| `index.html`, `home.css` | Custom project homepage using HTML and Liquid. |
| `research.html`, `style.css`, `script.js` | Paper, original benchmarks, clips and citation. |
| `guide/` | Installation, first run and troubleshooting. |
| `robots/` | Rover profiles and Ingenuity development status. |
| `reference/` | Configuration, physics, sensing, ROS and model limits. |
| `development/` | Architecture, rover integration and roadmap. |
| `_layouts/doc.html`, `_includes/sidebar.html` | Shared document shell and navigation. |
| `_data/navigation.yml`, `_data/robots.yml` | Navigation groups and homepage robot summaries. |
| `docs.css`, `docs.js` | Document styling, mobile navigation, theme, local table of contents and copy buttons. |
| `search.json`, `search.js`, `search.html` | Jekyll-generated search data and small browser-side search. |
| `asset/`, `demo/`, `MarsLab.pdf` | Existing media, browser demo and paper, at their original paths. |

The search uses plain JavaScript and matches query terms across page titles and text. It has no hosted search service or third-party search library. Documentation remains readable with JavaScript disabled; search and convenience controls require JavaScript.

## Optional local preview

Local preview requires Ruby and Jekyll, but neither is needed to edit Markdown on GitHub or to use the simulator. Match the [GitHub Pages dependency versions](https://pages.github.com/versions/) when checking deployment behavior. The current site was verified with Jekyll 3.10.0, Kramdown 2.4.0 and the GFM parser 1.1.0.

With Ruby and its development headers available, a minimal local setup is:

```sh
gem install --user-install jekyll -v 3.10.0
gem install --user-install kramdown -v 2.4.0
gem install --user-install kramdown-parser-gfm -v 1.1.0
```

Ensure your Ruby user-gem `bin` directory is on `PATH`. Then, from the repository root:

```sh
cd docs
jekyll serve --safe --host 127.0.0.1 --port 4000
```

Open **http://localhost:4000/MarsLab/**. For a one-off build and local link check:

```sh
jekyll build --safe
python3 scripts/check_links.py
```

The Python checker uses only the standard library and is optional. `_site/` is generated output and is ignored by Git. The Markdown, layouts and static assets are the files committed for Pages to build.

## Compatibility and provenance

The URLs `/MarsLab/demo/`, `/MarsLab/asset/…` and `/MarsLab/MarsLab.pdf` remain unchanged. `_config.yml` explicitly includes `demo/vendor` so Jekyll retains the demo's vendored Three.js modules. Keep the [vendor license](demo/vendor/THREE-LICENSE.txt), [demo provenance](demo/DATA.md) and [clip sources](asset/showcase/SOURCES.md).

Old homepage research fragments (`#slam`, `#vpr`, `#citation`, etc.) navigate to the corresponding research section. Configuration documentation is maintained in `reference/`; the former root configuration guide has been removed. Paper results describe the original experimental setup, not new benchmarks for all robot profiles.

The local ignored `techreport/` reports are background material, not build inputs. Robot summaries use checked-in profile values; longer calibration and construction appendices can be curated independently.

# Canadian GRADS — GitHub Pages

Public website: https://canadiangrads.shop/

This repository contains only the public website export. The Rust application source remains in the private `canadian-grads-shop` repository.

`canadian-grads-github-pages.zip` contains the website pages, styles, images, fonts, and PDF downloads. GitHub Actions extracts it into `public/`, then `.github/scripts/configure-domain.py` adapts the page links, assets, canonical URLs, and sitemap for the domain root before deployment. Replacing the ZIP on `main` publishes an updated export automatically. Pages uses GitHub Actions and the custom domain `canadiangrads.shop`, with HTTPS enforcement enabled.

GoDaddy DNS points the apex (`@`) to GitHub Pages addresses `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, and `185.199.111.153`. The `www` CNAME points to `qmclaughlin0.github.io`. The GitHub ownership TXT record must stay in DNS to retain verified ownership.

GitHub Pages cannot run the Rust HTTP server. Newsletter sign-up links to the existing Rust-hosted website at https://canadian-grads-shop.onrender.com/#form-field-email. No newsletter records or server code are included in this repository.

Original content, asset copyrights, stylesheet notices, and website attribution remain in the export. `SOURCE-ATTRIBUTION.md` inside the ZIP records the source.

# Canadian GRADS — GitHub Pages

Public website: https://qmclaughlin0.github.io/canadian-grads-pages/

This repository contains only the public website export. The Rust application source remains in the private `canadian-grads-shop` repository.

`canadian-grads-github-pages.zip` contains the website pages, styles, images, fonts, and PDF downloads. GitHub Actions extracts it into `public/` and deploys that directory to Pages. Replacing the ZIP on `main` publishes an updated export automatically. Pages is configured to use GitHub Actions, with HTTPS enabled.

GitHub Pages cannot run the Rust HTTP server. Newsletter sign-up links to the existing Rust-hosted website at https://canadian-grads-shop.onrender.com/#form-field-email. No newsletter records or server code are included in this repository.

Original content, asset copyrights, stylesheet notices, and website attribution remain in the export. `SOURCE-ATTRIBUTION.md` inside the ZIP records the source.

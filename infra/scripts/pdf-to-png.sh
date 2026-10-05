#!/usr/bin/env bash
# Turn each PDF in a folder into PNG pictures of its pages (needs poppler's
# pdftoppm). Used for the printout screenshots in docs/screenshots/.
#
#   infra/scripts/pdf-to-png.sh docs/screenshots/phase-6
set -euo pipefail
DIR=${1:?usage: pdf-to-png.sh <folder>}
for pdf in "$DIR"/*.pdf; do
  [ -e "$pdf" ] || continue
  pdftoppm -r 110 -png "$pdf" "${pdf%.pdf}-page"
done

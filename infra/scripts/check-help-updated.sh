#!/usr/bin/env bash
# CI check (pull requests): a change people can see in the app must come with
# a matching change to the in-app help (backend/apps/help/articles/), or say
# in the pull request description why the help doesn't need one:
#
#     Help: no change needed (only fixes a crash, nothing on screen changes)
#
# Usage: check-help-updated.sh <base ref>   (PR_BODY in the environment)
set -euo pipefail

base="${1:?usage: check-help-updated.sh <base ref>}"
changed="$(git diff --name-only "${base}...HEAD")"

# What users see and do: screens, menus, and the server rules behind them.
user_facing="$(printf '%s\n' "$changed" | grep -E \
  -e '^frontend/src/(features|app|components/shell)/' \
  -e '^backend/apps/[a-z_]+/(views|serializers|services|permissions|urls|pdf|paper|stock|maintenance|totals)\.py$' \
  -e '^backend/apps/[a-z_]+/migrations/.*flag.*\.py$' \
  | grep -vE '\.test\.tsx?$' | grep -vE '^frontend/src/features/help/' || true)"
help_changed="$(printf '%s\n' "$changed" | grep -E '^backend/apps/help/articles/' || true)"

if [[ -z "$user_facing" ]]; then
  echo "No user-facing changes; help articles don't need updating."
  exit 0
fi
if [[ -n "$help_changed" ]]; then
  echo "Help articles updated:"
  printf '  %s\n' "${help_changed//$'\n'/$'\n'  }"
  exit 0
fi
# The description without <!-- comments --> (the template's example lives in one).
body="$(printf '%s' "${PR_BODY:-}" | perl -0pe 's/<!--.*?-->//gs')"
opt_out="$(printf '%s\n' "$body" \
  | grep -iE '^[[:space:]>*_-]*help:[[:space:]*_]*no change needed[[:space:]*_]*\(.+\)' \
  | grep -viE '\([[:space:]]*reason[[:space:]]*\)' | head -1 || true)"
if [[ -n "$opt_out" ]]; then
  echo "The pull request says the help doesn't need a change:"
  echo "  $opt_out"
  exit 0
fi

cat <<MSG
::error title=Help articles not updated::This pull request changes what people see in the app, but no help article changed.
These files change something users see:
  ${user_facing//$'\n'/$'\n'  }

Update the matching articles in backend/apps/help/articles/ (see docs/HELP_ARTICLES.md),
or, if nothing a user sees or does has changed, add this line to the pull request
description with the reason:

    Help: no change needed (reason)
MSG
exit 1

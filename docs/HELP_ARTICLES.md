# In-app help articles

Signed-in users read these in the app: **Help** in the menu (`/help`), the **?** button at the top of every page (opens the article for that page), and the **Help** group in the global search. They are the users' manual, written for owners, salespeople, mechanics and parts staff, not developers.

The articles live in [`backend/apps/help/articles/`](../backend/apps/help/articles/), one Markdown file per task. The server reads them, checks who may see what, and sends them to the app as plain blocks (never HTML).

## Keeping them accurate (every change)

Any change that alters what a user sees or does updates the help **in the same pull request**:

1. **Find the articles.** Search the articles folder for the screen's route (`pages:`), the button labels you changed, and the feature's flag.
2. **Read the code, not your memory.** Check the exact on-screen labels, the roles the server enforces, the feature flag, confirmations, undo, limits and error messages.
3. **Update the steps, labels and rules.** New page: add it to an article's `pages:` (or write a new article). Removed feature: remove its help. New role rules: update the `::: roles` blocks.
4. **Add search words** people would type for the new feature (`keywords:`).
5. **Run the tests:** `pytest tests/test_help.py` and `npx vitest run src/app/helpCoverage.test.ts`.
6. **Say what changed** under "Help articles" in the pull request description.

If nothing a user sees or does has changed (a refactor, a deploy fix, a test), say so in the pull request description. The **Help docs** check reads it:

```
Help: no change needed (only the deploy script changed)
```

### What enforces this

| Check | Fails when |
|---|---|
| `backend/tests/test_help.py` | An article breaks the format, names an unknown role, section or flag, links to a missing article or heading, or common searches stop finding the right article |
| `frontend/src/app/helpCoverage.test.ts` | A page (route) or menu item has no article listing it under `pages:`, or an article lists or links to a page that doesn't exist |
| **Help docs** workflow (`.github/workflows/help-docs.yml`) | A pull request changes screens, menus or server rules (`frontend/src/features`, `app`, `components/shell`; `backend/apps/*/views.py`, `serializers.py`, `services.py`, `permissions.py`, `urls.py`, `pdf.py` and similar; feature-flag migrations) without changing any article, and its description doesn't say `Help: no change needed (reason)` |
| `CLAUDE.md` | The phase workflow's Docs step includes the help, and each phase ends with a re-read of the articles it touched |

## File format

```markdown
---
title: Work orders
summary: Open a job on a unit, assign a mechanic, log labor, and move it from open to completed.
section: service
roles: admin, service              (optional; everyone if left out)
flag: service                      (optional; hidden while that feature flag is off)
pages: /service, /service/new, /service/:id   (optional; the ? button on these pages opens it)
keywords: new job, open a job, labor, on hold   (optional; other words people search with)
order: 10                          (optional; position in its section)
---
Body text.
```

- **File name** = the article's address: `work-orders.md` → `/help/work-orders`. Lower-case words joined by dashes. Renaming breaks links: search for `help:old-name` first.
- **section**: one of `getting-started`, `customers`, `units`, `service`, `sales`, `parts`, `reports`, `imports`, `admin`, `trouble` (see `SECTIONS` in `backend/apps/help/content.py`).
- **roles**: only these roles see the article at all. Leave it out for everyone.

### Body

| Write | Shows as |
|---|---|
| `## Heading` / `### Smaller heading` | A heading. Search results jump to the matching heading. Every heading in an article must be different |
| A paragraph, lines wrapped freely | A paragraph |
| `- item` / `1. step` (indent continuation lines two spaces) | A list |
| `> Tip: …` / `> Note: …` / `> Warning: …` | A coloured callout |
| `**Save changes**` | Bold: use it for on-screen labels, exactly as written in the app |
| `` `WO-20001` `` | Something to type |
| `[Units](/units)` | A link to an app page |
| `[Change owner](help:change-owner#undo-the-latest-change)` | A link to another article (and heading) |
| `::: roles admin sales` … `:::` | Only those roles see what's inside (removed on the server) |

HTML, images, tables and links outside the app are refused by the tests.

### Role blocks

Use `::: roles` for steps only some roles can take, and say what the others can do instead:

```markdown
::: roles admin sales
## Change the owner
1. Press **Change owner**.
:::

::: roles service parts read_only
Only admin and sales can record a change of owner.
:::
```

Prices (cost, asking and sale price) belong in `::: roles admin sales` blocks. A part's cost belongs in `::: roles admin sales parts`.

## Writing style

- Write for someone in the shop with a tablet: short sentences, plain words, second person ("Press **Save**").
- Start with what it's for, then the steps, then the rules and limits.
- Use the app's exact labels in bold. If a label changes in the code, change it here.
- Say who can do it, what happens after, and how to undo it.
- Don't promise features that aren't built. Don't describe how the code works.
- Add `keywords:` in shop language: "job" for work order, "forklift" or "truck" for unit, "packing slip" for invoice. The search also knows common synonyms (`SYNONYMS` in `backend/apps/help/search.py`). Add to that list when people search with words it doesn't know.

## Search

`/api/v1/help?q=…` ranks the articles the person may read. It works in memory, with no database, and:

- ignores small words ("how do I"),
- folds word endings ("received", "receiving" → "receive"),
- maps shop words to the app's words,
- fixes small typos,
- matches a half-typed last word,
- points at the best-matching heading.

The global search shows the top few under **Help**. Common searches are pinned in `test_finds_what_people_type`. Add one whenever a search should find a new article.

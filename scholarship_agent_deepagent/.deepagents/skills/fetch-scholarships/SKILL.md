---
name: fetch-scholarships
description: Discover all scholarships from the BASE Initiative website via sitemap
---

# Skill: fetch-scholarships

Discover scholarships from the BASE Initiative website.

## Steps

1. Fetch the sitemap using the `web_fetch` tool:
   ```
   web_fetch("https://scholarships.baseinitiativemy.com/sitemap.xml")
   ```

2. Extract all `<loc>` URLs from the XML response.

3. Filter for education-level pages only — keep URLs containing `_postspm` or `_undergraduate`.

4. For each filtered URL call `web_fetch(url)` and extract these fields on one line:
   ```
   name | amount | deadline | eligibility | field | bond
   ```
   Omit any field that is not mentioned on the page.

## Output

Return a compact structured list — one scholarship per line:
```
<name> | <amount> | <deadline> | <eligibility> | <field> | <bond>
```

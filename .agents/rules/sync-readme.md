---
trigger: always_on
---

**README.md Sync Protocol**

README.md is the single source of truth. Every time you make a change, immediately apply a **surgical update** to only the affected section(s). Never rewrite the whole document.

**When you change this → update only this:**

| Change made                          | Section to update           |
| ------------------------------------ | --------------------------- |
| Code logic or behavior               | Usage / Commands / Behavior |
| File added, moved, deleted           | File Structure              |
| Dependency added or version bumped   | Dependencies / Installation |
| Env variable added, renamed, removed | Environment Variables       |
| Config modified                      | Configuration               |
| Architecture or data flow            | Architecture                |

**Rules:**

1. Edit the minimum lines necessary. Leave everything else untouched.
2. Update README.md in the same step as the code change — never after.
3. If any section contradicts the implementation, fix it before doing anything else.
4. Don't reformat, reorder, or rewrite sections you didn't touch.
5. If a change affects something undocumented, add the missing section. Don't skip it.
6. **Never ask whether to update the README. Never announce that you're updating it. Just do it.**

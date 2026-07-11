---
name: search-teachings
description: >-
  Search prior sermons and teachings in this repo via local MiniLM + SQLite
  before drafting, brainstorming, or editing related messages. Use when the
  user is writing a sermon, looking for prior teaching on a theme, scripture,
  series, or tag, or asking what has already been taught on a topic.
---

# Search Teachings

Before drafting or brainstorming a sermon/lesson that overlaps existing themes, run the local search CLI and ground your work in real prior material.

## Command

From the repository root (`Personal/teachings`):

```bash
search/.venv/bin/python -m search query "YOUR QUERY" --top 8
```

If the venv does not exist yet:

```bash
python3 -m venv search/.venv
search/.venv/bin/pip install -r search/requirements.txt
search/.venv/bin/python -m search index
```

Refresh the index after many sermon edits:

```bash
search/.venv/bin/python -m search index
```

Full rebuild:

```bash
search/.venv/bin/python -m search index --rebuild
```

## Filters

```bash
search/.venv/bin/python -m search query "Sabbath rest" --series "Discipleship"
search/.venv/bin/python -m search query "endurance" --tag perseverance
search/.venv/bin/python -m search query "joy set before" --scripture "Hebrews 12"
```

## Rules

1. Run a search when the topic, scripture, or series likely overlaps prior teachings.
2. Cite returned files when reusing themes, illustrations, or teaching points.
3. Do not invent matches — only use hits the CLI returns.
4. Prefer weaving prior teaching forward (continuity) over repeating the same outline.
5. If the index is missing, run `index` once, then query again.
6. When listing results for the user, make every file a markdown link with an absolute workspace path (see `.cursor/rules/search.mdc`). Example: `[Title](/Users/jameslamar/james-obsidian-sync/Personal/teachings/sermons/YYYY-MM-DD-slug.md)`. Do not use code-citation fences or backtick-only paths for result lists.

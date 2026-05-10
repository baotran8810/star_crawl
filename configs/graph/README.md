# Graph configuration

Three lightweight YAML files drive keyword extraction quality.

| File | What it does |
|---|---|
| `glossary.yaml` | Tech terms always kept (exact match, case-insensitive). Add new tools/concepts as the corpus expands. |
| `aliases.yaml` | Map variants to canonical form so "k8s" and "Kubernetes" become one node. |
| `blacklist.yaml` | Generic noise that KeyBERT might rank highly (team, system, …). Always dropped. |

After editing any of these, rebuild:

```bash
star-crawl extract-keywords --rebuild
star-crawl build-graph
```

## Tips

- Keep the glossary tight (~500 terms). Bloat = noise.
- Aliases are case-insensitive on input. The map values must already be canonical (lowercased).
- The blacklist applies AFTER alias resolution.

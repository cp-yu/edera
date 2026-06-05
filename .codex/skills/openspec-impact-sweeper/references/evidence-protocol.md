# Impact Sweeper Evidence Protocol

1. Query OPSX first through the CLI. For each plausible node ID, run:
   ```bash
   openspec opsx query <node-id> --json
   ```
   Use the returned `node`, `relations`, and `codeMap` fields as evidence. If the command reports "OPSX files not found", record that phrase in coverageGaps, add a bootstrap question, and continue with repository search.
2. Map the user term and concept to plausible project terms. Include all plausible mappings in termMappings.
3. For matched OPSX nodes, read node intent, code-map refs, and one-hop relations.
4. Expand to second-hop relations only when the first-hop node is shared infrastructure, crosses domains, or code search shows outward runtime use.
5. When optionalChangeName is provided, read only that change's proposal.md, design.md, tasks.md, specs/**/*.md, and opsx-delta.yaml if present. Do not inspect unrelated active changes.
6. Use git ls-files as the repository search boundary when available. Exclude openspec/changes/archive/**.
7. Perform repo-wide reverse search across tracked files for mapped project terms, exported symbols, workflow names, skill names, command names, configuration keys, template fragment names, and path references.
8. Build the cap->spec mapping through:
   ```bash
   openspec list --specs --json
   ```
   Extract each spec entry's `capabilities` string array. Treat a missing frontmatter mapping as an empty array. Add specs linked to affected caps to mustCheck with the CLI output as evidence.
9. When reading mustCheck specs and the caller provided `concept`, perform the terminology awareness step.
10. Do not rely only on OPSX code-map paths. Classify findings into mustChange, mustCheck, coverageGaps, and questions.
# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | M002 planning | package-architecture | Rename the shared graph-wiki implementation package and import namespace during v1.12. | Rename core to graph-wiki-core and graph_wiki_core | The user decided the former all-in-one graph-wiki-agent package should become an honest library core. With no backward compatibility requirement, renaming both distribution and import namespace avoids preserving old agent-shaped vocabulary in active code. | Yes | human |
| D002 | M002 planning | package-architecture | Split presentation surfaces from shared graph-wiki command implementation. | Separate CLI and MCP packages depending on graph-wiki-core | CLI and MCP are runtime surfaces over shared command logic. Keeping command implementations in core while moving Typer and FastMCP code into focused packages gives clearer dependencies, tests, and ownership. | Yes | collaborative |
| D003 | M002 planning | compatibility-boundary | Do not provide backward-compatible graph_wiki_agent imports or a graph-wiki-agent console-script alias in v1.12. | No shims or old console aliases | The user explicitly said backward compatibility is not a concern. Avoiding shims and aliases makes stale references fail during migration instead of hiding incomplete package-boundary work. | Yes | human |
| D004 | M002 planning | plugin-identity | Do not rename graph-wiki-agent plugin identity in .graph-wiki.yaml or workspace manifests during the package split. | Keep plugin identity as graph-wiki-agent for now | The Python package and CLI names can change without forcing a vault manifest identity migration. Keeping the existing plugin identity avoids expanding this milestone into config compatibility and migration work. | Yes | human |
| D005 | Quick task 2 follow-up | cli-architecture | Long-term code graph CLI surface for graph-wiki | Expose code graph operations as native Typer subcommands under `gw graph ...` with no standalone `cg` or `gwgraph` executable. | The user confirmed graph-wiki-cli is the long-term unified CLI home. A native Typer subapp keeps command parsing, help, packaging, and tests consistent with the rest of `gw` instead of preserving a bolted-on argparse shim. | Yes | collaborative |

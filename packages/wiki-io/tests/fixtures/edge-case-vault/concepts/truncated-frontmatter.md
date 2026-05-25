---
title: Truncated Frontmatter Example
category: concept
summary: This page has an opening frontmatter fence but no closing fence.
tags: [edge-case, frontmatter, testing]
updated: 2026-05-14
tokens: 89

# Truncated Frontmatter Example

This page intentionally has no closing `---` fence after the frontmatter block.
Python-frontmatter and other YAML parsers must handle this gracefully — typically
by treating the entire file as body content with no parsed metadata.

A robust agent or lint tool should report this as a malformed page
(missing required frontmatter fields) rather than crashing with a YAML parse error.

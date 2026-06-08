# Runbook: Freeze mono-repo wiki for eval

**Purpose:** Build, validate, and freeze the mono-repo wiki as a baseline for the three-arm cc-eval evaluation framework.

**Audience:** Developers running the cc-eval three-arm flow.

**Duration:** ~15 minutes (mostly automated steps)

**Prerequisites:** Python 3.11, `uv`, git, bash.

---

## Overview: What freezing means

The mono-repo wiki exists in two states:

1. **Live workspace** (`~/Personal/mono-repo/graph-wiki/`) — actively developed, contains `wiki/`, `.graph-wiki/code.db`, and `raw/` sources.
2. **Frozen baseline** (`~/Personal/graph-wiki/mono-repo-eval-551f7ed8/`) — a tagged git snapshot for reproducible eval runs at a fixed baseline commit (`551f7ed8`).

Freezing means:
- Building and linting the wiki at the pinned source commit.
- Migrating all wikilinks to the current schema (bare slugs → `entities/` + domain pages).
- Authoring missing domain concept pages and gap-fill pages.
- Creating a separate git-controlled artifact with a release tag (`eval-baseline-551f7ed8`).
- Configuring eval runners to use the frozen wiki so all test runs reference the same snapshot.

---

## Prerequisites: State that must be true before freezing

- [ ] **Source repo at commit `551f7ed8`**
  ```bash
  cd ~/Personal/mono-repo
  git fetch origin
  git checkout 551f7ed8
  git log --oneline -1  # should show 551f7ed8
  ```

- [ ] **Live workspace exists and is bootstrapped**
  ```bash
  [ -d ~/Personal/mono-repo/graph-wiki ] && echo "workspace exists" || echo "MISSING"
  [ -d ~/Personal/mono-repo/graph-wiki/wiki ] && echo "wiki exists" || echo "MISSING"
  [ -f ~/Personal/mono-repo/graph-wiki/.graph-wiki/code.db ] && echo "code.db exists" || echo "MISSING"
  ```

- [ ] **Curated pages are present** (concepts, adrs, architecture, sources, work)
  ```bash
  cd ~/Personal/mono-repo/graph-wiki/wiki
  for d in concepts adrs architecture sources work; do
    echo "$d: $(ls $d/*.md 2>/dev/null | grep -v '/index.md$' | wc -l) pages"
  done
  ```

- [ ] **Entity pages are healthy**
  ```bash
  ls ~/Personal/mono-repo/graph-wiki/wiki/entities/*.md | wc -l  # should be ~254
  ```

- [ ] **The `gw` CLI is installed** (from this repo)
  ```bash
  cd /Users/pat/Personal/agent-research && uv sync --quiet
  uv run --package graph-wiki-cli gw --help | head -3  # shows help text
  ```

---

## Step 1: Build wiki at baseline SHA (scan)

The scan command regenerates the graph, entity pages, and backlinks from the source tree at the pinned SHA.

**Why this step:** Ensures the frozen wiki describes the exact code at `551f7ed8`, not a stale snapshot.

### Step 1.1: Run deterministic scan without narration

```bash
cd ~/Personal/mono-repo
uv run --project /Users/pat/Personal/agent-research --package graph-wiki-cli \
  gw scan --workspace ~/Personal/mono-repo/graph-wiki --no-narrate
```

**Expected output:**
- Completes without errors.
- Log mentions: `referenced-in-wiki: N entity page(s)` (N > 0).
- Log mentions: `updated_index` entries for `concepts/`, `sources/`, `work/` folders.
- No Bedrock narrator fan-out (because of `--no-narrate`).

### Step 1.2: Verify entity pages have backlinks

```bash
cd ~/Personal/mono-repo/graph-wiki/wiki
awk '/## Referenced in wiki/{f=1;next} /^## /{f=0} f' entities/pkg_location-domain-ts.md | head
```

**Expected output:**
- Bullet list of curated pages that reference this entity.
- Not: "No wiki pages reference this entity yet."

---

## Step 2: Lint wiki for consistency

Run the lint suite to catch broken links, missing frontmatter, orphans, and format drift.

### Step 2.1: Run lint pass

```bash
cd ~/Personal/mono-repo
uv run --project /Users/pat/Personal/agent-research --package graph-wiki-cli \
  gw wiki lint --workspace ~/Personal/mono-repo/graph-wiki 2>&1 | tee /tmp/mono-wiki-lint.txt
```

### Step 2.2: Review lint output

Read `/tmp/mono-wiki-lint.txt`. Categories of findings:
- **Broken links** → fix typo'd basenames or unresolved slugs
- **Missing frontmatter** → add required keys (e.g. `tokens: 0`)
- **Duplicate titles** → disambiguate page titles
- **Orphans** → acceptable for some pages (log them, don't force-link)
- **Format drift** → match template style

### Step 2.3: Fix findings and re-run lint

For each finding, fix the source page, then re-run Step 2.1. Iterate until lint is clean or only intentional residuals remain.

**Intentional residuals that are acceptable:**
- The 5 demoted external references (now plain text, not links): `location-legacy-py`, `autogen-dev-team-py`, `source-code-tools-py`, `populate-endpoints-and-data-models`, `coding`.
- Genuinely-orphan source pages (pages nothing links to) — log them, don't delete.

### Step 2.4: Log the run

Once clean, append a log entry:

```bash
cd ~/Personal/mono-repo
uv run --project /Users/pat/Personal/agent-research --package graph-wiki-cli \
  gw wiki log --workspace ~/Personal/mono-repo/graph-wiki \
  "migration: 5 external refs demoted to plaintext; lint clean."
```

**Expected:** entry appended to `wiki/log.md`.

---

## Step 3: Freeze wiki (create tagged snapshot)

Create a separate git-controlled directory with the finalized wiki, tagged for repeatable checkouts.

### Step 3.1: Prepare the frozen directory

If the directory doesn't exist yet, create it:

```bash
mkdir -p ~/Personal/graph-wiki/mono-repo-eval-551f7ed8
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8
```

### Step 3.2: Copy the live workspace into the frozen directory

```bash
rsync -av --delete \
  ~/Personal/mono-repo/graph-wiki/ \
  ~/Personal/graph-wiki/mono-repo-eval-551f7ed8/
```

**What this copies:**
- `wiki/` — entity pages, curated pages, index files.
- `.graph-wiki/code.db` — the code graph snapshot.
- `raw/` — ingest sources (specifications, articles).

### Step 3.3: Initialize git and create the baseline tag

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8

# Initialize git if not already done
if [ ! -d .git ]; then
  git init
  git config user.email "psprowls@gmail.com"
  git config user.name "Pat Sprowls"
fi

# Stage all content
git add -A

# Commit
git commit -m "freeze: mono-repo wiki baseline at 551f7ed8 (eval-baseline)" --allow-empty

# Tag the baseline
git tag eval-baseline-551f7ed8 -f
```

**Expected:**
- A commit SHA is created (or reported as empty if content unchanged).
- The tag `eval-baseline-551f7ed8` is created or updated.

### Step 3.4: Verify the frozen snapshot

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8
echo "=== Git status ==="
git log --oneline -1
git tag

echo "=== Content ==="
ls -la wiki/ | head
echo "---"
ls -la .graph-wiki/ | head
echo "---"
ls -la raw/ | head
```

**Expected:**
- Latest commit shown.
- Tag `eval-baseline-551f7ed8` present.
- `wiki/`, `.graph-wiki/`, `raw/` directories visible.

---

## Step 4: Verify frozen wiki (spot-check key pages)

Spot-check the frozen wiki to ensure critical pages exist and contain expected content.

### Step 4.1: Check scenario-critical pages exist

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8/wiki

echo "=== API Client convention ==="
head -5 concepts/shared-api-client.md

echo "=== Design Tokens gap-fill ==="
head -5 concepts/design-tokens.md

echo "=== Example impossible-without-wiki ADR ==="
head -5 adrs/0006-auto-create-activities-from-presence-events.md
```

**Expected:** All three files exist and begin with frontmatter (YAML `---` block).

### Step 4.2: Verify entity backlinks are present

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8/wiki
awk '/## Referenced in wiki/{f=1;next} /^## /{f=0} f' entities/pkg_location-domain-ts.md | wc -l
```

**Expected:** A non-zero count (at least 3–5 references).

### Step 4.3: Verify index files exist

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8/wiki
for d in concepts sources work; do
  [ -f "$d/index.md" ] && echo "$d/index.md: PRESENT" || echo "$d/index.md: MISSING"
done
```

**Expected:** All three index files present.

### Step 4.4: Confirm source paths resolve

```bash
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8
grep -rhoE 'source_path:\s*\S+' wiki/sources/*.md | sed -E 's/source_path:\s*//' | sort -u | while read p; do
  [ -e "$p" ] && echo "OK: $p" || echo "DANGLING: $p"
done
```

**Expected:** All entries show `OK:`, no `DANGLING` lines.

---

## Step 5: Configure eval to use frozen wiki

Update eval configuration to point to the frozen baseline snapshot so all test runs reference the same wiki state.

### Step 5.1: Verify environment variable

The eval system uses the `GRAPH_WIKI_WORKSPACE` env var to locate the wiki. Confirm this is set in your test runner:

```bash
echo "Current GRAPH_WIKI_WORKSPACE:"
echo "${GRAPH_WIKI_WORKSPACE:-(not set)}"
```

If empty, set it:

```bash
export GRAPH_WIKI_WORKSPACE=~/Personal/graph-wiki/mono-repo-eval-551f7ed8
```

### Step 5.2: Check eval step-zero configuration

The eval step-zero spec should reference the frozen wiki. Verify:

```bash
grep -A 5 "frozen-wiki" /Users/pat/Personal/agent-research/docs/superpowers/specs/2026-06-07-cc-eval-wiki-design.md | head -10
```

**Expected:** References `eval-baseline-551f7ed8` tag and the frozen path.

### Step 5.3: Run a quick integration test

```bash
cd /Users/pat/Personal/agent-research
export GRAPH_WIKI_WORKSPACE=~/Personal/graph-wiki/mono-repo-eval-551f7ed8

# This should not error
uv run --package graph-wiki-cli gw wiki lint --workspace "$GRAPH_WIKI_WORKSPACE" 2>&1 | head -20
```

**Expected:** Lint runs successfully against the frozen wiki.

---

## Troubleshooting

### Issue: Lint reports broken links

**Cause:** A curated page references a non-existent entity or concept.

**Fix:**
1. Identify the broken link in the lint output (e.g. `[[some-broken-link]]`).
2. Check if it's a typo: `ls ~/Personal/mono-repo/graph-wiki/wiki/{concepts,entities}/ | grep -i "broken"`.
3. If the target doesn't exist, either:
   - Fix the link to a real target (most likely).
   - Delete the link if it was erroneous (less common).
4. Re-run lint.

### Issue: Entity backlinks are empty or unchanged

**Cause:** The scan didn't regenerate backlinks.

**Fix:**
1. Confirm the scan ran without errors: check the log output from Step 1.1.
2. If backlinks are still placeholder text, re-run Step 1.1 without `--no-narrate` (this will regenerate narratives and may fail on the 3 problematic packages, but will regenerate backlinks).
3. If the 3-package failure occurs, consult the live workspace's `raw/` directory for pre-authored narrative overrides.

### Issue: Source paths dangle

**Cause:** A `source_path:` in a sources page points to a file that doesn't exist.

**Fix:**
1. Identify the dangling path in Step 4.4 output (e.g. `DANGLING: raw/specs/something.md`).
2. Check the live workspace: `ls ~/Personal/mono-repo/graph-wiki/raw/specs/ | grep something`.
3. If missing, copy from the archive: `cp ~/Personal/archive/mono-repo-workspace-backup/raw/specs/something.md ~/Personal/mono-repo/graph-wiki/raw/specs/`.
4. Re-run the rsync in Step 3.2 and re-tag in Step 3.3.

### Issue: The frozen directory is out of sync with the live workspace

**Cause:** The live workspace was updated after the freeze.

**Fix:**
1. Re-run Step 3.2 (rsync) to sync the frozen directory.
2. Re-run Step 3.3 to re-tag (the `-f` flag allows re-tagging).
3. Verify with Step 4.

### Issue: GRAPH_WIKI_WORKSPACE env var not found during eval run

**Cause:** The env var was not exported before running tests.

**Fix:**
1. Export before starting the test runner: `export GRAPH_WIKI_WORKSPACE=~/Personal/graph-wiki/mono-repo-eval-551f7ed8`.
2. Confirm: `echo $GRAPH_WIKI_WORKSPACE`.
3. Re-run the eval.

---

## After Freezing: Do's and Don'ts

### Do's
- ✅ Use the frozen wiki path (`~/Personal/graph-wiki/mono-repo-eval-551f7ed8/`) in all eval runs.
- ✅ Run eval tests against the same frozen baseline to ensure repeatability.
- ✅ Keep the frozen wiki in version control (git tags allow easy checkout).
- ✅ Document changes to the source code or wiki in the wiki log (`wiki/log.md`).
- ✅ Re-freeze if the source code at `551f7ed8` changes (unlikely, but possible for urgent fixes).

### Don'ts
- ❌ Edit the frozen wiki directly. Instead, edit the live workspace and re-freeze.
- ❌ Modify the source repo commit at `551f7ed8`. If urgent changes are needed, create a new tag at a new commit and re-run the build pipeline.
- ❌ Delete the `.graph-wiki/code.db` file. This is the code graph snapshot — losing it requires a full rebuild from source.
- ❌ Run eval tests against the live workspace. Always use the frozen baseline for eval consistency.
- ❌ Commit the frozen wiki's `.graph-wiki/` directory to your main repo. It's a machine-generated artifact and belongs in the frozen workspace repo.

---

## Success Criteria

After following this runbook, you should be able to:

1. [ ] Build a fresh wiki at the pinned SHA with zero lint errors.
2. [ ] Verify that entity backlinks are regenerated and accurate.
3. [ ] Confirm that all scenario-critical pages (api-client, design-tokens, impossible-without-wiki) exist and are grounded.
4. [ ] Create and tag a frozen snapshot that can be checked out by eval tests.
5. [ ] Run lint and integration tests against the frozen wiki without errors.
6. [ ] Set the `GRAPH_WIKI_WORKSPACE` env var and run eval with the frozen baseline.

---

## References

- **Plan:** `/Users/pat/Personal/agent-research/docs/superpowers/plans/2026-06-07-mono-repo-wiki-build.md`
- **Spec:** `/Users/pat/Personal/agent-research/docs/superpowers/specs/2026-06-07-cc-eval-wiki-design.md`
- **Graph Wiki CLI:** `uv run --package graph-wiki-cli gw --help`
- **Live workspace:** `~/Personal/mono-repo/graph-wiki/`
- **Frozen baseline:** `~/Personal/graph-wiki/mono-repo-eval-551f7ed8/`

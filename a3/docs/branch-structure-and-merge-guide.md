# A3 Branch Merge Guide

## Branch Structure

```
main
 └── a3                    ← shared: docs, infra, configs
      ├── a3-p2            ← P2: architecture changes (if applicable)
      ├── a3-p3            ← P3: context window extension
      └── a3-p4            ← P4: final nanochat training
```

> **Note**: Branch names use hyphens (`a3-p3`), not slashes (`a3/p3`), because git cannot create `a3/p3` when `a3` already exists as a branch.

## How to Merge

### 1. Merge feature branches into `a3`

```bash
git checkout a3
git merge a3-p3 --no-ff -m "Merge P3: context window extension"
git merge a3-p2 --no-ff -m "Merge P2: architecture changes"
git merge a3-p4 --no-ff -m "Merge P4: final nanochat training"
```

### 2. Verify

```bash
git log --oneline --graph a3
ls a3/  # should show docs/, shared/, p2/, p3/, p4/
```

### 3. PR to course repo

```bash
gh pr create --base main --head a3 --title "A3: Nanochat Pre-training"
```

## Notes

- Each feature branch only touches its own `p*/` directory + shared docs
- Merge conflicts should be rare — if they occur, they'll be in `a3/docs/` (shared README, interface docs)
- Use `--no-ff` to preserve branch history for the reviewer

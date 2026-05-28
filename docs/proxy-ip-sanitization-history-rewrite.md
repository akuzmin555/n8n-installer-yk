# Proxy IP Sanitization and History Rewrite

Date: 2026-05-28

This note records the repository cleanup performed after real proxy IP addresses were found in documentation and in a tracked local Docker Compose override file.

No real IP addresses are intentionally recorded in this document. Use `YOUR_PROXY_IP` as the placeholder for any private/local proxy address.

## What Changed

- Replaced real proxy IP examples with `YOUR_PROXY_IP` in documentation.
- Added a sanitized Markdown copy of the local override file:
  - `docker-compose.override.example.md`
- Added `docker-compose.override.yml` to `.gitignore`.
- Removed `docker-compose.override.yml` from Git history.
- Kept the local working `docker-compose.override.yml` file on disk as an ignored runtime configuration file.

## Files Updated

- `.gitignore`
- `proxy-guide-enhanced.md`
- `proxy-guide.md`
- `gost-migration-plan.md`
- `docker-compose.override.example.md`

## Local Runtime File

`docker-compose.override.yml` is now intentionally untracked and ignored.

Expected status:

```bash
git status --short --ignored docker-compose.override.yml
```

Expected output:

```text
!! docker-compose.override.yml
```

If the local override file is missing, recreate it from the sanitized example:

```bash
awk '/^```yaml$/ {inside=1; next} /^```$/ && inside {inside=0; next} inside {print}' \
  docker-compose.override.example.md > docker-compose.override.yml

sed -i 's/YOUR_PROXY_IP/<your-real-proxy-ip>/g' docker-compose.override.yml
```

Replace `<your-real-proxy-ip>` locally only. Do not commit the generated `docker-compose.override.yml`.

## Git History Rewrite

The history was rewritten to remove `docker-compose.override.yml` from all local and origin refs.

Commands used:

```bash
git filter-branch --force \
  --index-filter 'git rm --cached --ignore-unmatch docker-compose.override.yml' \
  --prune-empty HEAD

git filter-branch --force \
  --index-filter 'git rm --cached --ignore-unmatch docker-compose.override.yml' \
  --prune-empty --tag-name-filter cat -- --all
```

After rewriting, `refs/original/*` backup refs were deleted and local unreachable objects were pruned:

```bash
git for-each-ref --format='%(refname)' refs/original | xargs -r -n 1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now
```

## Branches Force-Pushed

The following origin branches were force-pushed after rewriting:

- `pomudoro-main`
- `docling-gpu-setup-v2`
- `n8n-queue-mode-fix`
- `ragflow-installation`

Other origin branches were checked and did not contain `docker-compose.override.yml` in their current reachable history after the cleanup.

## Verification Commands

Check that `docker-compose.override.yml` is no longer reachable from any local ref:

```bash
git log --oneline --all -- docker-compose.override.yml
```

Expected output: no output.

Check origin remote-tracking refs:

```bash
git log --oneline --remotes=origin -- docker-compose.override.yml
```

Expected output: no output.

Check current tracked files for the old real proxy IPs by searching for them locally if needed. Do not record those values in committed docs.

Check which files are tracked:

```bash
git ls-files docker-compose.override.yml docker-compose.override.example.md .gitignore
```

Expected output:

```text
.gitignore
docker-compose.override.example.md
```

## Operational Impact

Because `docker-compose.override.yml` is no longer tracked, new clones will not have local proxy routing configured automatically. Operators should create the local file from `docker-compose.override.example.md` and replace `YOUR_PROXY_IP` locally.

Any user who already cloned the old public history may still have the removed file and old commits locally. They should reclone or hard-reset to the rewritten branch state if they need to align with this repository.

GitHub may retain old objects or cached views for some time, and forks/clones outside this repository are not affected by the cleanup.

# Ripple Glasses — Server Infrastructure
 
Summit Innovative's IoT device ("Ripple Glasses") supplements hearing aids by classifying
acoustic environments in real time. This is the infrastructure for the remote Linux server it
talks to: a production environment and a shared development environment, both reachable through
one fixed device URL.
 
**Status as of 2026-09-09: working end-to-end.** The physical device successfully uploads audio
to the dev environment through `https://summit-innovative.duckdns.org/dev/...`, the dev pipeline
processes it, and the live dashboard reflects it. Production has been running the whole time and
was untouched by this rollout.
 
## The short version
 
- **Production**: root-only, always tracks `master` from the `ripple` GitHub repo, lives at
  `/srv/projects/ripple_server/` on the server. Deployed via CI only — no interactive dev access.
- **Dev**: one shared slot, used by one team member at a time. Whoever's turn it is runs
  `sudo dev-claim` to point the dev slot at their own checkout and restart the dev services,
  tests against it, then `sudo dev-release` when done.
- **The device** can't use separate ports or IPs — it only has one base URL. Instead, a URL
  path prefix (`/dev/...` vs. no prefix) tells nginx which backend to route to. Flipping the
  device between prod and dev is separate from and independent of `dev-claim` — the device
  toggle picks prod-vs-dev, `dev-claim` picks *whose* checkout dev currently means.
For anyone new to this, read in this order:
1. This file, for the shape of the system and how to actually use it day to day.
2. `infra/prod-dev-server-architecture.md` — the full design: why it's built this way, every
   service/unit/config file involved, and what's still open.
3. `infra/troubleshooting-log.md` — real bugs hit getting this running, useful if something
   that used to work suddenly doesn't.
## Using the dev environment
 
```bash
ssh your-account@summit-innovative-server
sudo dev-claim      # claims the dev slot for you, restarts the two dev services
```
 
Then flip the physical device to dev mode and test. The dev services keep running the whole
time — no need to re-claim between individual test uploads, only when someone else needs the
slot or your claim goes stale (45 min of inactivity by default).
 
```bash
sudo dev-status      # who currently holds the dev slot, and since when
sudo dev-release      # release it when you're done, so the next person can claim
```
 
To watch your dev session on the live dashboard instead of production's: open the dashboard
with `?env=dev` appended to its URL. It shows a red "Dev Mode" banner so it's never confused
with the real production feed.
 
### One-time setup for a new checkout (each developer, once)
 
```bash
git clone <ripple-repo-url> ~/ripple_server
cd ~/ripple_server/audio-uploader && python3 -m venv venv && venv/bin/pip install -r requirements.txt   # or equivalent
cd ~/ripple_server/environment-classifier && python3 -m venv .venv && .venv/bin/pip install scikit-learn scipy soundfile soxr
```
 
An admin (root) also needs to run the group/ACL setup once per new developer so the dev
services (which run as `www-data`) can read and write into that checkout — see "Dev service
account" in the architecture doc. Skipping this is the most common cause of a
`PermissionError` the first time a new developer claims the dev slot.
 
## What's still open
 
The core system works; what's left is cleanup and rolling out to the rest of the team, not
core design. Full list with detail is in the architecture doc's "Open items" section — the
short version:
 
- Where the `/usr/local/bin/dev-*` scripts' repo checkout lives and who can write to it (a real
  security gap right now — write access there is effectively root access, via the passwordless
  sudo rule that lets any developer run `dev-claim`).
- A couple of remaining `RIPPLE_BASE_DIR`-relative path fixes in the app code.
- Explicit env vars on the two production systemd units (currently relying on defaults that
  happen to be correct).
- Onboarding the rest of the team (repeat the one-time checkout + permission setup above for
  each person).
- Writing down exactly how the device's dev/prod toggle works — it works, just isn't documented
  anywhere yet.
## Key locations
 
| What | Where |
|---|---|
| Production code + data | `/srv/projects/ripple_server/` |
| Dev symlink (repoints on claim) | `/srv/projects/ripple_dev/current` |
| Dev claim lock file | `/srv/projects/ripple_dev/active.json` |
| Claim scripts | `/usr/local/bin/dev-claim`, `dev-release`, `dev-status` |
| Nginx endpoints snippet | `/etc/nginx/snippets/summit-endpoints.conf` (symlinked from the `ripple` repo) |
| Nginx site config (certbot-managed) | `/etc/nginx/sites-available/summit-innovative.conf` |
| Prod audio-uploader | port 8000, `ripple-audio-uploader.service` |
| Dev audio-uploader | port 8080, `audio-uploader-dev.service` |
| Prod/dev environment classifier | no port, `environment-realtime-watcher-{prod,dev}.service` |

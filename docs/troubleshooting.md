# Dev Environment: Bugs Hit and Fixed (Sep 2026 rollout)
 
A running log of the real bugs found while bringing the dev environment (see
`infra/prod-dev-server-architecture.md`) up on the actual server, in the order they were found.
Kept separate from the design doc because most of these are general gotchas worth remembering
even outside this specific project — the kind of thing that'll bite again on a different server.
 
## 1. `dev-claim` assumed the wrong checkout directory name
 
`CHECKOUT_DIR="$USER_HOME/ripple"` was baked into the script from an early, unconfirmed guess.
The real checkout directory is `~/ripple_server`, matching production's actual folder name.
Fixed by changing the script's `CHECKOUT_DIR` to `"$USER_HOME/ripple_server"`.
 
**Lesson:** don't let an assumed path made early in a design conversation go unverified once
real deployment starts — confirm folder names against what's actually on the server before
baking them into scripts.
 
## 2. Venv location for `realtime_watcher` — two wrong guesses before the real answer
 
First guess: the venv lived at the repo root (`ripple_server/.venv/`). Wrong. The real,
confirmed production `ExecStart` was:
```
/srv/projects/ripple_server/environment-classifier/.venv/bin/python -m scripts.realtime_watcher
```
So the venv is nested inside its own code subfolder (`environment-classifier/.venv/`), the same
pattern `audio-uploader` uses (`audio-uploader/venv/`) — just with a different venv folder name
(`.venv` vs `venv`).
 
This also surfaced a naming ambiguity: `environment-classifier/` (code + venv) and
`environment-uploader/` (data-only: `training-uploads/`, `realtime-uploads/`) are two separate
sibling folders, not the same thing under two names — confirmed directly with the user rather
than guessed a third time.
 
**Lesson:** when in doubt about a path, ask for the actual `ExecStart`/config line rather than
inferring structure from code that references directory names indirectly (e.g. via a config
class). The real line settled it immediately once we had it.
 
## 3. `pipefail`/shebang: `sudo dev-claim` → `set: Illegal option -o pipefail`
 
Caused by `#!/usr/bin/env bash` resolving unpredictably under `sudo`'s restricted
`secure_path` — likely landing on `dash`/`sh` instead of `bash`, which doesn't support
`set -o pipefail`. Fix: hardcode the shebang as `#!/bin/bash` instead of relying on `env` to
find `bash`. Confirmed fixed.
 
**Lesson:** for any script invoked via `sudo` (especially with a passwordless NOPASSWD rule),
hardcode the shebang. `env`-based shebangs depend on `$PATH`, and `sudo` deliberately restricts
`$PATH` for security reasons.
 
## 4. `ln -sfn` silently nested a symlink instead of replacing a pre-existing directory
 
`dev-claim` runs `ln -sfn "$CHECKOUT_DIR" "$RIPPLE_DEV_LINK"` to point
`/srv/projects/ripple_dev/current` at whichever developer's checkout is claimed. This only
replaces `LINKNAME` (`current`) if `LINKNAME` is already a symlink (or doesn't exist yet). If
`LINKNAME` is a *real directory* — which `/srv/projects/ripple_dev/current` apparently was,
likely created by hand before `dev-claim` was ever run against it — `ln -sfn` doesn't replace
it. Instead it silently creates the symlink *inside* that directory, using the target's
basename: `current/ripple_server -> /home/samfry/ripple_server`.
 
This produced a confusing string of downstream symptoms: `audio-uploader-dev.service` crashed
with `PermissionError` trying to create
`/srv/projects/ripple_dev/current/ripple_server/audio-uploader/realtime-uploads` (the doubled
`ripple_server` segment), while `environment-realtime-watcher-dev.service` happened to work
because someone had already (unknowingly) compensated for the bug by adding a matching
`/ripple_server` segment into *its* unit's `ExecStart`/`RIPPLE_BASE_DIR` — so two units disagreed
about the correct path, and both were "right" relative to the broken symlink structure they'd
each separately adapted to.
 
Fix: confirm with `ls -ld /srv/projects/ripple_dev/current` whether it's a symlink (`l...`, with
a `->` target) or a real directory (`d...`). If it's a real directory, remove the nested symlink
and the directory, then re-run `dev-claim` so it creates `current` as a proper top-level symlink:
```bash
sudo rm /srv/projects/ripple_dev/current/ripple_server
sudo rmdir /srv/projects/ripple_dev/current
sudo dev-claim
```
Then make sure every unit that references `current` uses it consistently (no unit should have a
`/ripple_server` segment after `current` — `current` already *is* the checkout root).
 
**Lesson:** `ln -sfn TARGET LINKNAME` is not a reliable "replace this symlink" idiom if there's
any chance `LINKNAME` could exist as a real directory instead of a symlink. Worth a
pre-flight check (`[ -L "$LINKNAME" ] || [ ! -e "$LINKNAME" ]`) in the script itself before
relying on `ln -sfn` to do the right thing — not yet added to `dev-claim`.
 
## 5. `www-data` permission denied writing into a developer's checkout
 
`audio-uploader-dev.service` crashed with `PermissionError` writing an uploaded file, even after
the symlink bug (#4) was fixed and the path was correct. Root cause: the `chgrp`/`chmod`/`setfacl`
setup described in "Dev service account" (project doc) had only ever been done against the
placeholder `alice` example, never against the real developer's home directory (`samfry`).
Fixed by running the full block — `chgrp -R ripple-dev`, `chmod -R g+rwX`, `find ... chmod g+s`,
and critically `setfacl -m u:www-data:x /home/samfry` for traversal into the home directory
itself — against the real path, then restarting the dev services so `www-data` picked up its
new group membership.
 
**Lesson:** a POSIX ACL like the `setfacl` traversal fix is easy to document once and then
forget to actually apply per-user. If a future teammate hits `PermissionError` after everything
else checks out, this is the first thing to check — and it's easy to verify with
`getfacl /home/<user> | grep www-data`.
 
## 6. nginx `proxy_pass` missing the trailing path — the original 404
 
The very first symptom reported (`/dev/realtime/1.wav` → `404 {"detail":"Not Found"}`) turned
out to be the last bug found, and the most subtle. The deployed nginx snippet had:
```nginx
location /dev/realtime/ {
    proxy_pass http://127.0.0.1:8080;   # <- no path after the port
    ...
}
```
In nginx, whether `proxy_pass` includes a URI after the host:port changes its behavior
completely:
- **With** a URI (`proxy_pass http://127.0.0.1:8080/realtime/;`) — nginx replaces the matched
  `location` prefix with that URI before forwarding, i.e. it strips `/dev` off.
- **Without** one (`proxy_pass http://127.0.0.1:8080;`) — nginx forwards the original request
  URI completely unchanged, `/dev` and all.
So `/dev/realtime/1.wav` was reaching the dev `audio-uploader` app as literally
`/dev/realtime/1.wav`, but the app's route is `/realtime/{filename}` — no `/dev`. No route
matched, hence FastAPI's own 404 (a real, JSON, `{"detail":"Not Found"}` response — which is
what actually made this diagnosable as an app-level 404 and not an nginx-level one; nginx's own
404 page is HTML, not JSON). The prod blocks (`/realtime/` → port 8000) happened to work despite
the same missing trailing path, purely because their location prefix and the app's real route
are identical strings — there was nothing to strip, so the bug was invisible there.
 
Fixed by adding the trailing path back to every `/dev/...` block:
```nginx
location /dev/realtime/ {
    proxy_pass http://127.0.0.1:8080/realtime/;
    ...
}
```
(and the same for `/dev/training/` and `/dev/realtime/ws/results`). Confirmed working via
`curl` through the public URL, then via the actual microcontroller.
 
**Lesson:** a `proxy_pass` with a bare `host:port` and no trailing path/slash is a completely
different rewrite rule from one with a trailing path — not a stylistic choice. When a
`location` prefix doesn't exactly match the backend's real route (which is the whole point of
the `/dev` prefix design here), the trailing path on `proxy_pass` is load-bearing. Worth a
`curl` test against every `/dev/...` route whenever this snippet is touched, since a config that
"looks right" and passes `nginx -t` can still be silently wrong in a way that only shows up as a
confusing 404 from the *application*, not from nginx.
 
## Diagnostic techniques that helped
 
- **`{"detail":"Not Found"}` vs. nginx's own HTML 404** — the response *shape* tells you whether
  the request reached the backend app at all. Learned to check this before assuming "not
  exposed" (nginx-level) vs. "no matching route" (app-level).
- **Testing the backend directly on its port** (`curl http://127.0.0.1:8080/...`), bypassing
  nginx entirely, isolates app bugs from nginx bugs. This is what surfaced bug #5 (permissions)
  cleanly, separate from bug #6 (nginx), even though both were blocking the same end-to-end
  request.
- **`sudo journalctl -u <service> -n 50 --no-pager`** for the actual Python traceback —
  `systemctl status`'s own output is too truncated to diagnose anything past "it crashed."
  Every bug from #4 onward was actually confirmed from a traceback, not guessed from symptoms
  alone.
- **`ls -ld` vs. `ls -la` on a suspected symlink** — `ls -la <path>` on a symlink-to-a-directory
  lists the *target's contents*, which can be misread as "a file named X exists here" when X is
  actually one level deeper than you think. `ls -ld <path>` shows the entry itself (symlink or
  real directory, and its target if a symlink) without following it — use `-d` first when a
  path's own nature (real dir vs. symlink) is in question.

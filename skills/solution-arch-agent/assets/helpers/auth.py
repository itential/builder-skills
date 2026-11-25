#!/usr/bin/env python3
"""Get an Itential Platform token from a .env file without showing the agent any secret.

Reads the credentials in <dir>/.env, exchanges them for a token, and writes the token to
<dir>/.auth.json (mode 600). Prints one status line. It never prints a password, client
secret or token, so the agent running it never has them in its context.

    python3 auth.py <use-case-dir>            reuse a still-valid token, otherwise get a new one
    python3 auth.py <use-case-dir> --force    always get a new token (after a 401/403)
    python3 auth.py <dir> --env PATH --out PATH   read/write other locations

.env keys:
    PLATFORM_URL                      required
    CLIENT_ID + CLIENT_SECRET         OAuth client credentials  -> Authorization: Bearer <token>
    USERNAME + PASSWORD               local /login               -> Cookie: token=<token>
    AUTH_METHOD=oauth|local           optional; picked from the keys present when missing

.auth.json gets platform_url, auth_method, token (also as access_token, for older readers),
header (the name and value prefix to send it with) and expires_at.

Exit codes: 0 ok, 1 authentication failed, 2 bad input (.env missing or incomplete).
Standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REUSE_MARGIN = 120  # seconds: a token that expires sooner than this is treated as expired
LOCAL_TTL = 3600    # /login doesn't say when its token expires; assume an hour


def read_env(path):
    values = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key] = value
    return values


def fail(code, message, secrets=()):
    for s in secrets:
        if s:
            message = message.replace(s, "<redacted>")
    print(f"error: {message}")
    sys.exit(code)


def post(url, data, content_type):
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": content_type})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def main():
    ap = argparse.ArgumentParser(description="Get an Itential Platform token without showing any secret.")
    ap.add_argument("dir", help="use-case folder holding .env (and where .auth.json is written)")
    ap.add_argument("--env", help="path to the .env file (default: <dir>/.env)")
    ap.add_argument("--out", help="path to write the token file (default: <dir>/.auth.json)")
    ap.add_argument("--force", action="store_true", help="get a new token even if the saved one is still valid")
    args = ap.parse_args()

    env_path = args.env or os.path.join(args.dir, ".env")
    out_path = args.out or os.path.join(args.dir, ".auth.json")
    if not os.path.isfile(env_path):
        fail(2, f"{env_path} not found. Ask the engineer to create it (see environments/*.env for the keys).")
    env = read_env(env_path)

    base = env.get("PLATFORM_URL", "").rstrip("/")
    if not base:
        fail(2, f"PLATFORM_URL is missing from {env_path}")
    method = env.get("AUTH_METHOD", "").lower()
    if method in ("password", "login"):
        method = "local"
    if not method:
        method = "oauth" if env.get("CLIENT_ID") else "local" if env.get("USERNAME") else ""
    secrets = [env.get("CLIENT_SECRET", ""), env.get("PASSWORD", "")]
    if method == "oauth" and not (env.get("CLIENT_ID") and env.get("CLIENT_SECRET")):
        fail(2, f"AUTH_METHOD is oauth but CLIENT_ID or CLIENT_SECRET is missing from {env_path}")
    if method == "local" and not (env.get("USERNAME") and env.get("PASSWORD")):
        fail(2, f"AUTH_METHOD is local but USERNAME or PASSWORD is missing from {env_path}")
    if method not in ("oauth", "local"):
        fail(2, f"can't tell the auth method: set CLIENT_ID + CLIENT_SECRET, or USERNAME + PASSWORD, in {env_path}")

    if not args.force and os.path.isfile(out_path):
        try:
            saved = json.load(open(out_path))
            if (saved.get("platform_url", "").rstrip("/") == base and saved.get("auth_method") == method
                    and saved.get("token") and saved.get("expires_at", 0) - time.time() > REUSE_MARGIN):
                left = int(saved["expires_at"] - time.time())
                print(f"ok: {method} token for {base} still valid ({left}s left) in {out_path}")
                return
        except (ValueError, OSError):
            pass  # unreadable file: get a new token

    try:
        if method == "oauth":
            body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": env["CLIENT_ID"],
                                           "client_secret": env["CLIENT_SECRET"]}).encode()
            resp = json.loads(post(f"{base}/oauth/token", body, "application/x-www-form-urlencoded"))
            token, ttl = resp.get("access_token"), int(resp.get("expires_in") or 3600)
            header = "Authorization: Bearer"
        else:
            body = json.dumps({"username": env["USERNAME"], "password": env["PASSWORD"]}).encode()
            raw = post(f"{base}/login", body, "application/json").strip()
            try:
                parsed = json.loads(raw)
                token = parsed if isinstance(parsed, str) else parsed.get("token")
            except ValueError:
                token = raw
            ttl, header = LOCAL_TTL, "Cookie: token="
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200].replace("\n", " ")
        fail(1, f"{method} login to {base} returned HTTP {e.code}: {detail}", secrets)
    except (urllib.error.URLError, OSError, ValueError) as e:
        fail(1, f"{method} login to {base} failed: {e}", secrets)
    if not token:
        fail(1, f"{method} login to {base} returned no token", secrets)

    record = {"platform_url": base, "auth_method": method, "token": token, "access_token": token,
              "header": header, "expires_at": int(time.time()) + ttl}
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(record, f, indent=2)
    os.chmod(out_path, 0o600)
    print(f"ok: new {method} token for {base} saved to {out_path} (expires in {ttl}s)")


if __name__ == "__main__":
    main()

"""The Surgeon server client - the chunk protocol (`upload_begin - upload_chunk - upload_finish`), the session
cookie kept in a jar, the 60-second single-use hand-off link. Lifted from `tools/surgeon_cli.py` `_remote` /
`_remote_upload` / `_remote_claim` (HANDOFF-1, V7.14) with two changes: errors RAISE `ClientError` instead of
`sys.exit`, so a caller decides; nothing here imports the server package."""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


class ClientError(Exception):
    """A refusal in words - the caller prints it and exits nonzero."""


NEXT_ACTION = {   # THIN-1 step 4b (V7.58): every HTTP refusal names the next action, after the server's own words
    401: "next: the session is gone (30 idle minutes, a server restart, or a stale session cache) - run the command again; a new session is minted.",
    403: "next: the key was refused for this - check the key (`surgeon doctor` shows its tier); surgery and jobs need Practitioner (/pricing); verification never needs a key.",
    404: "next: the name is not on the table - check it against the Nodes & Layers panel or `surgeon report`.",
    409: "next: nothing to do - the job already finished; post a new one.",
    413: "next: the file is over this tier's ceiling stated above - use a smaller checkpoint, .safetensors for the larger ceiling, or Practitioner.",
    422: "next: the recipe or job body is not what the server reads - re-export the recipe from a current session.",
    429: "next: rate limited - wait a minute and retry (per-account and per-IP buckets).",
}


def _session_cache_path(host):
    """The session cookie kept between runs, per server host, so a dropped upload resumes (the server's
    `upload_begin` returns the chunks it already holds for the same filename and size IN THE SAME SESSION)."""
    d = os.path.join(os.path.expanduser("~"), ".falconsai-surgeon")
    return os.path.join(d, "session-" + "".join(c if c.isalnum() else "_" for c in host) + ".txt")


class Remote:
    def __init__(self, server, key=None, timeout=600, opener=None, verbose=False, session_cache=True):
        self.base = server.rstrip("/")
        self.key = key
        self.timeout = timeout
        self.verbose = verbose
        self.host = urllib.parse.urlsplit(self.base).netloc
        self.cache = _session_cache_path(self.host) if session_cache else None
        self.jar = http.cookiejar.LWPCookieJar(self.cache) if self.cache else http.cookiejar.CookieJar()
        if self.cache and os.path.isfile(self.cache):
            try:
                self.jar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass   # an unreadable cache is a fresh session, never an error
        host, base = self.host, self.base

        class _SameHost(urllib.request.HTTPRedirectHandler):
            # SA-031 (V7.14 D51 sweep): urllib re-sends every header on a redirect, the key included.
            # A redirect that leaves the host the user named is refused, in words.
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if urllib.parse.urlsplit(newurl).netloc != host:
                    raise ClientError(f"{base} redirected to another host ({urllib.parse.urlsplit(newurl).netloc}) - "
                                      f"the key is not sent there. Name that host with --server if it is yours.")
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        self.opener = opener or urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), _SameHost())

    def call(self, path, body=None, raw=None, query=""):
        url = self.base + path + (("?" + query) if query else "")
        if raw is not None:
            req = urllib.request.Request(url, data=raw, method="POST", headers={"Content-Type": "application/octet-stream"})
        else:
            req = urllib.request.Request(url, data=json.dumps(body or {}).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        if self.key:
            req.add_header("X-Surgeon-Key", self.key)
        if self.verbose:
            print(f"-> {req.get_method()} {url} ({len(req.data) if req.data else 0} bytes)", file=sys.stderr)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                data = r.read()
                if self.verbose:
                    print(f"<- {r.status} {path} ({len(data)} bytes)", file=sys.stderr)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode()).get("detail", "")
            except Exception:
                pass
            if self.verbose:
                print(f"<- {e.code} {path}", file=sys.stderr)
            hint = NEXT_ACTION.get(e.code, "next: the server refused this; its words above say why." if e.code < 500 else
                                   "next: the server failed (5xx) - `surgeon doctor` reads its health; if it is up, retry once, then report it.")
            raise ClientError(f"HTTP {e.code} from {path} - {detail or e.reason}\n{hint}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, ClientError):
                raise e.reason
            raise ClientError(f"could not reach {self.base} - {e.reason}\nnext: is the server up and the address right? `surgeon doctor --server {self.base}`; behind a proxy, name the host the proxy serves.")
        finally:
            self._save()
        try:
            out = json.loads(data.decode("utf-8", "replace") or "{}")
        except ValueError:
            # SA-032 (D11): an edge page or a non-Surgeon server - say so, never a traceback
            raise ClientError(f"{self.base}{path} did not answer JSON (an edge or proxy page?) - first bytes: {data[:80]!r}")
        if not isinstance(out, dict):
            raise ClientError(f"{self.base}{path} answered JSON that is not an object - is this a Surgeon server?")
        return out

    def _save(self):
        if not self.cache:
            return
        try:
            os.makedirs(os.path.dirname(self.cache), exist_ok=True)
            self.jar.save(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass   # a cache that cannot be written only costs the resume

    def get(self, path):
        """A GET with the same jar, key and refusals (THIN-1 step 4b: `doctor`)."""
        url = self.base + path
        req = urllib.request.Request(url, method="GET")
        if self.key:
            req.add_header("X-Surgeon-Key", self.key)
        if self.verbose:
            print(f"-> GET {url}", file=sys.stderr)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            raise ClientError(f"HTTP {e.code} from {path} - {e.reason}\n" + NEXT_ACTION.get(e.code, "next: the server refused this."))
        except urllib.error.URLError as e:
            if isinstance(e.reason, ClientError):
                raise e.reason
            raise ClientError(f"could not reach {self.base} - {e.reason}\nnext: is the server up and the address right?")
        finally:
            self._save()
        try:
            out = json.loads(data.decode("utf-8", "replace") or "{}")
        except ValueError:
            raise ClientError(f"{self.base}{path} did not answer JSON (an edge or proxy page?) - first bytes: {data[:80]!r}")
        return out if isinstance(out, dict) else {}

    def upload(self, path, purpose="model", on_progress=None):
        """Drive the chunk protocol for `path`; returns the state the server drew (what the browser gets from
        upload_finish). Resumable for free: upload_begin lists the chunks the server already holds."""
        if not os.path.isfile(path):
            raise ClientError(f"{path}: no such file (the V7.53 field run traced here; a missing checkpoint is a refusal in words).")
        size = os.path.getsize(path)
        if size <= 0:
            raise ClientError("empty file.")
        begin = self.call("/api/upload_begin", {"filename": os.path.basename(path), "size": size, "purpose": purpose})
        try:
            uid, chunk, n = begin["upload_id"], int(begin["chunk_size"]), int(begin["n_chunks"])
        except (KeyError, TypeError, ValueError):
            raise ClientError(f"upload_begin answered without upload_id/chunk_size/n_chunks - is this a Surgeon server? got {str(begin)[:120]}")
        have = set(begin.get("received") or [])
        if have and self.verbose:
            print(f"resuming: the server already holds {len(have)} of {n} chunk(s) of {os.path.basename(path)}", file=sys.stderr)
        with open(path, "rb") as f:
            for i in range(n):
                if i in have:
                    continue
                f.seek(i * chunk)
                self.call("/api/upload_chunk", raw=f.read(chunk), query=f"upload_id={uid}&index={i}&purpose={purpose}")
                if on_progress:
                    on_progress(i + 1, n)
        return self.call("/api/upload_finish", {"upload_id": uid, "purpose": purpose})

    def claim(self):
        """Mint the 60-second, single-use hand-off link for the session the jar holds -> (url, ttl)."""
        c = self.call("/api/session_claim")
        if not str(c.get("url", "")).startswith("/#claim="):
            raise ClientError(f"session_claim answered without a hand-off url - got {str(c)[:120]}")
        return self.base + c["url"], int(c.get("expires_in", 60))

    def recipe(self, text):
        """THIN-1 step 4: the server reads the recipe (YAML or JSON) against its contract - `/api/recipe_parse` - so
        the client needs no YAML parser. Returns {source_model, ops, count}."""
        return self.call("/api/recipe_parse", raw=text.encode("utf-8"))

    def job(self, ops, kind="replay"):
        """THIN-1 step 4: post a job to the session the jar holds and return its record (the job runs inside the
        request in this version: state done, `done` applied, `refused` in the server's words)."""
        return self.call("/api/jobs", {"kind": kind, "ops": ops})

"""`surgeon` - the thin command line (THIN-1 step 2, V7.53; step 4, V7.57).
ASCII ONLY in this package: on Windows a piped stdout is cp1252 and a non-ASCII character in help or a refusal
raises UnicodeEncodeError - the V7.53 bake read exactly that traceback on `surgeon --help`.
Step 4b (V7.58): the session is kept between runs per server (~/.falconsai-surgeon/) so a dropped upload resumes;
`doctor`; a next action on every refusal; `--verbose`; exit codes 0 / 1 / 2.
Step 4: `replay`, `fleet`, `report`, `excise`, `merge` ride the server - a checkpoint is uploaded into a session
(the chunk protocol), the recipe is read by the server (/api/recipe_parse), the job is posted (/api/jobs) and its
record printed. `compare`, `quantize`, `fold` refuse in words until the server runs them as job kinds."""
import argparse
import os
import sys

from . import __version__
from .client import ClientError, Remote

NOT_YET = ("compare", "quantize", "fold")
REFUSAL = ("`surgeon {cmd}` is not a job kind the server runs yet (the job API runs excise, reparent and merge, THIN-1 "
           "step 3). Today `{cmd}` runs from a copy of the repository: `python tools/surgeon_cli.py {cmd} ...`. "
           "`surgeon replay`, `fleet`, `report`, `excise`, `merge`, `upload --open` and `verify` work from this client now.")
CHECKPOINT_EXT = (".safetensors", ".pt", ".pth", ".bin", ".ckpt")


def _upload(r, path):
    st = r.upload(path, on_progress=lambda i, n: print(f"  chunk {i}/{n}", file=sys.stderr))
    label = ((st.get("vitals") or {}).get("architecture") or {}).get("label") or st.get("filename")
    print(f"loaded on {r.base}: {st.get('filename')} - {label}")
    return st


def _open(r):
    url, ttl = r.claim()
    print(f"open within {ttl} s (single use): {url}")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def _print_job(job, name=None):
    ok = job.get("state") == "done" and not job.get("refused")
    head = f"{'OK ' if ok else 'REFUSED'} {name}: " if name else f"job {job.get('id')}: "
    print(f"{head}{job.get('done')} of {job.get('total')} op(s) applied" + (f" - job {job.get('id')}" if name else ""))
    for line in job.get("refused") or []:
        print(f"    refused: {line}")
    return ok


def main(argv=None):
    # V7.54: a piped Windows stdout is cp1252 and strict; the verifier prints check marks and dashes. Never let an
    # encoding raise out of the client - replace what the console cannot show.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="surgeon", description=f"FALCONS.AI Model Surgeon thin client {__version__}",
                                 epilog="exit codes: 0 clean - 1 one or more ops refused by the server - 2 the client refused (its message says why and what next)")
    ap.add_argument("--verbose", action="store_true", help="print every request and its status to stderr")
    ap.add_argument("--no-session-cache", action="store_true", help="do not keep the session between runs (a dropped upload cannot resume)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("doctor", help="check the server, the version and this key's tier, in words")
    p.add_argument("--server", required=True); p.add_argument("--key", default=None)
    p = sub.add_parser("upload", help="load a checkpoint into a browser session on the server (the chunk protocol)")
    p.add_argument("path"); p.add_argument("--server", required=True); p.add_argument("--key", default=None)
    p.add_argument("--open", action="store_true", help="mint the 60-second single-use hand-off link and open it")
    p = sub.add_parser("verify", help="verify a Surgeon package offline (free, Apache-2.0 verifier)")
    p.add_argument("package"); p.add_argument("--key", default=None)
    for c_ in ("replay", "fleet"):
        p = sub.add_parser(c_, help="replay a recipe on one checkpoint (fleet: on every checkpoint in a folder) through the job API")
        p.add_argument("recipe"); p.add_argument("target", help="a checkpoint file (fleet: a folder of them)")
        p.add_argument("--server", required=True); p.add_argument("--key", default=None)
        p.add_argument("--open", action="store_true", help="after the job, mint the hand-off link and open the edited table")
    p = sub.add_parser("report", help="upload a checkpoint and print what the server read (vitals)")
    p.add_argument("path"); p.add_argument("--server", required=True); p.add_argument("--key", default=None)
    p = sub.add_parser("excise", help="one excise on a checkpoint, as a one-op job")
    p.add_argument("path"); p.add_argument("node"); p.add_argument("--server", required=True); p.add_argument("--key", default=None)
    p.add_argument("--open", action="store_true")
    p = sub.add_parser("merge", help="one merge on a checkpoint (the donor must be on the table), as a one-op job")
    p.add_argument("path"); p.add_argument("name"); p.add_argument("--server", required=True); p.add_argument("--key", default=None)
    p.add_argument("--method", default="lerp"); p.add_argument("--alpha", type=float, default=0.5); p.add_argument("--open", action="store_true")
    for c_ in NOT_YET:
        sub.add_parser(c_, help="refuses in words until the server runs it as a job kind").add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd in NOT_YET:
        print(REFUSAL.format(cmd=a.cmd), file=sys.stderr); return 2
    if a.cmd == "verify":
        from . import verify as _v
        sys.argv = ["verify_attestation.py", a.package] + (["--key", a.key] if a.key else [])
        return _v.main()
    try:
        r = Remote(a.server, a.key, verbose=a.verbose, session_cache=not a.no_session_cache)
        if a.cmd == "doctor":
            h = r.get("/api/health")
            print(f"server      : {r.base} - {h.get('status')} - version {h.get('version')}")
            m = r.get("/api/meta")
            tier = m.get("tier")
            print(f"key         : {'none given' if not a.key else ('recognised' if m.get('signed_in') else 'NOT recognised')} - tier {tier}")
            print(f"client      : {__version__}" + ("" if str(h.get("version")) == __version__ else f" - the server runs {h.get('version')}: install the wheel that ships with it"))
            print(f"session     : {'a model is on the table - ' + str((m.get('session') or {}).get('filename')) if m.get('session') else 'empty'}")
            if a.key and not m.get("signed_in"):
                print("next        : the key is not recognised by this server - check it, or get one from the account page.")
            elif tier == "free":
                print("next        : a free key can verify and upload; surgery through jobs needs Practitioner (/pricing).")
            else:
                print("next        : nothing - upload, replay, fleet, report, excise and merge will run.")
            return 0
        if a.cmd in ("upload", "report"):
            st = _upload(r, a.path)
            if a.cmd == "report":
                v = st.get("vitals") or {}
                print(f"architecture: {(v.get('architecture') or {}).get('label')}")
                for k in ("params", "modules", "tensors", "size_bytes", "format"):      # the server's own vitals keys (tools/state_fixture.py)
                    if k in v:
                        print(f"{k:<12}: {v[k]}")
            elif a.open:
                _open(r)
            return 0
        if a.cmd in ("replay", "fleet"):
            rec = r.recipe(open(a.recipe, encoding="utf-8").read())
            ops = rec.get("ops") or []
            if a.cmd == "replay":
                targets = [a.target]
            else:
                if not os.path.isdir(a.target):
                    raise ClientError(f"{a.target}: not a folder.")
                targets = sorted(os.path.join(a.target, f) for f in os.listdir(a.target) if f.endswith(CHECKPOINT_EXT))
                if not targets:
                    raise ClientError(f"{a.target}: no checkpoint files ({' '.join(CHECKPOINT_EXT)}) to replay on.")
            clean = 0
            for t in targets:
                _upload(r, t)
                clean += 1 if _print_job(r.job(ops), os.path.basename(t)) else 0
            if a.cmd == "replay" and a.open:
                _open(r)
            print(f"{clean} of {len(targets)} checkpoint(s) clean")
            return 0 if clean == len(targets) else 1
        _upload(r, a.path)
        op = {"op": "excise", "node": a.node} if a.cmd == "excise" else {"op": "merge", "name": a.name, "method": a.method, "alpha": a.alpha}
        ok = _print_job(r.job([op]))
        if a.open:
            _open(r)
        return 0 if ok else 1
    except ClientError as e:
        print(str(e), file=sys.stderr); return 2
    except OSError as e:
        print(f"{e.filename or ''}: {e.strerror or e}\nnext: check the path; `surgeon --help` shows the argument order.", file=sys.stderr); return 2


if __name__ == "__main__":
    sys.exit(main())

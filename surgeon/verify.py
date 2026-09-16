#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 FALCONS.AI. Licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations.
# This file — the free verifier — is the open-source component of Model
# Surgeon (T3-a, operator-ruled Apache-2.0, 2026-08-31). The product itself
# is proprietary; see LICENSE-verifier and NOTICE in the package.
"""
FALCONS.AI Model Surgeon — FREE attestation verifier.

Anyone can verify a Surgeon package without a subscription:

    python verify_attestation.py package.zip [--key HEXKEY-OR-STRING]

Checks, in order:
  1. the package carries a lineage.intoto.jsonl attestation;
  2. every subject artifact's SHA-256 matches the signed digest;
  3. the DSSE HMAC signature verifies under the given key
     (--key or FALCONSAI_HMAC_KEY; defaults to the public demo key).

Exit codes: 0 VERIFIED · 1 TAMPERED/INCOMPLETE · 2 not a Surgeon package.
Verification is free by design: signed creation is the paid act, universal
verification is what makes the signature worth anything.
"""
VERIFIER_VERSION = "2"   # D-4 (V6.98): chain-aware
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import zipfile

# SEC-7: this script used to default to a shipped secret — which meant the
# signing key travelled inside every exported package. Anyone holding a
# package could mint forgeries that verified. No default now: the verifier
# requires the key out of band, exactly like any other shared secret.
DEFAULT_KEY = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--key", default=os.environ.get("FALCONSAI_HMAC_KEY"))
    ap.add_argument("--bind", nargs="?", const="https://surgeon.falcons.ai", default=None,
                    help="D-2: fetch the publisher's published fingerprint document from this host and say WHO signed "
                         "(bound · retired · unbound). Off by default: the verifier is offline unless you ask.")
    a = ap.parse_args()
    try:
        z = zipfile.ZipFile(a.package)
    except Exception as e:
        print(f"✖ cannot open {a.package}: {e}")
        sys.exit(2)
    names = z.namelist()
    # v6.51 container fix (UPSTREAM_NOTE): some Windows tools zip with
    # backslash separators — normalize member names so those packages
    # verify instead of reading "not a Surgeon package".
    canon = {n.replace("\\", "/"): n for n in names}
    names = list(canon)
    prefix = ""
    roots = {n.split("/", 1)[0] for n in names if n.strip("/")}
    if len(roots) == 1 and all("/" in n for n in names if n.strip("/")):
        prefix = next(iter(roots)) + "/"   # Explorer-style re-zip: descend

    def _zread(nm):
        return z.read(canon.get(prefix + nm, prefix + nm))
    try:
        att = json.loads(_zread("lineage.intoto.jsonl"))
    except KeyError:
        print("✖ no lineage.intoto.jsonl — not a Surgeon package "
              "(or the attestation was stripped).")
        sys.exit(2)
    payload = base64.b64decode(att.get("payload", ""))
    want = (att.get("signatures") or [{}])[0].get("sig", "")
    # SEC-1: asymmetric first — the package carries the publisher's PUBLIC
    # key, so verification needs no secret and forgery needs the private
    # key. Free verification, restored properly.
    env_missing = False
    sig_uncheckable = False
    sig_entry = (att.get("signatures") or [{}])[0] or {}
    scheme = sig_entry.get("scheme") or "hmac"
    if scheme == "ed25519" and sig_entry.get("publicKey"):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey)
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(sig_entry["publicKey"])).verify(
                    bytes.fromhex(want), payload)
            have = want
            print(f"signature   : ed25519 OK · publisher {sig_entry.get('keyid')}")
            if a.bind:
                # D-2 (V7.20): one fetch, only because you asked — the publisher's own document
                import json as _j2, urllib.request as _ur
                try:
                    with _ur.urlopen(a.bind.rstrip("/") + "/.well-known/falconsai-publisher.json", timeout=10) as _r:
                        _doc = _j2.loads(_r.read().decode("utf-8"))
                    _fpr = str(sig_entry.get("keyid") or "").replace("ed25519:", "").lower()
                    if _doc.get("current") and _fpr == str(_doc["current"]).lower():
                        print(f"publisher   : {_doc.get('publisher', '?')} (bound — the current key)")
                    else:
                        _ret = next((r for r in _doc.get("retired") or [] if _fpr == str(r.get("fingerprint", "")).lower()), None)
                        if _ret:
                            print(f"publisher   : {_doc.get('publisher', '?')} — retired key, signed before {_ret.get('retired')} ({_ret.get('reason', 'retired')})")
                        else:
                            print("publisher   : unbound — not this publisher's key; pin the fingerprint yourself")
                except Exception as _e:                                       # noqa: BLE001
                    print(f"publisher   : could not fetch {a.bind} ({_e.__class__.__name__}) — pin the fingerprint yourself")
            else:
                print("              (pin this fingerprint to establish WHO signed it, "
                      "or run again with --bind to check the publisher's published fingerprint)")
        except ImportError:
            # A missing library is an ENVIRONMENT problem, not evidence of
            # tampering — say so, keep checking digests, verdict INCOMPLETE.
            have = None
            env_missing = True
            print("signature   : cannot check — install the 'cryptography' "
                  "package (pip install cryptography) to verify ed25519")
        except Exception as e:
            have = None
            print(f"signature   : ed25519 INVALID ({e})")
    elif a.key:
        have = hmac.new(a.key.encode(), payload, hashlib.sha256).hexdigest()
        print("signature   : legacy shared-key (hmac) — anyone with the "
              "key could have produced this package")
    else:
        have = None
        sig_uncheckable = True
        print("signature   : legacy shared-key package; supply --key or "
              "FALCONSAI_HMAC_KEY to check it (digests still verified)")
    sig_ok = have is not None and hmac.compare_digest(want, have)
    stmt = json.loads(payload)
    print(f"verifier    : {VERIFIER_VERSION}")
    print(f"attestation : {stmt.get('predicateType')}")
    print(f"tool        : {(stmt.get('predicate') or {}).get('tool')}")
    all_ok = True
    for sub in stmt.get("subject", []):
        nm, digest = sub["name"], sub["digest"]["sha256"]
        try:
            actual = hashlib.sha256(_zread(nm)).hexdigest()
            ok = actual == digest
        except KeyError:
            actual, ok = "<missing from zip>", False
        except Exception:
            # e.g. the archive's own CRC rejects the entry — the byte-flip
            # case. Corruption is tampering evidence, not a crash.
            actual, ok = "<unreadable — fails the archive's own checksum>", False
        all_ok &= ok
        print(f"  {'✔' if ok else '✖'} {nm}")
        if not ok:
            print(f"      signed  {digest}\n      actual  {actual}")
    print(f"signature   : {'✔ valid under this key' if sig_ok else '✖ does NOT verify under this key'}")
    # D-4 (V6.98, VERIFIER 2): the lineage CHAIN. A prior attestation, when the
    # package carries one, is checked for payload integrity and — when it was
    # signed by THIS package's key — for signature. A prior that cannot be
    # verified here is reported AMBER; it never makes this package TAMPERED.
    chain = (stmt.get("predicate") or {}).get("chain")
    if chain:
        depth = chain.get("depth")
        pr = chain.get("prior")
        if not pr:
            print(f"chain       : depth {depth} · no prior attestation reachable at load")
        else:
            try:
                p_env = pr.get("envelope") or {}
                p_payload = base64.b64decode(p_env.get("payload", ""))
                p_digest = hashlib.sha256(p_payload).hexdigest()
                p_sig = (p_env.get("signatures") or [{}])[0]
                intact = p_digest == pr.get("digest")
                same_key = bool(sig_entry.get("publicKey")) and p_sig.get("keyid") == sig_entry.get("keyid")
                p_ok = None
                if intact and same_key and p_sig.get("scheme") == "ed25519" and p_sig.get("sig"):
                    try:
                        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as _PK
                        _PK.from_public_bytes(bytes.fromhex(sig_entry["publicKey"])).verify(
                            bytes.fromhex(p_sig["sig"]), p_payload)
                        p_ok = True
                    except Exception:
                        p_ok = False
                state = ("prior VERIFIED (same publisher key)" if p_ok else
                         "prior INVALID under this key — AMBER" if p_ok is False else
                         "prior intact · signed by another key — not verified here (AMBER)" if intact else
                         "prior payload does not match its recorded digest — AMBER")
                print(f"chain       : depth {depth} · {state} · prior keyid {str(p_sig.get('keyid') or '?')[:20]} · {len(pr.get('operations') or [])} earlier operation(s)")
            except Exception as e:
                print(f"chain       : depth {depth} · prior present but unreadable ({e}) — AMBER")
    merges = (stmt.get("predicate") or {}).get("merges") or []
    if merges:
        print(f"merges      : {len(merges)} recorded "
              f"({', '.join(sorted({m.get('method','lerp') for m in merges}))})")
    verdict = "VERIFIED" if sig_ok and all_ok and stmt.get("subject") \
        else "INCOMPLETE" if ((env_missing or sig_uncheckable) and all_ok) \
        else "TAMPERED" if stmt.get("subject") else "INCOMPLETE"
    print(f"\nVERDICT: {verdict}")
    sys.exit(0 if verdict == "VERIFIED" else 1)


if __name__ == "__main__":
    main()

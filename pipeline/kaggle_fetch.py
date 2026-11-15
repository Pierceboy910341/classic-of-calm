"""Download Kaggle notebook outputs and (private) datasets with plain HTTPS — standard library only.

    python -m pipeline.kaggle_fetch kernel-output piercezheng910341/classic-of-calm-01-generate weekly/W/candidates_raw
    python -m pipeline.kaggle_fetch dataset piercezheng910341/classic-of-calm-suno /tmp/suno_dl
    python -m pipeline.kaggle_fetch dataset-files piercezheng910341/classic-of-calm-suno   # list only

Why not the ``kaggle`` CLI: in Claude's cloud environment the Kaggle credential is injected by the
HTTPS proxy, and the CLI refuses to start without a local token. So this helper sends NO
Authorization header; the proxy adds it for api.kaggle.com. On a machine with a real key
(e.g. the VPS) set ``KAGGLE_API_TOKEN`` (Bearer) or ``KAGGLE_USERNAME``+``KAGGLE_KEY`` (Basic)
and it is used instead. Never print or store the key.

Endpoints (from the kagglesdk source, kagglesdk 0.1.38; checked 2026-11-15):
* POST https://api.kaggle.com/v1/kernels.KernelsApiService/ListKernelSessionOutput
       {"userName","kernelSlug","pageToken"?} -> {"files":[{"fileName","url"}],"log","nextPageToken"}
       file urls (www.kaggleusercontent.com) are signed: fetched WITHOUT auth.
* POST https://api.kaggle.com/v1/datasets.DatasetApiService/ListDatasetFiles
       {"ownerSlug","datasetSlug","datasetVersionNumber"?,"pageToken"?}
       -> {"datasetFiles":[{"name","totalBytes",...}],"nextPageToken"}
* POST https://api.kaggle.com/v1/datasets.DatasetApiService/DownloadDataset
       {"ownerSlug","datasetSlug","fileName"?,"datasetVersionNumber"?} -> 302 to a signed
       storage.googleapis.com URL (fetched WITHOUT auth). Single files may arrive zipped
       ("<name>.zip"); whole datasets always do. Both are unpacked automatically.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.kaggle.com/v1"
UA = "classic-of-calm-fetch/1.0"


class FetchError(RuntimeError):
    pass


def _auth_headers() -> dict:
    tok = os.environ.get("KAGGLE_API_TOKEN")
    if tok:
        return {"Authorization": f"Bearer {tok.strip()}"}
    u, k = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    if u and k:
        return {"Authorization": "Basic " + base64.b64encode(f"{u}:{k}".encode()).decode()}
    return {}  # proxy injects it


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _open(req, follow=True, timeout=300):
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    return opener.open(req, timeout=timeout)


def rpc(service: str, method: str, body: dict, follow: bool = True, retries: int = 3):
    """POST an RPC. Returns parsed JSON, or (for a redirect when follow=False) {'_redirect': url}."""
    url = f"{API}/{service}/{method}"
    data = json.dumps(body).encode()
    last = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": UA,
                                              **_auth_headers()})
        try:
            with _open(req, follow=follow, timeout=120) as r:
                raw = r.read()
            return json.loads(raw.decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and not follow:
                return {"_redirect": e.headers.get("Location")}
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (400, 401, 403, 404):
                raise FetchError(f"{method} HTTP {e.code}: {msg}") from e
            last = f"HTTP {e.code}: {msg}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = str(e)
        time.sleep(2 * attempt)
    raise FetchError(f"{method} failed: {last}")


def download_url(url: str, dest: Path, retries: int = 3) -> Path:
    """GET a signed URL without auth, streaming to disk (atomic rename)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as fh:
                shutil.copyfileobj(r, fh, 1 << 20)
            os.replace(tmp, dest)
            return dest
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(3 * attempt)
    raise FetchError(f"download failed for {dest.name}: {last}")


def _split(ref: str) -> tuple[str, str]:
    ref = ref.strip().rstrip("/")
    for pre in ("https://www.kaggle.com/", "https://kaggle.com/", "code/", "datasets/"):
        if ref.startswith(pre):
            ref = ref[len(pre):]
    parts = [p for p in ref.split("/") if p and p not in ("code", "datasets")]
    if len(parts) < 2:
        raise SystemExit(f"expected <user>/<slug>, got {ref!r}")
    return parts[-2], parts[-1]


def _want(name: str, patterns: list[str] | None) -> bool:
    return not patterns or any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(Path(name).name, p) for p in patterns)


def kernel_output(ref: str, dest: str | Path, patterns: list[str] | None = None, skip_existing: bool = True) -> list[Path]:
    user, slug = _split(ref)
    dest = Path(dest)
    files, token, log_text = [], None, None
    while True:
        body = {"userName": user, "kernelSlug": slug}
        if token:
            body["pageToken"] = token
        r = rpc("kernels.KernelsApiService", "ListKernelSessionOutput", body)
        files += r.get("files") or []
        log_text = log_text or r.get("log")
        token = r.get("nextPageToken")
        if not token:
            break
    out = []
    for f in files:
        name = (f.get("fileName") or "").lstrip("/")
        if not name or not f.get("url") or not _want(name, patterns):
            continue
        p = dest / name
        if not (skip_existing and p.exists()):
            download_url(f["url"], p)
        out.append(p)
    if log_text:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "_kernel_log.json").write_text(log_text if isinstance(log_text, str) else json.dumps(log_text),
                                               encoding="utf-8")
    return out


def dataset_files(ref: str, version: int | None = None) -> list[dict]:
    owner, slug = _split(ref)
    out, token = [], None
    while True:
        body = {"ownerSlug": owner, "datasetSlug": slug}
        if version:
            body["datasetVersionNumber"] = int(version)
        if token:
            body["pageToken"] = token
        try:
            r = rpc("datasets.DatasetApiService", "ListDatasetFiles", body)
        except FetchError as e:
            if "403" in str(e) or "404" in str(e):
                raise FetchError(f"{e}\n  -> dataset {owner}/{slug} does not exist yet, or the Kaggle "
                                 "credential in this environment belongs to another account") from e
            raise
        if r.get("errorMessage"):
            raise FetchError(r["errorMessage"])
        out += r.get("datasetFiles") or []
        token = r.get("nextPageToken")
        if not token:
            return out


def _unpack_if_zip(path: Path, want_name: str | None, dest_dir: Path) -> list[Path]:
    if not zipfile.is_zipfile(path) or (want_name and want_name.lower().endswith(".zip")):
        return [path]
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        for n in names:
            target = (dest_dir / n).resolve()
            if dest_dir.resolve() not in target.parents and target != dest_dir.resolve():
                raise FetchError(f"unsafe path in zip: {n}")
        z.extractall(dest_dir)
    path.unlink()
    return [dest_dir / n for n in names]


def dataset_download(ref: str, dest: str | Path, patterns: list[str] | None = None,
                     version: int | None = None, skip_existing: bool = True) -> list[Path]:
    """Download each dataset file (filtered by glob ``patterns``) into ``dest``."""
    owner, slug = _split(ref)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for f in dataset_files(ref, version):
        name = f.get("name") or ""
        if not name or not _want(name, patterns):
            continue
        p = dest / name
        if skip_existing and p.exists():
            out.append(p)
            continue
        body = {"ownerSlug": owner, "datasetSlug": slug, "fileName": name}
        if version:
            body["datasetVersionNumber"] = int(version)
        r = rpc("datasets.DatasetApiService", "DownloadDataset", body, follow=False)
        url = r.get("_redirect") or r.get("url")
        if not url:
            raise FetchError(f"no download URL for {name}: {str(r)[:200]}")
        with tempfile.TemporaryDirectory(dir=dest) as td:
            got = download_url(url, Path(td) / (Path(name).name + ".download"))
            files = _unpack_if_zip(got, name, Path(td) / "unz")
            if files == [got]:
                p.parent.mkdir(parents=True, exist_ok=True)
                os.replace(got, p)
                out.append(p)
            else:
                for g in files:
                    rel = g.relative_to(Path(td) / "unz")
                    tgt = dest / (Path(name).parent / rel.name if len(files) == 1 else rel)
                    tgt.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(g, tgt)
                    out.append(tgt)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.kaggle_fetch", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kernel-output", help="download a notebook's latest output")
    k.add_argument("ref", help="<user>/<kernel-slug>")
    k.add_argument("dest")
    k.add_argument("--only", nargs="*", help='glob filter, e.g. "candidates/*"')
    d = sub.add_parser("dataset", help="download a (private) dataset's files")
    d.add_argument("ref", help="<owner>/<dataset-slug>")
    d.add_argument("dest")
    d.add_argument("--only", nargs="*", help='glob filter, e.g. "*.mp3" "*.wav"')
    d.add_argument("--version", type=int)
    ls = sub.add_parser("dataset-files", help="list a dataset's files")
    ls.add_argument("ref")
    ls.add_argument("--version", type=int)
    for p in (k, d):
        p.add_argument("--force", action="store_true", help="re-download files that already exist")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "kernel-output":
            files = kernel_output(a.ref, a.dest, a.only, not a.force)
        elif a.cmd == "dataset":
            files = dataset_download(a.ref, a.dest, a.only, a.version, not a.force)
        else:
            for f in dataset_files(a.ref, a.version):
                print(f"{f.get('totalBytes', 0):>12}  {f.get('creationDate', '')[:19]}  {f.get('name')}")
            return 0
    except FetchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"{len(files)} files -> {a.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

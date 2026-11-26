#!/usr/bin/env python3
"""Cache public NASA PDS ChemCam source products, with byte-level provenance."""
from __future__ import annotations
import concurrent.futures
import argparse
import datetime as dt
import hashlib
import html as html_parser
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
BASE = 'https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/'
MANIFEST = ROOT / 'source_manifest.json'

def set_workdir(folder: Path):
    """Keep downloaded files and generated products in the selected work folder."""
    global ROOT, RAW, MANIFEST
    ROOT = folder.resolve()
    RAW = ROOT / 'raw'
    MANIFEST = ROOT / 'source_manifest.json'
    RAW.mkdir(parents=True, exist_ok=True)

def moc_inventory(html: str) -> dict[str, str]:
    """Read only paired MOC products in the official directory listing."""
    directory = BASE + 'data/moc/'
    expected = urllib.parse.urlparse(directory)
    inventory = {}
    for href in re.findall(r'''href\s*=\s*['"]([^'"]+)['"]''', html, re.I):
        url = urllib.parse.urljoin(directory, html_parser.unescape(href))
        parsed = urllib.parse.urlparse(url)
        name = parsed.path.rsplit('/', 1)[-1]
        if not re.fullmatch(r'moc_\d+_\d+\.(csv|lbl)', name):
            continue
        if (parsed.scheme, parsed.netloc, parsed.path.rsplit('/', 1)[0] + '/') != (expected.scheme, expected.netloc, expected.path):
            raise ValueError('Unexpected MOC product location: ' + url)
        if name in inventory and inventory[name] != url:
            raise ValueError('Conflicting MOC directory entry: ' + name)
        inventory[name] = url
    csv_names = {name[:-4] for name in inventory if name.endswith('.csv')}
    label_names = {name[:-4] for name in inventory if name.endswith('.lbl')}
    if not csv_names or csv_names != label_names:
        raise ValueError('MOC directory must contain nonempty matching CSV/label pairs')
    return dict(sorted(inventory.items()))

def fetch(url: str, name: str | None = None, refresh: bool = False) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    name = name or urllib.parse.urlparse(url).path.rstrip('/').split('/')[-1]
    dest = RAW / name
    sidecar = dest.with_name(dest.name + '.source.json')
    previous = None
    if dest.exists() and sidecar.exists():
        meta = json.loads(sidecar.read_text())
        if meta.get('url') == url and hashlib.sha256(dest.read_bytes()).hexdigest() == meta['sha256']:
            previous = meta
            if not refresh:
                return meta
    for attempt in range(3):
        try:
            headers = {'User-Agent': 'MarsLIBSResearchExplorer/1.0'}
            if refresh and previous:
                if previous.get('etag'):
                    headers['If-None-Match'] = previous['etag']
                if previous.get('last_modified'):
                    headers['If-Modified-Since'] = previous['last_modified']
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as response:
                content = response.read()
                meta = {'url': url, 'resolved_url': response.geturl(), 'local_file': str(dest.relative_to(ROOT)),
                        'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content),
                        'retrieved_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                        'last_modified': response.headers.get('Last-Modified'),
                        'etag': response.headers.get('ETag'), 'content_type': response.headers.get('Content-Type')}
            temporary = dest.with_name(dest.name + '.part')
            temporary.write_bytes(content)
            temporary.replace(dest)
            sidecar.write_text(json.dumps(meta, indent=2))
            return meta
        except urllib.error.HTTPError as e:
            if e.code == 304 and previous:
                previous['last_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
                sidecar.write_text(json.dumps(previous, indent=2))
                return previous
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError('Unreachable')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path(__file__).resolve().parent,
                        help='Source cache and output directory (default: this script directory).')
    parser.add_argument('--refresh', action='store_true', help='Check the remote directory and source products for updates using HTTP conditional requests.')
    parser.add_argument('--workers', type=int, default=6, help='Concurrent public downloads (default: 6).')
    args = parser.parse_args()
    set_workdir(args.workdir)
    index = fetch(BASE + 'data/moc/', 'moc_directory.html', refresh=args.refresh)
    html = (ROOT / index['local_file']).read_text()
    inventory = moc_inventory(html)
    tasks = [(url, name) for name, url in inventory.items()]
    tasks.extend((BASE + p, None) for p in ['document/msl_ccam_obs.csv', 'document/msl_ccam_obs.lbl',
                 'document/release_notes.txt', 'catalog/ccam_libs_rdr_ds.cat', 'calib/calinfo.txt'])
    results = [index]
    failures = []
    print(f'Fetching {len(tasks)} PDS products', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 12))) as ex:
        pending = {ex.submit(fetch, url, name, args.refresh): url for url, name in tasks}
        for n, future in enumerate(concurrent.futures.as_completed(pending), 1):
            try:
                results.append(future.result())
            except Exception as e:
                failures.append({'url': pending[future], 'error': str(e)})
            if n % 10 == 0 or n == len(tasks):
                print(f'{n}/{len(tasks)} completed; {len(failures)} failed', flush=True)
    MANIFEST.write_text(json.dumps({'sources': sorted(results, key=lambda x: x['url']),
                                    'moc_inventory': inventory, 'failures': failures}, indent=2))
    print(json.dumps({'source_count': len(results), 'failures': failures}, indent=2))
    if failures:
        raise SystemExit('Source acquisition failed; no new dataset may be accepted.')

if __name__ == '__main__':
    main()

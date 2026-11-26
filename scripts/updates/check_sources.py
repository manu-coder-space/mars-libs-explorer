#!/usr/bin/env python3
"""Check public Mars sources without mutating published datasets.

Usage: python scripts/updates/check_sources.py --cache /tmp/mars-check \
  --baseline-state /path/to/previous-state.json --output /path/to/check.json

The baseline may be a state object or a previous full report. Successful remote
states are returned under ``state``; unavailable sources retain their previous
successful state. NASA bytes are ALWAYS compared to the published source hashes,
not merely the preceding check, so an unpublished change remains pending. The
caller must retain the old published site on essential errors and validate a
staged rebuild before publishing. Exit 2 means an essential check failed; optional
outages produce status partial and exit 0. No credentials or private data used.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html.parser
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('source_watch.json')
MAX_BYTES = 96 * 1024 * 1024
USER_AGENT = 'Mars-LIBS-Explorer/3.0 public-source-update-check'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(path)


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            for key, value in attrs:
                if key.lower() == 'href' and value:
                    self.links.append(value)


def directory_urls(body, url, pattern):
    parser = Links()
    parser.feed(body.decode('utf-8-sig', errors='strict'))
    base = urllib.parse.urlsplit(url)
    result = set()
    for value in parser.links:
        candidate = urllib.parse.urljoin(url, value)
        parsed = urllib.parse.urlsplit(candidate)
        if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
            continue
        if not parsed.path.startswith(base.path):
            continue
        tail = parsed.path[len(base.path):]
        if re.fullmatch(pattern, tail, flags=re.I):
            result.add(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', '')))
    if not result:
        raise ValueError('Archive directory returned no expected product links; refusing an empty inventory')
    return sorted(result)


def metadata(headers):
    return {k: v for k, v in {
        'etag': headers.get('ETag'), 'last_modified': headers.get('Last-Modified'),
        'content_type': headers.get('Content-Type'), 'content_length': headers.get('Content-Length'),
    }.items() if v is not None}


def request(url, previous=None, *, head=False, timeout=40):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Only HTTPS public sources are supported')
    headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'}
    # A prior successful fingerprint is required before reusing a 304 response.
    if previous and previous.get('fingerprint') and not head:
        if previous.get('etag'):
            headers['If-None-Match'] = previous['etag']
        elif previous.get('last_modified'):
            headers['If-Modified-Since'] = previous['last_modified']
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=headers, method='HEAD' if head else 'GET')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if urllib.parse.urlsplit(response.url).scheme != 'https':
                    raise ValueError('Refusing a redirect to an unencrypted source')
                info = metadata(response.headers)
                info['resolved_url'] = response.url
                if head:
                    return None, info, False
                declared = response.headers.get('Content-Length')
                if declared and int(declared) > MAX_BYTES:
                    raise ValueError(f'Source exceeds monitoring download limit: {declared} bytes')
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError('Source exceeds monitoring download limit')
                if declared and len(body) != int(declared):
                    raise ValueError('Incomplete response body')
                if not body:
                    raise ValueError('Unexpected empty source response')
                return body, info, False
        except urllib.error.HTTPError as error:
            if error.code == 304 and previous and previous.get('fingerprint'):
                return None, metadata(error.headers), True
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt:
                raise
        time.sleep(1 + attempt)
    raise RuntimeError('No response from source')


def zenodo_projection(doc):
    if not doc.get('id') or not isinstance(doc.get('files'), list) or not doc['files']:
        raise ValueError('Unexpected Zenodo record schema')
    files = sorted(({'key': f['key'], 'checksum': f['checksum'], 'size': f['size']} for f in doc['files']), key=lambda f: f['key'])
    if not all(f['checksum'].startswith(('md5:', 'sha256:')) and f['size'] > 0 for f in files):
        raise ValueError('Zenodo file checksum/size is missing')
    return {'id': str(doc['id']), 'files': files}


def semantic(spec, body, headers):
    kind = spec['kind']
    if kind == 'head':
        value = {k: headers[k] for k in ('etag', 'last_modified', 'content_length') if k in headers}
        if not ('etag' in value or 'last_modified' in value):
            raise ValueError('Object metadata has no stable validator')
        return value
    # Byte-comparison source hashes ignore local build timestamps by design.
    if kind == 'sha256':
        if body.lstrip()[:20].lower().startswith((b'<!doctype html', b'<html')):
            raise ValueError('Expected an archive data/label file, received HTML')
        return None
    if kind == 'moc_inventory':
        urls = directory_urls(body, spec['url'], r'moc_\d{4}_\d{4}\.(?:csv|lbl)')
        csvs = {u.rsplit('.', 1)[0] for u in urls if u.lower().endswith('.csv')}
        labels = {u.rsplit('.', 1)[0] for u in urls if u.lower().endswith('.lbl')}
        if not csvs or csvs != labels:
            raise ValueError('ChemCam MOC directory has unmatched CSV/label products')
        return urls
    if kind == 'sol_inventory':
        return directory_urls(body, spec['url'], r'sol_\d{5}/')
    if kind == 'text':
        return '\n'.join(line.rstrip() for line in body.decode('utf-8-sig').replace('\r\n', '\n').splitlines()).strip()
    doc = json.loads(body)
    if kind == 'zenodo':
        return zenodo_projection(doc)
    if kind == 'waypoints':
        if doc.get('type') != 'FeatureCollection' or not isinstance(doc.get('features'), list) or not doc['features']:
            raise ValueError('Expected a waypoint FeatureCollection')
        # Ignore envelope generation timestamps, preserve every actual feature/property.
        return sorted(doc['features'], key=lambda feature: canonical(feature))
    if kind == 'arcgis_metadata':
        if doc.get('error') or doc.get('type') != 'Feature Layer':
            raise ValueError('Expected ArcGIS feature layer metadata')
        reference = doc.get('extent', {}).get('spatialReference', {})
        # The published service is natively Mars transverse Mercator. The
        # geography builder explicitly requests outSR=104971 for geographic
        # output; its projected native extent must not be read as lon/lat.
        if reference.get('wkid') != 104971 and reference != spec.get('verified_native_spatial_reference'):
            raise ValueError('Jezero native coordinate declaration changed; verify before rebuilding geography')
        keys = ['id', 'name', 'type', 'geometryType', 'extent', 'fields', 'drawingInfo', 'editingInfo', 'maxRecordCount', 'capabilities']
        return {key: doc[key] for key in keys if key in doc}
    raise ValueError('Unsupported source kind: ' + kind)


def source_specs(config):
    specs, known_moc = [], []
    for mission in ('chemcam', 'supercam'):
        doc = json.loads((ROOT / 'dist/data' / (mission + '.json')).read_text())
        for source in doc['sources']:
            url = source['url']
            name = urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1]
            if mission == 'chemcam':
                selected = ('/data/moc/' in url and name.endswith(('.csv', '.lbl'))) or name in ('msl_ccam_obs.csv', 'msl_ccam_obs.lbl', 'release_notes.txt', 'MSL_waypoints.json')
            else:
                selected = source['id'] in ('supercam_moc', 'supercam_moc_label', 'supercam_masterlist', 'supercam_masterlist_label') or source['id'].startswith('places_')
            if not selected:
                continue
            if not re.fullmatch(r'[0-9a-f]{64}', source.get('sha256', '')):
                raise ValueError('Published source hash is absent: ' + url)
            spec = {'id': mission + ':' + source['id'], 'group': mission, 'kind': 'sha256',
                    'url': url, 'action': 'automatic_nasa', 'essential': True,
                    'published_fingerprint': source['sha256'], 'cache_path': mission + '/raw/' + name}
            specs.append(spec)
            if mission == 'chemcam' and '/data/moc/' in url:
                known_moc.append(url)
    specs.extend(dict(source) for source in config['sources'])
    inventory = {'id': 'chemcam:moc_inventory', 'group': 'chemcam', 'kind': 'moc_inventory',
                 'url': config['chemcam_inventory_url'], 'action': 'automatic_nasa', 'essential': True,
                 'published_value': sorted(known_moc), 'published_fingerprint': fingerprint(sorted(known_moc)),
                 'cache_path': 'chemcam/raw/moc_directory.html'}
    return specs, inventory


def check_one(spec, previous, cache, timeout):
    saved = previous.get(spec['id'])
    if saved and (saved.get('url'), saved.get('kind')) != (spec['url'], spec['kind']):
        saved = None
    record = {key: spec[key] for key in ('id', 'group', 'kind', 'url', 'action', 'essential')}
    try:
        body, headers, not_modified = request(spec['url'], saved, head=spec['kind'] == 'head', timeout=timeout)
        current = dict(saved or {}) if not_modified else {}
        current.update({key: spec[key] for key in ('url', 'kind', 'group')})
        current.update(headers)
        if not not_modified:
            value = semantic(spec, body, headers)
            current['fingerprint'] = hashlib.sha256(body).hexdigest() if spec['kind'] == 'sha256' else fingerprint(value)
            if body is not None:
                current.update(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
                relative = spec.get('cache_path') or 'metadata/' + re.sub(r'[^a-zA-Z0-9._-]', '_', spec['id']) + '.json'
                path = cache / relative
                atomic_write(path, body)
                current['cache_file'] = str(path)
            if spec['kind'] in ('moc_inventory', 'sol_inventory', 'zenodo', 'head', 'arcgis_metadata'):
                current['value'] = value
        expected = spec.get('published_fingerprint')
        origin = 'published_source_manifest'
        if expected is None and 'expected' in spec:
            value = spec['expected']
            if spec['kind'] == 'zenodo':
                value = {'id': str(value['id']), 'files': sorted(value['files'], key=lambda f: f['key'])}
            expected = fingerprint(value)
            origin = 'pinned_source_version'
        if expected is None and saved:
            expected = saved['fingerprint']
            origin = 'previous_successful_check'
        status = 'initialized' if expected is None else 'unchanged' if expected == current['fingerprint'] else 'changed'
        record.update(status=status, fingerprint=current['fingerprint'], baseline_fingerprint=expected,
                      baseline_origin=origin if expected is not None else None, http_not_modified=not_modified)
        if 'cache_file' in current and Path(current['cache_file']).exists():
            record['cache_file'] = current['cache_file']
        if spec['kind'] == 'moc_inventory':
            before, after = set(spec['published_value']), set(current['value'])
            record.update(added=sorted(after - before), removed=sorted(before - after), file_count=len(after))
            if before - after:
                record['block_automatic_refresh'] = True
                record['review_reason'] = 'Published MOC files disappeared from the directory; do not remove observations automatically.'
        return record, current
    except Exception as error:
        record.update(status='error', error_type=type(error).__name__, message=str(error)[:500])
        # Preserve only a prior SUCCESSFUL state; never substitute an error fingerprint.
        return record, saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--baseline-state', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=40)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12 or not 5 <= args.timeout <= 120:
        parser.error('Use 1–12 workers and a timeout of 5–120 seconds')
    config = json.loads(CONFIG.read_text())
    baseline = json.loads(args.baseline_state.read_text()) if args.baseline_state and args.baseline_state.exists() else {}
    previous = baseline.get('state', baseline).get('sources', {})
    cache = args.cache.resolve()
    specs, inventory = source_specs(config)
    records, states = [], dict(previous)

    # Discover new MOC files before scheduling downloads; historical files remain monitored.
    record, current = check_one(inventory, previous, cache, args.timeout)
    records.append(record)
    if current:
        states[inventory['id']] = current
    known_urls = {s['url'] for s in specs}
    if record['status'] != 'error':
        for url in current['value']:
            if url not in known_urls:
                name = url.rsplit('/', 1)[-1]
                specs.append({'id': 'chemcam:' + name, 'group': 'chemcam', 'kind': 'sha256',
                              'url': url, 'action': 'automatic_nasa', 'essential': True,
                              'cache_path': 'chemcam/raw/' + name, 'new_product': True})
    ids = [s['id'] for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source IDs in watch configuration')
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check_one, spec, previous, cache, args.timeout): spec for spec in specs}
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            record, current = future.result()
            if spec.get('new_product') and record['status'] != 'error':
                record['status'] = 'new'
                record['baseline_origin'] = 'absent_from_published_manifest'
            records.append(record)
            if current:
                states[spec['id']] = current
    records.sort(key=lambda value: value['id'])
    changes = [r for r in records if r['status'] in ('changed', 'new')]
    errors = [r for r in records if r['status'] == 'error']
    blocked = [r for r in records if r.get('block_automatic_refresh')]
    essential_errors = [r for r in errors if r['essential']]
    pending_auto = [r for r in changes if r['action'] == 'automatic_nasa']
    review = [r for r in changes if r['action'] != 'automatic_nasa' or r.get('block_automatic_refresh')]
    report = {
        'schema_version': '1.0', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'status': 'failed' if essential_errors or blocked else 'partial' if errors else 'ok',
        'auto_refresh_required': bool(pending_auto) and not essential_errors and not blocked,
        'automatic_refresh_blocked': bool(essential_errors or blocked),
        'pending_automatic_changes': len(pending_auto),
        'changes': changes, 'errors': errors, 'review_required': review,
        'summary': {status: sum(r['status'] == status for r in records) for status in ('unchanged', 'changed', 'new', 'initialized', 'error')},
        'sources': records,
        'state': {'schema_version': '1.0', 'sources': states},
        'notes': [
            'NASA fingerprints compare to the currently published dataset manifests, even when a previous check already saw an unpublished change.',
            'Optional source failures are reported separately; essential failures block automatic refresh and preserve prior successful source states.',
            'First observations without a known fingerprint initialize monitoring; they are not evidence of newly published data.',
            'HEAD object metadata and ArcGIS service metadata indicate possible context changes; they do not prove pixel/geometry equality.',
            'The source checker does not perform a literature search or classify minerals, organics, or geological units.',
            'Raman acquisitions and public dataset versions can be checked mechanically; new scientific interpretations need primary-source review.',
        ],
    }
    atomic_write(args.output, json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False).encode() + b'\n')
    print(json.dumps({k: report[k] for k in ('checked_at_utc', 'status', 'auto_refresh_required', 'automatic_refresh_blocked', 'pending_automatic_changes', 'summary')}))
    print(str(args.output.resolve()))
    return 2 if essential_errors or blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())

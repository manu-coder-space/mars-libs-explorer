#!/usr/bin/env python3
"""Stage public Mars archive updates for a validated GitHub commit, without secrets.

The repository's current data are the scientific baseline. Rebuilds occur in a
temporary copy; GitHub Actions commits only after this command and validation
finish successfully. No Sites access, API key, or browser session is used.
"""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'data/update-state.json'
STATUS = ROOT / 'dist/data/update-status.json'
EVIDENCE_FIELDS = ('category', 'target', 'method', 'evidence_status', 'summary',
                   'minerals', 'organic_interpretation', 'source_ids', 'source_url')
PROVENANCE_FILES = (
    'scripts/chemcam/source_manifest.json', 'scripts/chemcam/qa_report.json',
    'scripts/chemcam/sample_record.json', 'scripts/chemcam/findings.txt',
    'scripts/supercam/source_manifest.json', 'scripts/supercam/summary.json',
    'scripts/spectroscopy/verification.json', 'VALIDATION.json', 'CONTEXT_VALIDATION.json',
)

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def read_json(path, fallback=None):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(fallback)

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)

def public_state(value):
    """Store portable HTTP fingerprints, never local cache paths."""
    if isinstance(value, dict):
        return {key: public_state(item) for key, item in value.items() if key != 'cache_file'}
    if isinstance(value, list):
        return [public_state(item) for item in value]
    return value

def accepted_state(previous, check, outcome):
    """Failed/check-only runs must leave unactivated changes pending."""
    accepted = copy.deepcopy(previous)
    if outcome not in ('updated', 'unchanged'):
        return public_state(accepted)
    accepted.setdefault('schema_version', '1.0')
    accepted.setdefault('sources', {})
    review_ids = {row.get('id') for row in check.get('review_required', [])}
    for key, value in check['state'].get('sources', {}).items():
        if key not in review_ids:
            accepted['sources'][key] = value
    return public_state(accepted)

def pending_reviews(previous, check):
    """A source outage cannot silently resolve an earlier review item."""
    pending = {row['id']: row for row in previous}
    for row in check.get('sources', []):
        if row.get('status') == 'unchanged':
            pending.pop(row['id'], None)
    pending.update({row['id']: row for row in check.get('review_required', [])})
    return public_state([pending[key] for key in sorted(pending)])

def run(stage, *command):
    result = subprocess.run(command, cwd=stage, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stdout[-8000:]}")
    return result.stdout

def copy_stage(destination):
    excluded = {'.git', '.cache', '.sites-runtime', '.wrangler', 'exports', 'raw', '__pycache__', 'node_modules'}
    def ignored(directory, names):
        return [name for name in names if name in excluded or name in ('data.json', 'data.json.gz')
                or name.endswith(('.pyc', '.tar.gz'))]
    shutil.copytree(ROOT, destination, ignore=ignored)

def points_at(dist, mission):
    meta = read_json(dist / 'data' / f'{mission}.json')
    rows = [point for filename in meta['point_files'] for point in read_json(dist / filename)]
    indexed = {point['id']: point for point in rows}
    if len(indexed) != len(rows):
        raise ValueError(f'Duplicate {mission} measurement identifiers')
    return indexed

def compare_measurements(before, stage):
    comparisons = {}
    for mission, old in before.items():
        new = points_at(stage / 'dist', mission)
        fields = ('oxides', 'uncertainty', 'is_calibration', 'sol')
        revisions = sorted(identifier for identifier in old.keys() & new.keys()
                           if any(old[identifier].get(key) != new[identifier].get(key) for key in fields))
        comparisons[mission] = {'before': len(old), 'after': len(new),
                                'new_records': len(new.keys() - old.keys()),
                                'removed_ids': sorted(old.keys() - new.keys()),
                                'revised_historical_ids': revisions}
    return comparisons

def preserve_evidence(previous, rebuilt):
    current = {row['id']: row for row in rebuilt}
    for old in previous:
        new = current.get(old['id'])
        if new is None or any(old.get(key) != new.get(key) for key in EVIDENCE_FIELDS):
            raise RuntimeError('Archive refresh would remove or revise curated evidence; review and synchronize its builder first')

def dataset_date():
    candidates = []
    for mission in ('chemcam', 'supercam'):
        metadata = read_json(ROOT / 'dist/data' / f'{mission}.json')
        for key in ('generated_at_utc', 'retrieved_at_utc'):
            if metadata.get(key):
                try:
                    value = dt.datetime.fromisoformat(metadata[key].replace('Z', '+00:00'))
                    candidates.append(value.replace(tzinfo=value.tzinfo or dt.timezone.utc))
                except ValueError:
                    pass
    return max(candidates).astimezone(dt.timezone.utc).isoformat(timespec='seconds') if candidates else None

def portable_transport(stage):
    # Preserve the portable export's ordinary JSON transport on GitHub Pages;
    # no host-specific compressed-content response behavior is required.
    for mission in ('chemcam', 'supercam'):
        path = stage / 'dist/data' / f'{mission}.json'
        metadata = read_json(path)
        metadata.pop('point_files_gzip', None)
        metadata.pop('traverse_files_gzip', None)
        metadata['packaging']['transport'] = 'plain_json_portable_export'
        write_json(path, metadata)
        for compressed in (stage / 'dist/data' / mission).glob('*.json.gz'):
            compressed.unlink()

def rebuild(stage):
    before = {mission: points_at(stage / 'dist', mission) for mission in ('chemcam', 'supercam')}
    old_evidence = read_json(stage / 'dist/data/spectroscopy.json')['observations']
    commands = [
        [sys.executable, 'scripts/chemcam/fetch_sources.py', '--refresh'],
        [sys.executable, 'scripts/chemcam/ingest_chemcam.py', '--refresh-context'],
        [sys.executable, 'scripts/supercam/ingest_supercam.py', '--workdir', 'scripts/supercam', '--refresh'],
        [sys.executable, 'scripts/assemble_data.py', '--input-root', 'scripts'],
        [sys.executable, 'scripts/spectroscopy/build_evidence.py', '--input-root', 'scripts'],
        [sys.executable, 'scripts/validate_bundle.py'], ['node', 'scripts/check_chemistry.cjs'],
        [sys.executable, 'scripts/validate_context.py'],
    ]
    for command in commands:
        run(stage, *command)
        if 'scripts/assemble_data.py' in command:
            portable_transport(stage)
    preserve_evidence(old_evidence, read_json(stage / 'dist/data/spectroscopy.json')['observations'])
    comparison = compare_measurements(before, stage)
    if any(row['removed_ids'] or row['revised_historical_ids'] for row in comparison.values()):
        raise RuntimeError('Historic chemistry or record membership changed; source review is required before a data commit')
    result = {'prepared_at_utc': utcnow(), 'validation': 'passed', 'changes': comparison,
              'missions': read_json(stage / 'VALIDATION.json'), 'context': read_json(stage / 'CONTEXT_VALIDATION.json')}
    write_json(stage / 'dist/data/update_summary.json', result)
    return result

def install_validated_stage(stage):
    # A partial copy cannot be published: Actions requires this command to
    # finish, validates the candidate, then makes one ordinary Git commit.
    for mission in ('chemcam', 'supercam'):
        destination = ROOT / 'dist/data' / mission
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(stage / 'dist/data' / mission, destination)
        shutil.copy2(stage / 'dist/data' / f'{mission}.json', ROOT / 'dist/data' / f'{mission}.json')
        shutil.copytree(stage / 'dist/assets' / mission, ROOT / 'dist/assets' / mission, dirs_exist_ok=True)
    for relative in ('dist/data/spectroscopy.json', 'dist/data/update_summary.json', *PROVENANCE_FILES):
        source = stage / relative
        if source.is_file():
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

def outputs(report, destination):
    if destination:
        with destination.open('a') as handle:
            handle.write(f"outcome={report['outcome']}\n")
            handle.write(f"data_changed={'true' if report['outcome'] == 'updated' else 'false'}\n")
            handle.write(f"review_required={'true' if report.get('review_required') else 'false'}\n")
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        counts = report.get('source_check', {}).get('summary', {})
        with open(summary, 'a') as handle:
            handle.write('## Mars public-source check\n\n')
            handle.write(f"Result: **{report['outcome']}**. Checked {report.get('checked_at_utc', report['started_at_utc'])}.\n\n")
            handle.write('Source counts: ' + ', '.join(f'{key}: {value}' for key, value in counts.items()) + '.\n\n')
            if report.get('review_required'):
                handle.write('### Source changes needing review\n\n')
                for row in report['review_required']:
                    handle.write(f"- {row['id']}: {row['url']}\n")
            if report.get('error'):
                handle.write('The update was held. The prior dataset remains in the default branch and published site. See the saved run report.\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Check sources without rebuilding science data')
    parser.add_argument('--report', type=Path, default=ROOT / '.cache/updates/latest.json')
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    previous_state = read_json(STATE, {'schema_version': '1.0', 'sources': {}})
    previous_status = read_json(STATUS, {})
    status = {**previous_status, 'schema_version': '1.0', 'backend': 'github-actions',
              'schedule': {'is_enabled': os.environ.get('GITHUB_ACTIONS') == 'true', 'local_time': '08:00', 'timezone': 'America/Toronto'},
              'last_data_update_at_utc': previous_status.get('last_data_update_at_utc') or dataset_date()}
    report = {'schema_version': '1.0', 'started_at_utc': utcnow(), 'outcome': 'held'}
    cache_parent = ROOT / '.cache/updates'
    cache_parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='stage-', dir=cache_parent) as temporary:
            workspace = Path(temporary)
            stage = workspace / 'source'
            copy_stage(stage)
            baseline = workspace / 'accepted-state.json'
            write_json(baseline, previous_state)
            checked_path = workspace / 'source-check.json'
            checked = subprocess.run([sys.executable, 'scripts/updates/check_sources.py', '--cache', str(workspace / 'downloads'),
                                      '--baseline-state', str(baseline), '--output', str(checked_path)],
                                     cwd=stage, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if not checked_path.is_file():
                raise RuntimeError('Source checker did not return a report: ' + checked.stdout[-5000:])
            check = public_state(read_json(checked_path))
            check['review_required'] = pending_reviews(previous_status.get('review_required', []), check)
            report.update(source_check=check, checked_at_utc=check['checked_at_utc'], review_required=check.get('review_required', []))
            status.update(last_checked_at_utc=check['checked_at_utc'], source_errors=check.get('errors', []),
                          review_required=check.get('review_required', []), check_summary=check.get('summary', {}))
            if checked.returncode or check.get('status') == 'failed' or check.get('automatic_refresh_blocked'):
                raise RuntimeError('An essential source check failed or an archive product was withdrawn; the prior dataset is retained')
            if check.get('auto_refresh_required') and not args.check_only:
                report['validation'] = rebuild(stage)
                install_validated_stage(stage)
                report['outcome'] = 'updated'
                status.update(last_data_update_at_utc=utcnow(), message='New public archive data passed validation.')
            else:
                report['outcome'] = 'check_only' if check.get('auto_refresh_required') else 'unchanged'
                status['message'] = ('New NASA data are pending; this check-only run did not apply them.'
                                     if report['outcome'] == 'check_only' else 'No new NASA data require ingestion.')
            write_json(STATE, accepted_state(previous_state, check, report['outcome']))
    except Exception as error:
        report.update(outcome='held', error=str(error))
        status.update(message=str(error), last_attempt_at_utc=utcnow())
    report['finished_at_utc'] = utcnow()
    status.update(last_result=report['outcome'], last_finished_at_utc=report['finished_at_utc'])
    write_json(STATUS, public_state(status))
    write_json(args.report.resolve(), public_state(report))
    outputs(report, args.github_output)
    print(json.dumps({key: value for key, value in report.items() if key not in ('source_check', 'validation')}, ensure_ascii=False))
    return 1 if report['outcome'] == 'held' else 0

if __name__ == '__main__':
    raise SystemExit(main())

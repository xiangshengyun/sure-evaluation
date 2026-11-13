"""Score one EAR-1 task and track using platform-side references."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import re
import unicodedata
from zipfile import ZipFile

from .metrics import cpcer, der, normalize_text

VERSION = 'openbench-integration-0.1'
SESSION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*')
MAX_ZIP_TEXT = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    result = float(value)
    require(math.isfinite(result), 'Non-finite timestamp')
    return result


def spans(values, duration):
    result = []
    for begin, end in sorted((number(a), number(b)) for a, b in values):
        require(0 <= begin < end <= duration, 'Invalid scoring or exclusion interval')
        if result and begin <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((begin, end))
    return result


def load_sessions(path, track):
    config = json.loads(path.read_text(encoding='utf-8'))
    require(config['track'] == track, 'Track differs from the reference configuration')
    sessions = config['sessions']
    require(isinstance(sessions, dict) and sessions, 'Expected at least one reference session')
    for session, meta in sessions.items():
        require(SESSION_ID.fullmatch(session), f'Invalid session ID: {session}')
        duration = number(meta['duration_s'])
        require(duration > 0, f'Invalid duration for {session}')
        meta['duration_s'] = duration
        meta['uem'] = spans(meta.get('uem', [[0, duration]]), duration)
        require(meta['uem'], f'Empty UEM for {session}')
        meta['exclude'] = spans(meta.get('exclude', []), duration)
    return sessions


def parse(text, kind, sessions, label, session=None):
    recordings = defaultdict(list)
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        loc = f'{label}:{i}'
        if kind == 'rttm':
            fields = line.split()
            require(len(fields) == 10 and fields[0] == 'SPEAKER', f'{loc}: invalid RTTM row')
            _, sid, channel, begin, length, _, _, speaker, _, _ = fields
            start = number(begin)
            end = start + number(length)
            transcript = ''
        else:
            fields = line.split(maxsplit=5)
            require(len(fields) == 6, f'{loc}: expected five STM fields and transcript')
            sid, channel, speaker, begin, stop, transcript = fields
            start, end = number(begin), number(stop)
        require(sid in sessions and (session is None or sid == session), f'{loc}: unknown or mismatched session')
        require(channel == '1' and speaker != '<NA>', f'{loc}: invalid channel or speaker')
        duration = sessions[sid]['duration_s']
        require(0 <= start < duration and start < end <= duration + 1e-9, f'{loc}: timestamp outside recording')
        recordings[sid].append({'speaker': speaker, 'start': start, 'end': min(end, duration), 'text': transcript})
    return recordings


def read_zip(path, allowed, required):
    with ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(names) == len(set(names)), 'Duplicate ZIP member')
        require(set(names) <= allowed and required <= set(names),
                'Unexpected or missing ZIP member. Place the required files at the ZIP root.')
        require(sum(entry.file_size for entry in entries) <= MAX_ZIP_TEXT, 'Submission text exceeds the size limit')
        return {name: archive.read(name).decode('utf-8-sig') for name in names}


def load_pair(task, submission, reference_dir, sessions):
    if task == 'ESD-ON':
        required = {'submission.rttm'}
        files = read_zip(submission, required | {'empty_sessions.txt'}, required)
        hyp = parse(files['submission.rttm'], 'rttm', sessions, 'submission.rttm')
        empty = files.get('empty_sessions.txt', '').split()
        require(len(empty) == len(set(empty)) and not set(empty).intersection(hyp),
                'Duplicate empty-session declaration or session also present in RTTM')
        require(set(hyp) | set(empty) == set(sessions), 'RTTM coverage differs from the expected sessions')
        ref_file = reference_dir / 'reference.rttm'
        ref = parse(ref_file.read_text(encoding='utf-8-sig'), 'rttm', sessions, ref_file.name)
        return ref, hyp
    expected = {sid + '.stm' for sid in sessions}
    files = read_zip(submission, expected, expected)
    ref, hyp = {}, {}
    for sid in sessions:
        name = sid + '.stm'
        ref[sid] = parse((reference_dir / name).read_text(encoding='utf-8-sig'), 'stm', sessions, name, sid).get(sid, [])
        hyp[sid] = parse(files[name], 'stm', sessions, name, sid).get(sid, [])
    return ref, hyp


def project(rows, regions):
    # Concatenate scored regions so the core fits one speaker map across the UEM.
    result, offset = [], 0.0
    for begin, end in regions:
        for row in rows:
            start, stop = max(row['start'], begin), min(row['end'], end)
            if start < stop:
                result.append({**row, 'start': offset + (start - begin), 'end': offset + (stop - begin)})
        offset += end - begin
    return result, offset


def score_der(ref, hyp, meta):
    ref, duration = project(ref, meta['uem'])
    hyp, _ = project(hyp, meta['uem'])
    keys = ('miss_s', 'fa_s', 'conf_s', 'ref_s')
    if not ref:
        return dict(zip(keys, (0.0, sum(row['end'] - row['start'] for row in hyp), 0.0, 0.0)))
    result = der(ref, hyp, duration)
    return {key: result[key] for key in keys}


def streams(rows, exclusions):
    result = defaultdict(str)
    for row in sorted(rows, key=lambda x: (x['start'], x['end'])):
        if any(row['start'] < b and a < row['end'] for a, b in exclusions):
            continue
        text = normalize_text(row['text'])
        if text:
            result[row['speaker']] += text
    return result


def score_cpcer(ref, hyp, meta, backend):
    starred = [(row['start'], row['end']) for row in ref
               if '*' in unicodedata.normalize('NFKC', row['text'])]
    exclusions = spans([*meta['exclude'], *starred], meta['duration_s'])
    ref, hyp = streams(ref, exclusions), streams(hyp, exclusions)
    keys = ('substitutions', 'deletions', 'insertions', 'reference_characters')
    if not ref:
        return dict(zip(keys, (0, 0, sum(map(len, hyp.values())), 0)))
    result = cpcer(ref, hyp, distance_backend=backend)
    return {key: result[key] for key in keys}


def score(task, track, submission, reference_dir, backend='builtin', distance_backend=None):
    if distance_backend is not None:
        backend = distance_backend
    require(task in {'ESD-ON', 'ESR-ON'} and track in {'D1', 'R1'}, 'Unknown task or track')
    sessions = load_sessions(reference_dir / 'sessions.json', track)
    ref, hyp = load_pair(task, submission, reference_dir, sessions)
    if task == 'ESD-ON':
        counts = [score_der(ref.get(sid, []), hyp.get(sid, []), meta) for sid, meta in sessions.items()]
        metric, denominator, errors = 'DER', 'ref_s', ('miss_s', 'fa_s', 'conf_s')
    else:
        counts = [score_cpcer(ref[sid], hyp[sid], meta, backend) for sid, meta in sessions.items()]
        metric, denominator, errors = 'cpCER', 'reference_characters', ('substitutions', 'deletions', 'insertions')
    totals = {key: sum(row[key] for row in counts) for key in counts[0]}
    require(totals[denominator] > 0, 'Zero reference denominator for the track')
    value = sum(totals[key] for key in errors) / totals[denominator]
    return {'scorer_version': VERSION, 'task': task, 'track': track, 'metric': metric,
            'score': value, 'score_pct': 100 * value, 'session_count': len(sessions), 'counts': totals}



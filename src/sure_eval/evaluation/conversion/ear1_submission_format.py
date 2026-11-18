"""EAR-1 submission and reference parsing shared by the EAR-1 conversion profiles.

The functions below are copied from the organizer scorer ``score.py``
(``openbench-integration-0.1``). Validation messages and floating-point
operations are kept as in the original so the converted rows score
identically. Scoring itself lives in ``nodes/scoring/ear1_scorer``.
"""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import re
import unicodedata
from zipfile import ZipFile

SCORER_VERSION = 'openbench-integration-0.1'
SESSION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*')
MAX_ZIP_TEXT = 64 * 1024 * 1024
TRACKS = {'D1', 'R1'}


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


def load_sessions(path):
    """Read ``sessions.json``. Returns the declared track and validated sessions."""
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    require(config.get('track') in TRACKS, f"sessions.json track must be one of {sorted(TRACKS)}")
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
    return config.get('track'), sessions


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


def load_diarization_pair(submission, reference, sessions):
    """ESD-ON: submission ZIP with ``submission.rttm`` and a merged reference RTTM."""
    required = {'submission.rttm'}
    files = read_zip(submission, required | {'empty_sessions.txt'}, required)
    hyp = parse(files['submission.rttm'], 'rttm', sessions, 'submission.rttm')
    empty = files.get('empty_sessions.txt', '').split()
    require(len(empty) == len(set(empty)) and not set(empty).intersection(hyp),
            'Duplicate empty-session declaration or session also present in RTTM')
    require(set(hyp) | set(empty) == set(sessions), 'RTTM coverage differs from the expected sessions')
    reference = Path(reference)
    ref = parse(reference.read_text(encoding='utf-8-sig'), 'rttm', sessions, reference.name)
    return ref, hyp


def load_transcription_pair(submission, reference_dir, sessions):
    """ESR-ON: submission ZIP and reference directory with one STM per session."""
    expected = {sid + '.stm' for sid in sessions}
    files = read_zip(submission, expected, expected)
    reference_dir = Path(reference_dir)
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


def exclusion_spans(ref_rows, meta):
    """Organizer ``exclude`` intervals plus reference rows containing ``*``."""
    starred = [(row['start'], row['end']) for row in ref_rows
               if '*' in unicodedata.normalize('NFKC', row['text'])]
    return spans([*meta['exclude'], *starred], meta['duration_s'])


def kept_rows(rows, exclusions):
    """Rows in scoring order with every row overlapping an exclusion removed."""
    return [row for row in sorted(rows, key=lambda x: (x['start'], x['end']))
            if not any(row['start'] < b and a < row['end'] for a, b in exclusions)]


def write_seglst(path, rows_by_session):
    """Write rows as MeetEval SegLST JSON, keeping row order and exact float values."""
    segments = [
        {'session_id': sid, 'speaker': row['speaker'], 'start_time': row['start'],
         'end_time': row['end'], 'words': row['text']}
        for sid, rows in rows_by_session.items() for row in rows
    ]
    Path(path).write_text(json.dumps(segments, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return len(segments)

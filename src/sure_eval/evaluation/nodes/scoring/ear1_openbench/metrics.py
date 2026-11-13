"""Character cpCER and collar-0, overlap-inclusive full-UEM DER.

Conventions follow earchallenge/ear1-baselines at
d2db369c747f3bc527da52657da1e4240fa6051d. DER is computed without the audio
inference dependencies; regression checks compare against pyannote.metrics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import importlib.metadata
import importlib.util
import math
import unicodedata

try:
    from scipy.optimize import linear_sum_assignment as _scipy_linear_sum_assignment
except ImportError:  # pragma: no cover - exercised only in minimal installs
    _scipy_linear_sum_assignment = None


def _linear_sum_assignment(costs):
    """Return a minimum-cost assignment for a square matrix without SciPy.

    EAR-1 uses square speaker matrices. This compact Hungarian implementation
    keeps the builtin scorer self-contained; an optional SciPy installation is
    not required for the standard backend.
    """
    n = len(costs)
    if n == 0:
        return [], []
    if any(len(row) != n for row in costs):
        raise ValueError("assignment matrix must be square")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                current = float(costs[i0 - 1][j - 1]) - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [(p[j] - 1, j - 1) for j in range(1, n + 1)]
    assignment.sort()
    return [row for row, _ in assignment], [col for _, col in assignment]


def _assignment(costs):
    """Use SciPy's upstream assignment when available, otherwise fallback."""
    if _scipy_linear_sum_assignment is not None:
        rows, cols = _scipy_linear_sum_assignment(costs)
        return list(rows), list(cols)
    return _linear_sum_assignment(costs)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).lower()
    return ''.join(c for c in text if not c.isspace()
                   and not unicodedata.category(c).startswith('P'))


def character_distance(reference: str, hypothesis: str) -> int:
    """Exact unit-cost Levenshtein distance, bit-parallel over Unicode chars."""
    if len(reference) > len(hypothesis):
        reference, hypothesis = hypothesis, reference
    if not reference:
        return len(hypothesis)
    masks = {}
    for position, char in enumerate(reference):
        masks[char] = masks.get(char, 0) | (1 << position)
    width = len(reference)
    limit, last = (1 << width) - 1, 1 << (width - 1)
    positive, negative, distance = limit, 0, width
    for char in hypothesis:
        equal = masks.get(char, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        insertion = negative | ~(horizontal | positive)
        deletion = positive & horizontal
        distance += int(bool(insertion & last)) - int(bool(deletion & last))
        insertion, deletion = (insertion << 1) | 1, deletion << 1
        positive = (deletion | ~(vertical | insertion)) & limit
        negative = insertion & vertical & limit
    return distance


def resolve_distance_backend(requested: str) -> tuple[str, dict]:
    if requested not in ('auto', 'builtin', 'agwer'):
        raise ValueError(f'Unknown distance backend: {requested}')
    if requested == 'builtin':
        return 'builtin', {}
    if importlib.util.find_spec('agwer') is None:
        if requested == 'auto':
            return 'builtin', {}
        raise ImportError('agwer backend missing; install requirements-scoring-fast.txt or choose --distance-backend builtin')
    versions = {name: importlib.metadata.version(name) for name in ('agwer', 'rapidfuzz')}
    expected = {'agwer': '0.4.11', 'rapidfuzz': '3.9.7'}
    if versions != expected:
        raise ValueError(f'Fast scoring versions differ from requirements-scoring-fast.txt: {versions}; choose builtin or install the pinned profile')
    return 'agwer', versions


def character_edit_counts(reference: str, hypothesis: str, backend: str) -> dict:
    """Count one minimum-edit alignment; S/D/I tie splits depend on backend.

    The builtin fallback stores one DP row (linear memory). It is only run for
    selected speaker pairs, never for every entry in the assignment matrix.
    Equal-cost candidates prefer diagonal, deletion, then insertion.
    """
    if backend == 'agwer':
        from agwer.align import pooled_counts
        correct, substitutions, deletions, insertions = pooled_counts([reference], [hypothesis], chars=True)
    elif backend == 'builtin':
        if reference == hypothesis:
            return {'correct': len(reference), 'substitutions': 0, 'deletions': 0, 'insertions': 0}
        if not reference or not hypothesis:
            return {'correct': 0, 'substitutions': 0, 'deletions': len(reference), 'insertions': len(hypothesis)}
        # Cells: (distance, correct, substitutions, deletions, insertions).
        previous = [(j, 0, 0, 0, j) for j in range(len(hypothesis) + 1)]
        for i, ref_char in enumerate(reference, 1):
            current = [(i, 0, 0, i, 0)]
            for j, hyp_char in enumerate(hypothesis, 1):
                diagonal, deletion, insertion = previous[j-1], previous[j], current[-1]
                different = int(ref_char != hyp_char)
                diagonal_cost = diagonal[0] + different
                if diagonal_cost <= deletion[0] + 1 and diagonal_cost <= insertion[0] + 1:
                    current.append((diagonal_cost, diagonal[1] + 1 - different,
                                    diagonal[2] + different, diagonal[3], diagonal[4]))
                elif deletion[0] <= insertion[0]:
                    current.append((deletion[0] + 1, deletion[1], deletion[2], deletion[3] + 1, deletion[4]))
                else:
                    current.append((insertion[0] + 1, insertion[1], insertion[2], insertion[3], insertion[4] + 1))
            previous = current
        _, correct, substitutions, deletions, insertions = previous[-1]
    else:
        raise ValueError(f'Unknown alignment backend: {backend}')
    result = {'correct': correct, 'substitutions': substitutions, 'deletions': deletions, 'insertions': insertions}
    if correct + substitutions + deletions != len(reference) or correct + substitutions + insertions != len(hypothesis):
        raise ValueError('Character alignment count/length mismatch')
    return result


def cpcer(reference: dict[str, str], hypothesis: dict[str, str], distance_backend='auto') -> dict:
    refs, hyps = sorted(reference), sorted(hypothesis)
    characters = sum(map(len, reference.values()))
    if not characters:
        raise ValueError('cpCER has no nonempty reference text')
    count = max(len(refs), len(hyps))
    backend, versions = resolve_distance_backend(distance_backend)
    pairs = [(reference[refs[i]] if i < len(refs) else '', hypothesis[hyps[j]] if j < len(hyps) else '')
             for i in range(count) for j in range(count)]
    if backend == 'agwer':
        # Raw strings make this character distance. No agwer word tokenization
        # or English/Whisper normalizer is applied to EAR-1 normalized streams.
        from agwer.align import pair_errors
        distances = pair_errors([r for r, _ in pairs], [h for _, h in pairs])
    else:
        distances = [character_distance(r, h) for r, h in pairs]
    costs = [distances[i * count:(i + 1) * count] for i in range(count)]
    rows, cols = _assignment(costs)
    assignment = []
    for i, j in zip(rows, cols):
        ref, hyp = pairs[i * count + j]
        counts = character_edit_counts(ref, hyp, backend)
        if sum(counts[key] for key in ('substitutions', 'deletions', 'insertions')) != costs[i][j]:
            raise ValueError('S/D/I counts do not match the selected minimum edit distance')
        assignment.append({'reference_speaker': refs[i] if i < len(refs) else None,
                           'hypothesis_speaker': hyps[j] if j < len(hyps) else None,
                           'errors': costs[i][j], **counts})
    errors = sum(row['errors'] for row in assignment)
    totals = {key: sum(row[key] for row in assignment)
              for key in ('correct', 'substitutions', 'deletions', 'insertions')}
    return {'cpcer': errors / characters, 'cpcer_pct': 100 * errors / characters,
            'errors': errors, 'reference_characters': characters,
            **totals,
            **{key + '_pct': 100 * totals[key] / characters
               for key in ('substitutions', 'deletions', 'insertions')},
            'reference_speakers': len(refs), 'hypothesis_speakers': len(hyps),
            'distance_backend': backend, 'distance_backend_versions': versions,
            'alignment_backend': 'agwer-rapidfuzz-opcodes' if backend == 'agwer' else 'builtin-linear-space-dp',
            'alignment_policy': 'One unit-cost minimum-edit path per selected cpCER speaker pair; equal-cost paths can have different S/D/I splits',
            'assignment': assignment}


def der(reference: list[dict], hypothesis: list[dict], duration: float) -> dict:
    """Match pyannote DER with collar=0, skip_overlap=False, UEM=[0,duration].

    Each row is an annotation track. Duplicate/overlapping tracks of the same
    label are retained, matching pyannote Annotation rather than deduplicated.
    Global mapping maximizes co-occurrence duration; local errors use label
    multiplicities after that mapping. cpCER's text mapping is never used here.
    """
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('DER requires a positive recording duration')
    events = defaultdict(list)
    events[0.0]; events[duration]
    labels = [set(), set()]
    clipped = [[], []]
    for side, rows in enumerate((reference, hypothesis)):
        for row in rows:
            start, end = float(row['start']), float(row['end'])
            if not math.isfinite(start) or not math.isfinite(end) or end <= start:
                raise ValueError('Invalid DER interval')
            start, end = max(0.0, start), min(duration, end)
            if end <= start:
                continue
            speaker = row['speaker']
            clipped[side].append({'start': start, 'end': end, 'speaker': speaker})
            labels[side].add(speaker)
            events[start].append((side, speaker, 1))
            events[end].append((side, speaker, -1))
    refs, hyps = map(sorted, labels)
    ref_index, hyp_index = {s: i for i, s in enumerate(refs)}, {s: i for i, s in enumerate(hyps)}
    # pyannote maps hypothesis -> reference with a rectangular cost matrix.
    # Preserve this orientation: transposition/padding can change tied mappings.
    coincidence = [[0.0] * len(refs) for _ in hyps]
    # Accumulate pairwise intersections, as Annotation.__mul__ does. Splitting
    # at unrelated speakers' boundaries can introduce different rounding in ties.
    for hyp in sorted(clipped[1], key=lambda r: (r['start'], r['end'])):
        for ref in sorted(clipped[0], key=lambda r: (r['start'], r['end'])):
            if ref['start'] >= hyp['end']:
                break
            length = min(ref['end'], hyp['end']) - max(ref['start'], hyp['start'])
            if length > 0:
                coincidence[hyp_index[hyp['speaker']]][ref_index[ref['speaker']]] += length
    active, spans = [Counter(), Counter()], []
    times = sorted(events)
    for start, end in zip(times, times[1:]):
        for side, speaker, delta in events[start]:
            active[side][speaker] += delta
            if active[side][speaker] == 0:
                del active[side][speaker]
        length = end - start
        r, h = dict(active[0]), dict(active[1])
        spans.append((length, r, h))
    mapping, assignment = {}, []
    if refs and hyps:
        rows, cols = _assignment([[-value for value in row] for row in coincidence])
        for i, j in zip(rows, cols):
            # Zero-coincidence pairs remain unmatched, as in HungarianMapper.
            if coincidence[i][j] > 0:
                mapping[hyps[i]] = refs[j]
                assignment.append({'reference_speaker': refs[j], 'hypothesis_speaker': hyps[i],
                                   'cooccurrence_seconds': coincidence[i][j]})
    total = missed = false_alarm = confusion = correct = 0.0
    for length, r, h in spans:
        nr, nh = sum(r.values()), sum(h.values())
        matched = sum(min(number, r.get(mapping.get(speaker), 0)) for speaker, number in h.items())
        total += length * nr
        correct += length * matched
        missed += length * max(nr - nh, 0)
        false_alarm += length * max(nh - nr, 0)
        confusion += length * (min(nr, nh) - matched)
    if not total:
        raise ValueError('DER has no reference speech inside the recording UEM')
    error = (missed + false_alarm + confusion) / total
    return {'der': error, 'der_pct': 100 * error, 'miss_s': missed, 'fa_s': false_alarm,
            'conf_s': confusion, 'correct_s': correct, 'ref_s': total,
            'reference_speakers': len(refs), 'hypothesis_speakers': len(hyps),
            'collar': 0.0, 'skip_overlap': False, 'uem': [0.0, duration],
            'assignment': assignment, 'backend': 'interval-hungarian-v1'}

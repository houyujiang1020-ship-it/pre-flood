"""Durable write-ahead journal. Original review evidence is never rewritten."""
import copy
import json
import os
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .manifest import digest, read_json

VERSION = '1.0'
FLAGS = ('CLOUD', 'BLACK_BORDER', 'NO_DATA', 'INVALID_AREA', 'TEMPORAL_MISMATCH',
         'ALIGNMENT_ERROR', 'LABEL_ERROR', 'CORRUPTED_IMAGE', 'OTHER')
DECISIONS = ('accepted', 'rejected', 'needs_review', 'pending')


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


class Store:
    def __init__(self, manifest, directory, legacy=None):
        self.manifest, self.directory = manifest, Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal = self.directory / 'reviews.jsonl'
        self.snapshot = self.directory / 'review_state.json'
        self.legacy = Path(legacy) if legacy else manifest.path.parent / 'top20_visual_review.json'
        self.legacy_hash = digest(self.legacy) if self.legacy.exists() else None
        self.mutex = threading.RLock()
        self.snapshot_issues = []
        with self.lock():
            self.reload()
            # Derived snapshot can always be rebuilt from immutable baseline + WAL.
            if self.snapshot.exists():
                try:
                    old = read_json(self.snapshot)
                except (ValueError, OSError):
                    old = None
                if old != self.snapshot_value():
                    # Keep discrepant snapshot bytes for inspection before rebuilding the derived file.
                    (self.directory / 'snapshot_before_recovery.json').write_bytes(self.snapshot.read_bytes())
                    if isinstance(old, dict):
                        for sid, r in old.get('reviews', {}).items():
                            try:
                                self.validate(r, check_files=False)
                            except (ValueError, KeyError, TypeError) as exc:
                                self.snapshot_issues.append({'code': 'INVALID_SNAPSHOT_REVIEW', 'sample_id': sid, 'detail': str(exc)})
                        self.issues.extend(self.snapshot_issues)
                    atomic_json(self.directory / 'snapshot_recovery_report.json', {
                        'at': now(), 'reason': 'Snapshot differs from durable journal; rebuilt from journal and legacy baseline',
                        'journal_sequence': self.sequence})
            self.persist()

    @contextmanager
    def lock(self):
        with self.mutex:
            with (self.directory / '.write.lock').open('a+b') as f:
                if f.tell() == 0:
                    f.write(b'0'); f.flush()
                f.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    f.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(f, fcntl.LOCK_UN)

    def blank(self, sid):
        return {'sample_id': sid, 'decision': 'pending', 'selected_post': None,
                'flags': {k: False for k in FLAGS}, 'reject_reasons': [], 'notes': '',
                'reviewer': 'manual', 'reviewed_at': None, 'source': self.manifest.source(sid),
                'review_tool_version': VERSION, 'revision': 0}

    def reload(self):
        self.states = {sid: self.blank(sid) for sid in self.manifest.samples}
        self.issues = list(self.snapshot_issues)
        self.sequence = 0
        if self.legacy.exists():
            if digest(self.legacy) != self.legacy_hash:
                raise ValueError('Legacy review changed during session; restart after auditing evidence')
            legacy = read_json(self.legacy)
            seen = set()
            for item in legacy['decisions']:
                sid = self.manifest.keys.get((item['split'], item['label']))
                if not sid or sid in seen:
                    self.issues.append({'code': 'UNKNOWN_OR_DUPLICATE_LEGACY_REVIEW', 'record': item})
                    continue
                seen.add(sid)
                r = self.states[sid]
                value = item['decision']
                if value not in ('reject', 'post-event image 1', 'post-event image 2'):
                    self.issues.append({'code': 'INVALID_LEGACY_DECISION', 'record': item})
                    continue
                r.update(decision='rejected' if value == 'reject' else 'accepted',
                         selected_post=None if value == 'reject' else 'post' + value[-1],
                         notes=item.get('reason', ''), reviewer=legacy.get('reviewer', 'legacy'),
                         reviewed_at=legacy.get('reviewed_at'), legacy_record=copy.deepcopy(item),
                         legacy_evidence=legacy.get('evidence'), legacy_sha256=self.legacy_hash)
                # Retain verbatim legacy reasons; never guess flags from free text.
                r['reject_reasons'] = [item['reason']] if value == 'reject' and item.get('reason') else []
        if self.journal.exists():
            with self.journal.open(encoding='utf-8') as f:
                for number, line in enumerate(f, 1):
                    try:
                        event = json.loads(line)
                        if not line.endswith('\n'):
                            raise ValueError('incomplete journal tail')
                        if event['sequence'] != self.sequence + 1:
                            raise ValueError('journal sequence mismatch')
                        if event['manifest_sha256'] != self.manifest.sha256 or event['legacy_sha256'] != self.legacy_hash:
                            raise ValueError('source evidence changed')
                        record = event['record']
                        if record['sample_id'] not in self.states:
                            raise ValueError('unknown sample in journal')
                        self.validate(record, check_files=False)
                        self.states[record['sample_id']] = record
                        self.sequence = event['sequence']
                    except Exception as exc:
                        atomic_json(self.directory / 'journal_integrity_error.json', {'line': number, 'error': str(exc), 'at': now()})
                        raise ValueError(f'Journal line {number} invalid; original preserved. See journal_integrity_error.json') from exc

    def validate(self, r, check_files=True):
        if r['sample_id'] not in self.manifest.samples:
            raise ValueError('Unknown sample_id')
        if r['decision'] not in DECISIONS:
            raise ValueError('Invalid decision')
        post = r.get('selected_post')
        if post not in (None, 'post1', 'post2'):
            raise ValueError('Invalid selected_post')
        if post:
            image = self.manifest.samples[r['sample_id']]['images'][post]
            if not image or (check_files and not self.manifest.resolve(image['path']).is_file()):
                raise ValueError(post.upper() + ' unavailable')
        if r['decision'] == 'accepted' and not post:
            raise ValueError('Accepted requires post1 or post2')
        if r['decision'] in ('rejected', 'pending') and post:
            raise ValueError('Rejected/pending requires selected_post=null')
        if r['decision'] == 'rejected' and not r.get('reject_reasons'):
            raise ValueError('Rejected requires a reason flag or notes')
        if set(r['flags']) != set(FLAGS) or any(type(v) is not bool for v in r['flags'].values()):
            raise ValueError('Invalid flags')

    def save(self, sid, payload):
        with self.lock():
            self.reload()
            if sid not in self.states:
                raise ValueError('Unknown sample_id')
            old = self.states[sid]
            if payload.get('revision') != old['revision']:
                raise RuntimeError('Record changed in another tab. Reload before saving.')
            r = copy.deepcopy(old)
            for field in ('decision', 'selected_post', 'flags', 'notes', 'reviewer'):
                if field in payload:
                    r[field] = payload[field]
            if not isinstance(r['flags'], dict) or set(r['flags']) != set(FLAGS) or any(type(v) is not bool for v in r['flags'].values()):
                raise ValueError('Invalid flags')
            if not isinstance(r['notes'], str) or len(r['notes']) > 20000:
                raise ValueError('Notes must be text, maximum 20000 characters')
            if not isinstance(r['reviewer'], str) or not r['reviewer'].strip() or len(r['reviewer']) > 200:
                raise ValueError('Reviewer required (maximum 200 characters)')
            r['reject_reasons'] = ([k for k, v in r['flags'].items() if v] or
                                   ([r['notes'].strip()] if r['notes'].strip() else [])) if r['decision'] == 'rejected' else []
            r.update(reviewed_at=now(), review_tool_version=VERSION, revision=old['revision'] + 1)
            self.validate(r)
            event = {'sequence': self.sequence + 1, 'manifest_sha256': self.manifest.sha256,
                     'legacy_sha256': self.legacy_hash, 'record': r, 'operation_at': now()}
            with self.journal.open('a', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
                f.flush(); os.fsync(f.fileno())
            self.sequence += 1
            self.states[sid] = r
            self.persist()
            if self.sequence % 20 == 0:
                directory = self.directory / 'backups'
                atomic_json(directory / f'review_state-{self.sequence:08}.json', self.snapshot_value())
                for path in sorted(directory.glob('review_state-*.json'))[:-10]:
                    path.unlink()  # Only this tool's bounded derived backups, never source data.
            return copy.deepcopy(r)

    def snapshot_value(self):
        return {'schema_version': 1, 'manifest_sha256': self.manifest.sha256,
                'legacy_sha256': self.legacy_hash, 'sequence': self.sequence, 'reviews': self.states}

    def persist(self):
        atomic_json(self.snapshot, self.snapshot_value())
        atomic_json(self.directory / 'summary.json', self.summary())

    def summary(self):
        counts = Counter(r['decision'] for r in self.states.values())
        posts = Counter(r['selected_post'] for r in self.states.values() if r['decision'] == 'accepted')
        return {'total': len(self.states), **{k: counts[k] for k in DECISIONS},
                'selected_post1': posts['post1'], 'selected_post2': posts['post2'],
                'review_complete': bool(self.states) and counts['pending'] == counts['needs_review'] == 0}

    def query(self, kind='all', search='', risk=False):
        ids = [sid for sid, r in self.states.items() if search.lower() in sid.lower() and
               (kind == 'all' or r['decision'] == kind or
                (kind in ('post1', 'post2') and r['selected_post'] == kind))]
        return sorted(ids, key=lambda sid: (-self.manifest.samples[sid]['risk'], sid) if risk else (sid,))

    def resume(self):
        for kind in ('pending', 'needs_review'):
            ids = self.query(kind)
            if ids:
                return ids[0]
        return None

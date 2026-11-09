from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from .manifest import digest
from .review_store import atomic_json, now


def integrity(manifest, store, hashes=True):
    issues = list(manifest.issues) + list(store.issues)
    checked = 0
    for sid, sample in manifest.samples.items():
        for slot, image in sample['images'].items():
            if image is None:
                if slot != 'post2':
                    issues.append({'code': 'MISSING_REQUIRED_IMAGE', 'sample_id': sid, 'slot': slot})
                continue
            path = manifest.resolve(image['path'])
            if not path.is_file():
                issues.append({'code': 'MISSING_FILE', 'sample_id': sid, 'slot': slot, 'path': str(path)})
            elif hashes and image.get('sha256'):
                checked += 1
                if digest(path) != image['sha256']:
                    issues.append({'code': 'HASH_MISMATCH', 'sample_id': sid, 'slot': slot, 'path': str(path)})
        if not Path(sample['label']).is_file():
            issues.append({'code': 'MISSING_LABEL', 'sample_id': sid})
    for sid, record in store.states.items():
        try:
            store.validate(record)
        except (ValueError, KeyError) as exc:
            issues.append({'code': 'INVALID_REVIEW', 'sample_id': sid, 'detail': str(exc)})
    report = {'checked_at': now(), 'total_sample_count': manifest.total_entries,
              'unique_sample_count': len(manifest.samples), 'manifest_sha256': manifest.sha256,
              'hashes_checked': checked, 'full_hash_check': hashes, 'valid': not issues, 'issues': issues}
    atomic_json(store.directory / 'review_integrity_report.json', report)
    return report


def report(manifest, store, target):
    with store.lock():
        store.reload()
        store.persist()
        stats = store.summary()
        times = [r['reviewed_at'] for r in store.states.values() if r['reviewed_at']]
        if store.journal.exists():
            times += [json.loads(line)['operation_at'] for line in store.journal.read_text(encoding='utf-8').splitlines()]
        times = sorted(times, key=datetime.fromisoformat)
        reasons = Counter(reason for r in store.states.values() if r['decision'] == 'rejected' for reason in r['reject_reasons'])
        flags = Counter(k for r in store.states.values() for k, v in r['flags'].items() if v)
        text = ['# Germany Visibility Review Report', '', 'COMPLETE' if stats['review_complete'] else 'INCOMPLETE', '',
                '人工审查状态报告；不会冻结 split 或启动训练。', '',
                *[f'- {key}: {value}' for key, value in stats.items()], '',
                '- 开始时间: ' + (times[0] if times else '未开始'),
                '- 完成时间: ' + (times[-1] if times and stats['review_complete'] else '未完成'),
                '- 生成时间: ' + now(), '- manifest SHA256: ' + manifest.sha256,
                '- review_state SHA256: ' + digest(store.snapshot),
                '- legacy review SHA256: ' + str(store.legacy_hash), '',
                '## 拒绝原因分布', '', *[f'- {k}: {v}' for k, v in reasons.items()], '',
                '## 问题 flags 分布', '', *[f'- {k}: {flags[k]}' for k in sorted(flags)], '',
                '旧审查理由保留原文，未自动推断标准 flags。Preview 仅用于视觉审查，不用于训练。',
                'training_split_frozen=false（本工具不具备冻结功能）。', '']
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text('\n'.join(text), encoding='utf-8')
    return stats

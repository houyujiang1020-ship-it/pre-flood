# Germany Visibility Review Report

COMPLETE

人工审查状态报告；不会冻结 split 或启动训练。

- total: 197
- accepted: 116
- rejected: 81
- needs_review: 0
- pending: 0
- selected_post1: 91
- selected_post2: 25
- review_complete: True

- 开始时间: 2026-09-12T12:49:00+08:00
- 完成时间: 2026-09-12T06:14:46.339601+00:00
- 生成时间: 2026-09-12T06:15:56.219424+00:00
- manifest SHA256: bacb106ba38c5651243e948542fb0ff4da331685acbc5dc4df45f64b2afcdb9c
- review_state SHA256: b23abdbb2272b047a95debcf80b62af5729eea49a51606d20c72a094c4880071
- legacy review SHA256: 78df929618d80a1e7cf3e9040b931e744854d215ecf64ae3f4bd7110a7a887b9

## 拒绝原因分布

- CLOUD: 38
- LABEL_ERROR: 8
- INVALID_AREA: 5
- NO_DATA: 2
- BLACK_BORDER: 18
- CORRUPTED_IMAGE: 6
- OTHER: 1
- TEMPORAL_MISMATCH: 3
- post1 is cloud dominated; no post2 candidate: 7
- post1 is dominated by thick cloud; no post2 candidate: 1
- post1 contains a large invalid black area; no post2 candidate: 3
- ALIGNMENT_ERROR: 2

## 问题 flags 分布

- ALIGNMENT_ERROR: 2
- BLACK_BORDER: 18
- CLOUD: 39
- CORRUPTED_IMAGE: 6
- INVALID_AREA: 5
- LABEL_ERROR: 9
- NO_DATA: 2
- OTHER: 1
- TEMPORAL_MISMATCH: 3

旧审查理由保留原文，未自动推断标准 flags。Preview 仅用于视觉审查，不用于训练。
training_split_frozen=false（本工具不具备冻结功能）。

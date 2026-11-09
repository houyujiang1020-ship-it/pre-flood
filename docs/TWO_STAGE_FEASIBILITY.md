# Two-stage architecture feasibility study

Status: completed. Decision: **CASE A — two-stage strongly justified for a next, separate Predicted-Gate Integration study.** This is Germany development evidence, not independent accuracy evidence or a production feature.

## Scope and data boundary

The study used the frozen Germany reviewed split only: train 98, validation 18, test 0; split SHA256 `14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1`. The formal label pipeline maps channel 0/1 to non-flooded/flooded building and channel 2/3 to non-flooded/flooded road. Stage1 unions 0∨1 and 2∨3. Stage2 supervises channel 1 only within GT building union and channel 3 only within GT road union. The audit found no subset violations.

Both models retain SiamUnet_diff, GroupNorm8, 512 px input, the same pre/post preprocessing and augmentation, Adam at 0.0003, seed 20260912, and 40 epochs. Stage1 changes the head to building/road. Its loss is BCE plus 0.5 times the mean two-channel Dice. Its positive-aware sampler uses only building and road presence, with no flood-status quota. Stage2 has separate building and road conditional flood heads and applies BCE/Dice only inside the corresponding GT object mask.

## Results

All values below are on the same Germany validation set. “Calibrated” thresholds were selected on that set and therefore are descriptive development results.

| Task | Threshold | IoU | Precision | Recall | F1 | AP |
|---|---:|---:|---:|---:|---:|---:|
| Stage1 Building | 0.50 | 0.312 | 0.405 | 0.576 | 0.475 | 0.393 |
| Stage1 Building | calibrated 0.41 | 0.316 | 0.387 | 0.632 | 0.480 | 0.393 |
| Stage1 Road | 0.50 | 0.175 | 0.359 | 0.254 | 0.297 | 0.247 |
| Stage1 Road | calibrated 0.33 | 0.200 | 0.286 | 0.398 | 0.333 | 0.247 |
| Oracle Building flood status | 0.50 | 0.083 | 0.200 | 0.125 | 0.154 | 0.290 |
| Oracle Building flood status | calibrated 0.07 | 0.336 | 0.343 | 0.944 | 0.503 | 0.290 |
| Oracle Road flood status | 0.50 | 0.000 | n/a | 0.000 | 0.000 | 0.505 |
| Oracle Road flood status | calibrated 0.29 | 0.363 | 0.438 | 0.679 | 0.532 | 0.505 |

The old single-stage candidate uses frozen channel thresholds 0.54/0.45/0.18/0.25. Binary OR gives Building union IoU 0.284 and Road union IoU 0.181. Its inclusion-exclusion union score, calibrated on the same validation set, gives Building IoU 0.285/AP 0.378 and Road IoU 0.183/AP 0.211. The Stage1 gains are therefore +0.030 Building IoU, +0.017 Road IoU, and +0.036 Road AP using the calibrated score comparison. The four old sigmoid heads are independent, so `1-(1-p_nonflooded)(1-p_flooded)` is only a comparison score, not an exact union probability; binary OR remains the primary mask comparison.

Road morphology remains imperfect and fragmented. At the calibrated Stage1 road threshold, aggregate object overlap improves enough to cover nearly every validation GT component, but it creates many unmatched predicted components; the detailed per-tile skeleton recall, 1 px tolerance counts, component counts, fragments per matched GT, uncovered GT fraction, and unmatched components are in `experiments/two-stage/stage1-evaluation.json`.

Oracle Stage2's mapped-full-image binary counts equal the within-gate counts because predictions are multiplied by the true object mask; the meaning differs because the full image includes guaranteed-zero background. The default 0.5 road result is poorly calibrated even though AP is 0.505. The calibrated Oracle road result is substantially above the current single-stage flooded-road development baseline (AP about 0.046; frozen-threshold IoU about 0.053).

## Decision

Stage1 road improves over the single-stage road union, and Oracle Stage2 flooded-road status improves strongly. This matches predeclared CASE A: the two-stage architecture is strongly justified for a subsequent Predicted-Gate Integration experiment. The evidence suggests both object segmentation and status entanglement contributed to the prior bottleneck, with the larger recoverable gap in flood-status classification once the road location is known.

AI model research does not need to be abandoned, but this session stops here. The next study must measure Stage1 error propagation through a predicted gate. No predicted-gate system was built now.

`blind_holdout_used=false`; `louisiana_used=false`; `test_used=false`; `production_ready=false`. The online AI Service model and production thresholds were not changed.

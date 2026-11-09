# Factorized object/status spatial fold (2026-09-26)

## Motivation and method

Louisiana-West unlabeled inference showed that the independent sigmoid checkpoint usually predicts flooded
pixels as a subset of the corresponding non-flooded channel. A new four-logit interpretation was therefore
implemented without changing the SiamUnet architecture: building object, building conditional flood status,
road object, and road conditional flood status. The four reported probabilities are `object × (1-status)`,
`object × status` for each object type. They cannot overlap at a strict 0.5 threshold.

Object BCE is supervised on every valid pixel. Balanced status BCE is supervised only inside labeled objects,
and Dice uses the decoded four-class probabilities. Separately buffered road geometries of different status
overlap at a small number of junction pixels; flooded status deterministically wins only at those pixels while
the object union remains unchanged.

## Protocol correction before the clean comparison

The first `x=16..18` protocol incorrectly required raw raster masks to have no status overlap. Candidate
training failed at its first optimizer step, before a checkpoint or candidate holdout evaluation. An audit found
3,545 road-overlap pixels in training and 1,332 in that holdout, with zero building overlap. Because the paired
baseline result had already been revealed, no candidate was run on that fold. The invalidation is sealed in
`experiments/louisiana-x16-18-factorized-status-20260926/invalidation.json` (SHA-256
`bb92c8c377b7ab9895041fe6825de7a63cb7d03d8a6dca74fd2bb1beeb5ec191`).

The clean comparison was preregistered on the previously unevaluated Louisiana `x=13..15` strip: 592 training
tiles and 105 final-only spatial holdout tiles. Positive holdout tile counts were 84/15/85/28 for the four
classes. Both models used the same random seed, architecture, GroupNorm8, domain-balanced sampler, augmentation,
optimizer, 14 epochs, Dice weight, and fixed 0.5 threshold. Epochs 1–13 did not read holdout metrics.

## Independent reload result

| fixed-0.5 IoU | independent binary | factorized object/status | delta |
|---|---:|---:|---:|
| non-flooded building | 0.080769 | 0.000449 | -0.080320 |
| flooded building | 0.047911 | 0.000000 | -0.047911 |
| non-flooded road | 0.076197 | 0.002685 | -0.073512 |
| flooded road | 0.002537 | 0.000000 | -0.002537 |
| macro IoU | 0.051853 | 0.000783 | -0.051070 |

The factorized output achieved its structural invariant: building and road overlap pixels were both zero,
compared with 100,109 and 1,487 for the independent model. It nevertheless suppressed almost all predictions at
the fixed threshold: only 774 non-flooded-building and 4,852 non-flooded-road pixels remained, with no flooded
predictions. Structural exclusivity alone therefore does not improve recognition.

The independent checkpoint SHA-256 is
`fee6aaee35689f51588c6204c30cc6edb99164ee230b6ffb28fc7f2bb83600c1`; the factorized checkpoint SHA-256 is
`aafaf3c6317934c9296db32d2c4e0bfaa9d911c72d8475aa8b82fce985c7e88a`. Both were independently reloaded and
recomputed. The sealed evaluation SHA-256 is
`29b9683f3987df3ab379d4f3ba38b9a2ac793d7d0be1ac5650e985cf707efe35`.

## Decision

`promotion=rejected`. The candidate fails the preregistered macro, flooded-class, and per-class preservation
requirements. Do not tune its thresholds, status weighting, or product rule on `x=13..15`, and do not deploy
either checkpoint. This is development spatial evidence only; Louisiana-West was not read during either run,
`test_used=false`, and `production_ready=false`.

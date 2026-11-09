# Louisiana-East spatial holdout (2026-09-26)

## Protocol

This paired experiment excluded all 18 repeatedly used Germany validation tiles. From the former training
pool it held out the contiguous Louisiana-East strip whose filename x coordinate is at least 22: 92 tiles.
The remaining 605 tiles were used for training. Both runs used the same seed, domain-balanced sampling,
loss, model, output-layer initialization, and fixed 14 epochs. `validation_schedule=final_only` prevented
any holdout read or checkpoint selection before epoch 14.

This is a development spatial holdout. Louisiana data has been used in earlier research, so it is not the
future user-provided independent test and cannot establish production accuracy.

## First paired run — invalidated after leakage audit

| fixed-0.5 IoU | random initialization | foundation initialization | delta |
|---|---:|---:|---:|
| non-flooded building | 0.157778 | 0.253706 | +0.095928 |
| flooded building | 0.040006 | 0.032512 | -0.007494 |
| non-flooded road | 0.148252 | 0.264061 | +0.115809 |
| flooded road | 0.007029 | 0.057581 | +0.050552 |
| macro IoU | 0.088266 | 0.151965 | +0.063699 |

Random checkpoint SHA-256:
`274dc8369b6a1e78e7056d0e36fd5385aa02fbfbfa063f8ffba61ea592b90301`.

Foundation checkpoint SHA-256:
`93aeb2ce31acb8c0206732cca8718335c7840d651cf623f7dfd18688cf02e418`.

Foundation initialization raised flooded-building recall from 0.3070 to 0.5752 but reduced precision from
0.0440 to 0.0333. It predicted 145,175 flooded-building pixels for 8,407 truth pixels. The observed failure
is status overprediction rather than missed object localization.

This foundation checkpoint had previously been trained on all Louisiana-East tiles, including the 92 held-out
tiles. That exposure invalidates the foundation column as a spatial generalization estimate. The random column
remains a valid fixed-epoch baseline. The generated evaluation artifact is explicitly marked
`promotion=invalidated`; none of the apparent foundation gains are used for promotion.

## Fold-safe replacement result

The replacement foundation started from random weights, trained on the same 605 non-holdout tiles, and used
only the separate 18-tile Germany development split for foundation checkpoint selection. Its intersection
with the 92-tile Louisiana-East holdout was zero. Independent checkpoint reload reproduced foundation object
IoU 0.231347/0.277357 (mean 0.254352); checkpoint SHA-256 is
`37481aeb520342f7df573758a45a469f380b4bc020f9a3c07921385f8065dba4`.

| fixed-0.5 IoU | random initialization | clean foundation initialization | delta |
|---|---:|---:|---:|
| non-flooded building | 0.157778 | 0.215725 | +0.057947 |
| flooded building | 0.040006 | 0.026148 | -0.013858 |
| non-flooded road | 0.148252 | 0.258594 | +0.110342 |
| flooded road | 0.007029 | 0.052641 | +0.045612 |
| macro IoU | 0.088266 | 0.138277 | +0.050011 |

The clean downstream checkpoint SHA-256 is
`682ed3cdd80482dae82d67eb439de3a9b9b7dc52a70140a08bfdedf0ed9e1ab9`. Independent reload reproduced every
metric and confirmed zero validation reads before epoch 14.

## Decision

The leakage-free comparison is complete. Foundation transfer gives a large spatial-holdout macro gain, but
flooded-building IoU declines by 0.013858, exceeding the preregistered 0.005 tolerance. Therefore
`promotion=rejected`. The model is useful evidence that object representation transfers, but it does not
replace E4 or establish production accuracy. The sealed decision is in
`experiments/louisiana-east-spatial-holdout-20260926/fold-safe-evaluation.json`.

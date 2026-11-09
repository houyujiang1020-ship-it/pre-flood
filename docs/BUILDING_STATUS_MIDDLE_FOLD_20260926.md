# Building-status categorical loss, Louisiana middle fold (2026-09-26)

## Protocol

Before training, Louisiana-East tiles with filename x coordinate 19 through 21 were frozen as a fresh
106-tile spatial development holdout. It contains 33 tiles with flooded buildings and 42 with flooded roads.
The remaining 591 tiles formed the training set; the repeatedly selected Germany 18-tile validation set was
excluded. Both models used the same random seed, 14 epochs, domain-balanced sampler, SiamUnet_diff,
GroupNorm8, augmentation, Dice weight and fixed 0.5 threshold. `validation_schedule=final_only` produced zero
holdout reads before epoch 14.

The single candidate change made building states mutually exclusive: background/non-flooded/flooded
cross-entropy and softmax replaced two independent building BCE/sigmoid channels. Road supervision remained
binary BCE plus Dice. The labels contain no overlap between the two building classes.

## Result

| fixed-0.5 IoU | independent binary | categorical building status | delta |
|---|---:|---:|---:|
| non-flooded building | 0.090922 | 0.026903 | -0.064020 |
| flooded building | 0.151166 | 0.000000 | -0.151166 |
| non-flooded road | 0.064793 | 0.155230 | +0.090437 |
| flooded road | 0.000049 | 0.000000 | -0.000049 |
| macro IoU | 0.076732 | 0.045533 | -0.031199 |

Independent reload reproduced both results. Baseline checkpoint SHA-256 is
`33cf1a6fb481dd02b3f18ce91e7ba6d7d4012d30e18474bb5915207f1d4250ce`; candidate checkpoint SHA-256 is
`734b44fd5383dd557634e32787124e8eedc283a9decf3bbf5b238589f6d36994`.

## Decision

The candidate completely suppresses flooded-building output at the fixed threshold and reduces macro IoU.
It fails every material part of the preregistered gate, so `promotion=rejected`. Do not tune its threshold or
loss weights on this revealed fold. The sealed decision is
`experiments/louisiana-middle-building-status-20260926/evaluation.json`. This is development evidence only;
`test_used=false` and `production_ready=false`.

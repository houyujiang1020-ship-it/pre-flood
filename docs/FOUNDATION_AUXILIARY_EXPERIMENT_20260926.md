# Foundation auxiliary experiment (2026-09-26)

## Result

The promoted foundation is `models/experiments/germany-louisiana-single-unet-foundation-20260926/best_model.pth`.
It was selected at epoch 28 and independently reloaded in a new process.

| metric at fixed 0.5 | four-class leader object union | E3c single-image U-Net | delta |
|---|---:|---:|---:|
| building IoU | 0.255002 | 0.284363 | +0.029361 |
| road IoU | 0.227200 | 0.295812 | +0.068612 |
| mean object IoU | 0.241101 | 0.290088 | +0.048987 |

The checkpoint SHA-256 is `55502a96cf46f99dba5cafe929d7e1bdee70688bf08ee325821a2e454bd4a280`.
The test split was empty, so this is a development result and `production_ready=false`.

## Method and audit trail

The PRE-event foundation predicts building body, building border, building proximity, road body,
road skeleton, and road junction. Border/proximity/skeleton/junction targets are deterministic
approximations derived from the four supplied semantic masks; they are auxiliary shape supervision,
not new ground truth. Sampling stayed 1:1 Germany/Louisiana with the existing within-domain positive quotas.

The first E3 run used `SiamUnet_diff(pre, pre)` and failed (best mean object IoU 0.000700 at epoch 23).
Review then established that every inference skip difference is identically zero for equal inputs.
The balanced retry was stopped after epoch 6 because changing the loss could not correct that invalid graph.
E3c replaced only the forward graph with a true single-image U-Net skip path while retaining compatible
module names and tensor shapes. It inherited 84 parameter tensors from the previous four-class leader and
created only the six-channel output layer. The preregistration is under
`experiments/germany-louisiana-single-unet-foundation-20260926/preregistration.json`.

## Decision

E3c passed its preregistered rule: both object IoUs exceeded their baselines and mean object IoU improved
by more than 0.01. It was therefore permitted as initialization for E4. E3 and the stopped E3b run remain
negative evidence and are not model candidates.

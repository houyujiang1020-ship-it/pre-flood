# AI Model Audit (2026-10-05)

## Current Architecture

E4 uses the pinned upstream `SiamUnet_diff` graph, constructed with 3 RGB channels per timestamp and four output channels. GroupNorm (8 groups) replaces BatchNorm. The pre-event and post-event images are explicitly passed to the model. The output channels are non-flooded building, flooded building, non-flooded road, flooded road; inference currently applies independent sigmoid probabilities.

## Dataset

The frozen E4 configuration has 697 training tiles (Germany 98, Louisiana-East 599), 18 Germany development-validation tiles, and no labeled test tiles. The previous visibility review excluded unusable Germany scenes. The 512-pixel cache pairs pre/post rasters and four rasterized vector-label channels. Louisiana-West public test is unlabeled and was already used for a one-time blind inference, not for training or model selection.

## Input

Each timestamp contributes RGB. PRE defines the 512×512 geospatial target grid; POST is reprojected onto it. Valid supervision is the intersection of source and destination raster masks. `load_pair` validates road geometry and rasterizes buildings/roads; the current SpaceNet 8 preprocessing treats `flooded=null` as non-flooded. This convention applies to the original official data, not to new uncertain AI-assisted annotations. The service requires geometrically aligned equal-size input rasters.

## Output

Four binary logits become four independent sigmoid maps. `flood_mask` in the service is the union of flooded-building and flooded-road structure masks, not a continuous flood-water surface. The FastAPI `JobResult`/Java consumer expect the existing four class-mask keys; object-level `flood_prediction.json` is a distinct MapGIS business contract and is **not** currently produced directly by the AI service.

## Loss

E4 uses independent binary BCE plus 0.5×four-channel Dice. Experimental categorical-building, factorized object/status, road-union auxiliary, road Tversky, and EMA branches already exist but did not meet their own promotion criteria. E4 uses Adam at learning rate 0.0003.

## Sampler

E4 uses the existing `DomainBalancedPositiveSampler`: 400 samples/epoch, equal Germany/Louisiana quotas and within-domain positive-tile quotas. `ClassAwareSampler` also exists but is tile-level; there is no E4 crop-level class-aware sampler. Current full-image training is not fully random, but very thin roads shrink on 1300→512 resizing.

## Augmentation

Optional spatial flips/rotations are applied jointly to PRE, POST, label and valid mask. There is no active weak/strong teacher-student path. Training uses whole 512×512 pairs, not native-resolution crop training in the E4 config.

## Metrics

Validation uses fixed 0.5 per channel and four-class IoU/macro IoU. E4 selected epoch 14 of 30 by Germany development macro IoU. Per-class precision/recall/F1 are available in evaluation scripts, but no independent external accuracy exists. E4 Germany development IoUs: 0.225711/0.116226/0.227015/0.073678, macro 0.160657, flooded-road precision 0.113874.

## Checkpoint

E4's `best_model.pth` is SHA256 `ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc`; it is a research checkpoint and remains immutable. `train_full.py` saves best/last state, optimizer, epoch, selection score, history, run signature, RNG states, thresholds, class names, normalization and split hash. It supports `--resume`. It has optional EMA but no active AMP, GradScaler, scheduler or DDP in the E4 path. The current device is one RTX 4050 Laptop GPU.

## Inference

FastAPI loads an explicitly configured smoke/research checkpoint and returns five masks plus preview/statistics. The default fallback is not a trained production model. The Java MapGIS side consumes the existing class-mask schema; this refactor must remain opt-in and preserve all keys. The business `flood_prediction.json` requires a separate object bridge with MapGIS-ready geometry and `object_id/type/geometry/damage_probability/flood_status`.

## Weakness

Flooded-road IoU and precision are low. On the 18-tile development set all 38,481 flooded-road predicted pixels overlap the normal-road prediction. A fixed hard-argmax experiment removed every flooded-road prediction and reduced macro IoU to 0.113292. This points to status-probability ranking and sparse-object supervision, not simply a display overlap. The current 512 resize may lose topology; a prior native-crop experiment did not improve enough for promotion.

## Potential Leakage

The E4 train/validation manifest has distinct tile identities and no test entries; prior fold-safe studies detected and invalidated one initialization leakage. Germany's 18 validation tiles have been repeatedly used for architecture and threshold diagnostics. They are development data and no longer a fresh blind model-selection set. Auxiliary labels derived from existing masks and AI pseudo-labels are not independent ground truth. All future candidate comparison requires a frozen new spatial fold; final acceptance requires external four-class ground truth not used for tuning.

## Recommended Refactor

Preserve E4 and the service contract. Reuse the existing single-image E3c foundation and Siamese pre/post graph as starting points; add a separate change/status head, soft road spatial prior and train-only class-aware crops. Build isolated weak-label and pseudo-label tooling with explicit ignore masks and provenance. Use train-only thresholds for pseudo-label acceptance; any validation threshold search remains a development diagnostic and cannot turn Germany validation into an independent test. Gate model promotion on all key class metrics, especially flooded-road precision and nonzero recall, then run one frozen external test when compatible labels exist.

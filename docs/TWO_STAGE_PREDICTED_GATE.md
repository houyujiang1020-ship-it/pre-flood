# Predicted-Gate two-stage integration

Status: completed. Decision: **PG-B**. The frozen two-stage models do not become the final development candidate. `germany-reviewed-v1` remains the baseline candidate. No model training occurred in this study.

## Frozen inputs and method

The Stage1 checkpoint SHA256 is `f9aba1af820485d80d3cad8b8ece06df1bcb89a0bddb56e5b1622e69c4b7c4f9`; Oracle Stage2 is `7a01cb95d79f41d0ccc4065107be6e521593bb7aa30cd290ba67599ee85741de`. Both completion manifests and all recorded artifact hashes passed verification. Thresholds were locked before evaluation: object building/road `0.41/0.33`, status building/road `0.07/0.29`. The lock SHA256 is `78dcd71b2f366cad958988e91e6cf9f130286e54a25bbf26d18b2396b88694dd`.

Stage1 and Stage2 inference received PRE and POST imagery only. Ground truth was loaded after prediction for metrics, error decomposition, and labeled visualization. Hard Gate applies the locked object mask then the locked conditional-status threshold. Soft Gate uses only the semantic products `P(object) × P(status|object)` and `P(object) × (1-P(status|object))`; it has no fitted fusion weights.

## Gate recall

| Gate target | Recall | Covered / GT pixels |
|---|---:|---:|
| Building object | 0.632 | 35,759 / 56,615 |
| Road object | 0.398 | 49,650 / 124,781 |
| Flooded Building | 0.559 | 10,447 / 18,697 |
| Flooded Road | 0.440 | 11,154 / 25,376 |

## End-to-end four-class results

All values use the same Germany development validation18 and valid supervision mask.

| Integration / class | IoU | Precision | Recall | F1 | AP |
|---|---:|---:|---:|---:|---:|
| Hard non-flooded building | 0.036 | 0.235 | 0.040 | 0.069 | 0.166 |
| Hard flooded building | 0.107 | 0.117 | 0.539 | 0.193 | 0.057 |
| Hard non-flooded road | 0.158 | 0.277 | 0.268 | 0.273 | 0.132 |
| Hard flooded road | 0.097 | 0.118 | 0.358 | 0.178 | 0.086 |
| **Hard macro** | **0.099** | **0.187** | **0.301** | **0.178** | **0.110** |
| Soft non-flooded building | 0.228 | 0.307 | 0.473 | 0.372 | 0.256 |
| Soft flooded building | 0.085 | 0.086 | 0.830 | 0.156 | 0.094 |
| Soft non-flooded road | 0.168 | 0.218 | 0.425 | 0.288 | 0.223 |
| Soft flooded road | 0.087 | 0.097 | 0.468 | 0.160 | 0.088 |
| **Soft macro** | **0.142** | **0.177** | **0.549** | **0.244** | **0.165** |

## Single-stage comparison

| Class | Single-stage IoU | Hard IoU (absolute / relative change) | Soft IoU (absolute / relative change) |
|---|---:|---:|---:|
| Non-flooded Building | 0.227 | 0.036 (-0.191 / -84.3%) | 0.228 (+0.001 / +0.6%) |
| Flooded Building | 0.101 | 0.107 (+0.005 / +5.0%) | 0.085 (-0.017 / -16.7%) |
| Non-flooded Road | 0.154 | 0.158 (+0.004 / +2.7%) | 0.168 (+0.015 / +9.5%) |
| Flooded Road | 0.053 | 0.097 (+0.044 / +83.0%) | 0.087 (+0.034 / +63.4%) |

Hard Gate improves flooded-road IoU and AP over the single-stage baseline, but its +0.044 IoU gain misses the prelocked +0.05 requirement. Its macro IoU is below the single-stage baseline, chiefly because the low building-status threshold assigns most gated buildings to flooded and collapses non-flooded-building recall. Soft Gate has the better macro scores and preserves non-flooded building, but it also misses the flooded-road promotion threshold and reduces flooded-building IoU.

## Oracle retention and failure source

Hard Gate retains 31.7%/38.2%/19.8% of Oracle flooded-building IoU/F1/AP and 26.9%/33.4%/17.1% of Oracle flooded-road IoU/F1/AP. Soft retention for flooded road is 24.0%/30.1%/17.4%.

For flooded-road GT pixels, 14,222 (56.0%) are missed by Stage1; 2,070 (8.2%) pass Stage1 but are classified non-flooded by Stage2; 9,084 (35.8%) are correctly classified. Flooded building shows the same pattern: 44.1% Stage1 misses, 2.0% gate-passed status errors, and 53.9% correct. The dominant loss from the Oracle upper bound is Stage1 gate coverage.

All eight flooded-road GT connected components are touched and eventually detected, but pixel coverage is poor. Hard road skeleton recall is 0.469 with 1 px tolerance recall 0.551; single-stage values are 0.486/0.553. Hard produces 1,744 predicted road components and 1,506 unmatched components versus 1,324/1,122 for single-stage, so morphology does not support promotion. Soft raises skeleton recall to 0.540/0.617 but increases unmatched components to 1,700.

## Decision

The predeclared PG-A promotion rule fails. The result is PG-B because Oracle performance is strong, hard-gate flooded-road IoU retention is below 50%, and Stage1 misses greatly exceed gate-passed Stage2 errors. Two-stage does not become the final development candidate.

`recommended_integration=hard` if this architecture is revisited, following the prelocked decision rule and because its mutually exclusive masks are easier to interpret in GIS. This recommendation does not mean it passed promotion; neither integration is a candidate. Soft remains a useful probability-ranking diagnostic.

One tightly scoped Stage1 improvement study is justified because road object gate recall is only 0.398 and flooded-road gate recall is 0.440. Stage2 should remain frozen. After that single study, the project should either freeze a final development candidate for independent blind evaluation or stop architecture development.

The three fixed visualizations cover every flooded-road-positive validation sample and both flooded-building-positive samples. Every panel is marked `DEVELOPMENT VALIDATION`.

`production_ready=false`; `blind_holdout_used=false`; `louisiana_used=false`. No online model or production threshold was changed.

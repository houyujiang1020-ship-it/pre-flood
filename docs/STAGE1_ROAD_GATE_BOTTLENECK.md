# Stage1 Road Gate Bottleneck Study

Stage1 misses Road because its predicted coverage is low and varies sharply by scene, not because the audited validation roads generally collapse into 1–2 px structures. The 1300→512 full-image resize reduces median skeleton width from 13 to 5 px, but only 0.82% of 512 skeleton samples are ≤4 px. Component width does not track miss severity in this small set.

Flooded roads are not harder for the object gate: their recall is 0.440 versus approximately 0.387 for non-flooded roads. Invalid-mask and black-border proximity affect too few components to explain the result. The evidence points to low confidence and scene/appearance sensitivity as the main observed failure, with width, edge, and NoData effects unsupported as primary causes.

Stage1-E was not run because the mandatory resolution-evidence gate failed. Consequently Road gate recall remains 0.398, Flooded Road gate recall remains 0.440, and the last Predicted-Gate Flooded Road IoU remains 0.097. The historical PG promotion standard remains unmet.

`model_research_phase_paused=true`. No Experiment F, loss search, sampler search, backbone experiment, Stage2 retraining, or Predicted-Gate threshold search is authorized. `germany-reviewed-v1` remains the development baseline and two-stage remains a research result. The next project work moves to Gate 5, Gate 8, and Gate 9.

`blind_holdout_used=false`; `louisiana_used=false`; `production_ready=false`.

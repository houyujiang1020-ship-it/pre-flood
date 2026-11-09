# Single-stage research closure

`single_stage_tuning_status=paused`

The current local tuning phase is stopped. The class-aware sampler did not improve the development ranking, road-specific Tversky did not improve ranking, flooded-road AP remained low, flooded-road false positives remained high, and morphology did not improve consistently. Further local loss or sampler tuning has insufficient expected value.

This does not establish that a single-stage architecture is impossible. It records only that the current local tuning phase has stopped.

`germany-reviewed-v1`, Experiment C, and Experiment D checkpoints, manifests, histories, evaluations, OOF evidence, probability diagnostics, and morphology diagnostics were not overwritten. Their post-study SHA256 inventory is recorded in `experiments/two-stage/single-stage-closure-sha256.json`.

`production_ready=false`; `blind_holdout_used=false`.

# Experiment C final seal

status=completed
promotion=rejected
production_ready=false

C completed 40 epochs; best epoch=40. Original files were read and hashed without modification. All entries in its completion manifest were verified.

Reasons:
- frozen development thresholds underperform baseline (macro IoU 0.107021 vs 0.133868)
- new same-validation calibration does not establish improvement (0.122391 vs baseline 0.133868)
- two-fold threshold OOF underperforms old sampler (0.103920 vs 0.114051)
- flooded-building and road priority metrics regress at fixed development thresholds and OOF

The complete manifest, history, evaluation, development calibration, OOF, sample exposure and completion manifest were read. Seal hashes: experiments/diagnostics/experiment-d-preflight-20260912/protected-artifacts.json.

Keep germany-reviewed-v1 (old sampler epoch 37) as the development baseline. No C artifacts or source are changed for D; D has its own runner and loss module. No production promotion. Germany split remains train98/validation18/test0; no Louisiana or future blind holdout access.

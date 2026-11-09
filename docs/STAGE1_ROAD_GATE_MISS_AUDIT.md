# Stage1 Road Gate Miss Audit

The frozen Stage1 pipeline performs a **full-image resize from native 1300×1300 to 512×512**. It is not a native-resolution crop. The x/y scale is 0.393846. PRE is read directly at 512, POST is reprojected onto that 512 PRE grid, and labels are rasterized directly on the same grid.

Road width was estimated independently on the native grid and 512 grid using Chebyshev erosion distance sampled along the road skeleton (`width = 2×depth−1`). Native all-road widths have p05/p25/p50/p75/p95 of 11/13/13/15/21 px. At 512 they are 5/5/5/5/7 px. The median therefore shrinks 2.6×, consistent with the full-image resize.

Only 0.22% of 512 skeleton samples are estimated at ≤2 px and 0.82% at ≤4 px. Flooded-road values are still p05=5, p50=5, p95=7. Of 27 connected road components, 24 have median width 5 px and three have median width 7 px; none fall in the predefined 1, 2, or 3–4 px component buckets.

This distribution does not support a claim that roads generally collapse to 1–2 px at model input. It also cannot show increasing miss with decreasing width: 5 px components have pixel recall 0.408, while the three 7 px components have 0.348. The wider group is small and internally inconsistent, so this is descriptive rather than a causal width result.

Overall Road gate recall is 0.398. Flooded Road gate recall is 0.440; non-flooded Road gate recall is approximately 0.387. Flooded roads are therefore not preferentially missed in this validation set. All 27 GT road components are touched by some prediction, but many are only sparsely covered. Per-image recall ranges from 0.047 to 0.938 on images containing roads, which is much larger than the observed width variation.

All road networks touch a tile border because the buffered line network crosses tile boundaries, so that flag cannot separate good and bad cases. Only four components are near a valid-mask edge and three overlap a black-border region. Those conditions affect a minority of components and do not explain the global miss rate. The dominant observed pattern is low and highly variable Stage1 confidence/coverage, with image appearance or learned representation left as the residual explanation.

The encoder has four stride-2 max-pooling stages, producing theoretical spatial scales 1, 1/2, 1/4, 1/8, and 1/16. A 1–4 px input feature would have 0.0625–0.25 px theoretical support at the deepest stage. This is a geometric risk calculation, not a feature activation measurement. The measured road skeleton, however, is predominantly 5–7 px at input.

The high-resolution hypothesis is **not supported strongly enough to authorize Stage1-E**. Normal proportional compression is present, but material collapse to ≤4 px is only 0.82%, and width-related recall degradation is absent. No training, CUDA size trial, patch creation, or threshold search was performed.

`resolution_hypothesis_supported=false`; `stage1_e_authorized_by_audit=false`; `blind_holdout_used=false`; `louisiana_used=false`; `production_ready=false`.

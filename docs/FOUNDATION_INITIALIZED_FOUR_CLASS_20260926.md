# Foundation-initialized four-class experiment (2026-09-26)

## Result

E4 completed 30 epochs. The selected epoch 14 checkpoint is
`models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth`.
An independent process reloaded it and reproduced every fixed-0.5 IoU exactly.

| class IoU | previous domain-balanced leader | E4 | delta |
|---|---:|---:|---:|
| non-flooded building | 0.207851 | 0.225711 | +0.017860 |
| flooded building | 0.104213 | 0.116226 | +0.012013 |
| non-flooded road | 0.209415 | 0.227015 | +0.017600 |
| flooded road | 0.054116 | 0.073678 | +0.019562 |
| macro IoU | 0.143899 | 0.160657 | +0.016759 |

This is an 11.65% relative macro improvement, and all four classes improved. It passes the preregistered
rule of at least +0.005 macro with no class declining by more than 0.005. The checkpoint SHA-256 is
`ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc`.

The only experimental change was initialization: 84 compatible encoder/decoder tensors came from the
promoted E3c object foundation; the four-channel output layer was new. Data, split, sampler, model graph,
normalization, loss, learning rate, epochs, and threshold were held fixed. The preregistration is under
`experiments/germany-louisiana-foundation-initialized-four-class-20260926/preregistration.json`.

## Soft gate follow-up

One preregistered gate used
`p_gated = p_class * (0.75 + 0.25 * p_object)` at the unchanged 0.5 threshold. Macro IoU fell to 0.156770;
flooded-building, non-flooded-road, and flooded-road IoU declined beyond the allowed tolerance. The gate
was rejected, and gate strength or threshold will not be searched on the same validation split.

## Scope

E4 is the new research leader. It is not an independent test result and has not been installed as a
production model. The current test split remains empty, the Germany validation tiles have been used for
repeated development decisions, and `production_ready=false` remains mandatory.

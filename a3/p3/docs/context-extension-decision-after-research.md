# Context Extension: Decisions After Research

Decisions produced by section 3.1 (context extension literature review).

| # | Decision | Justification | Confirm |
|---|----------|---------------|---------|
| 1 | Short seq_len = 512 | GrowLength validates 2x per-stage jumps — the established baseline. We need to exceed 2x for meaningful cost savings (1024→2048 is nearly pointless). To anchor the starting length independently, BabyLM (Salhan et al., 2025) tests 125M-param models across seq_lens {64–8192} and recommends 512 as "a safe and efficient baseline across both architectures." This gives a 4x single-stage jump — the smallest extrapolation beyond GrowLength's 2x that still delivers meaningful savings. Assignment corroborates ("e.g. 512"). | |
| 2 | Loss spike on resume is expected and transient | GrowLength reports that 2x jumps produce "smooth" transitions while 8x jumps cause "dramatic loss rising." Our 4x jump falls between — we expect a spike, but GrowLength provides no quantitative recovery data. We run 500 extension steps with frequent saves to observe the actual trajectory. | |
| 3 | Our 4x per-jump will cause a larger spike than GrowLength's 2x per-stage | GrowLength warns that larger jumps between consecutive window sizes cause more dramatic loss rising | |
| 4 | Forgetting is unmitigated; extension phase must be kept short | ProLong shows mixing short-context data prevents forgetting, but nanochat doesn't do this — only defense is keeping extension brief | |
| 5 | Most learning happens during short-context phase; extension only adapts attention patterns | GrowLength and SkyLadder both find that short-context pretraining produces the bulk of capability, with extension mainly teaching the model to use longer positions | |

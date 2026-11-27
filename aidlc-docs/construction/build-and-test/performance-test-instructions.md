# Performance Test Instructions (U1 Foundation)

**Scope**: single user on one laptop (NFR-S.1), so no load or stress test applies. This file compares measured timings with the NFR targets.

## Test environment
- Windows 11 Home, NVIDIA GTX 1650 Ti (4 GB VRAM), 15.7 GiB RAM.
- Ollama 0.40.18, `qwen3:8b` with thinking on, context 4096. The model loads as 6.0 GB, split 61% CPU / 39% GPU.

## How measured
- Agent timings come from the integration harness (scenario S5 in `integration-test-instructions.md`): wall time per job and per model call, from the `job_id` key=value logs.
- GPU load: `nvidia-smi --query-gpu=utilization.gpu --format=csv` sampled every 3 s.
- Runner CPU: `Get-Process llama-server*` CPU seconds, sampled every 3 s.

## Targets vs. measured (2026-11-26)
| NFR | Target / limit | Measured | Result |
|---|---|---|---|
| P.1 Q&A answer | ≤ 30 s (target) | 241.2 s (3 steps) | **Not met** (known limitation) |
| P.1 journal draft | ≤ 90 s (target) | not measurable in U1 | Not verified (U3) |
| FD Q3 per-step rule | ≤ 11 s per step | 64.5 to 107.4 s per step | **Not met** (known; spike median was 65.6 s) |
| P.2 per model call | 120 s hard limit | longest call 107.4 s, including the model load | Met |
| P.3 per job | 300 s hard limit | 241.2 s; the 20 s test deadline cut the job at 20.0 s | Met; enforced |
| Cancel stops generation | GPU idle shortly after | GPU 33% → 0% within 3 s | Met |
| Status probe | 2 s timeout | Settings page loads with no visible delay; a dead port fails fast | Met (not timed exactly) |
| Nominatim | 5 s timeout, 1 req/s | unit tests only (mocked) | Not verified live |
| Test suite | none | 56.9 s default; 248.6 s with the `ci` profile | Info |

## Reading the results
- The model is the bottleneck. On a 4 GB GPU, `qwen3:8b` runs mostly on the CPU, so one answer takes about 4 minutes. That is under the 300 s job limit but far from the 30 s target. The spike (median 117.7 s per question) already showed this, and the team accepted it in NFR Requirements.
- The hard limits work: no call ran past 120 s, and both cancel paths freed the GPU.
- Risk: a question that needs more than about 4 steps will hit the 300 s job limit on this laptop.
- Options for U3/U4, which are the team's call: turn thinking off, use a smaller model, or allow fewer tool steps.

# Provider comparison (A2)

Synthetic invoices; one run per row (LLM answers vary a little run to run).

| set | provider | model | fully right | total exact | review P / R | retried | median ms | tokens/doc | cost/doc | when |
|---|---|---|---|---|---|---|---|---|---|---|
| easy | gemini | gemini-3.5-flash-lite | 33/36 | 100% | 75% / 100% | 0/36 | 1714 | 2364 | $0.00000 | 2026-10-11 13:49 |
| easy | groq | openai/gpt-oss-120b | 1/36 | 100% | 17% / 100% | 0/36 | 9432 | 97 | $0.00000 | 2026-10-12 14:05 |
| hard | gemini | gemini-3.5-flash-lite | 15/16 | 100% | 80% / 100% | 0/16 | 1602 | 1741 | $0.00000 | 2026-10-11 13:50 |
| real | gemini | gemini-3.5-flash-lite | 6/8 | 100% | 100% / 100% | 0/8 | 1501 | 2194 | $0.00000 | 2026-10-11 13:51 |
| world | gemini | gemini-3.5-flash-lite | 16/24 | 79% | 0% / n/a | 0/24 | 1541 | 2187 | $0.00000 | 2026-10-11 07:43 |
| world2 | gemini | gemini-3.5-flash-lite | 21/24 | 100% | 0% / n/a | 0/24 | 1770 | 2261 | $0.00000 | 2026-10-12 13:51 |
| world3 | gemini | gemini-3.5-flash-lite | 19/24 | 83% | 0% / n/a | 0/24 | 1414 | 1817 | $0.00000 | 2026-10-11 07:46 |
| world4 | gemini | gemini-3.5-flash-lite | 21/24 | 100% | 0% / n/a | 0/24 | 1493 | 1894 | $0.00000 | 2026-10-11 13:54 |
| world5 | gemini | gemini-3.5-flash-lite | 22/24 | 100% | 0% / n/a | 0/24 | 1474 | 1867 | $0.00000 | 2026-10-11 13:55 |
| world5 | groq | openai/gpt-oss-120b | 9/24 | 94% | 0% / n/a | 0/24 | 9125 | 2411 | $0.00000 | 2026-10-12 13:57 |

Failures per run: easy/gemini: inv_07, inv_20, inv_30; easy/groq: inv_00, inv_01, inv_02, inv_03, inv_04, inv_05, inv_06, inv_07, inv_08, inv_09, inv_10, inv_11, inv_12, inv_13, inv_14, inv_15, inv_16, inv_17, inv_18, inv_19, inv_20, inv_21, inv_22, inv_23, inv_24, inv_25, inv_26, inv_28, inv_29, inv_30, inv_31, inv_32, inv_33, inv_34, inv_35; hard/gemini: hard_01; real/gemini: real_07, real_08; world2/gemini: world_01, world_09, world_21; world3/gemini: world_05, world_09, world_16, world_17, world_21; world4/gemini: world_11, world_19, world_23; world5/gemini: world_19, world_23; world5/groq: world_00, world_04, world_05, world_07, world_09, world_11, world_12, world_16, world_17, world_18, world_19, world_20, world_21, world_22, world_23; world/gemini: world_02, world_06, world_09, world_10, world_12, world_14, world_15, world_18

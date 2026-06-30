# ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in PLANS.md) from design to implementation.

Please write the Exec Plan in Japanese.
Also, please create the Exec Plan under the .agent directory.

Please refer to existing Exec Plans in the .agent directory for examples.
Unless otherwise specified, the working directory is set to the root directory of the repository.

# Project Guardrails

- Keep this project focused on YouTube Shorts. Do not add automatic upload or buzz prediction unless explicitly requested.
- Do not commit generated media, local DB files, `.env`, downloaded BGM files, Pexels assets, or render outputs.
- Before pushing, run Ruff and pytest from the repository virtual environment.
- Treat `rendered.youtube.json` and `quality_report.json` as the main evidence for automated code improvements.
- Codex may fix code, constants, tests, credits, and FFmpeg stability based on quality reports. Human review remains required for factual correctness, music rights responsibility, final video quality, and publishing decisions.

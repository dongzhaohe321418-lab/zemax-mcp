# Repository operating instructions

This repository is the system of record for the Zemax MCP implementation and its simulations.

After every meaningful experimental milestone:

1. Copy `experiments/templates/experiment.json` to a scratch location and fill in the objective, hypothesis, exact inputs, numeric results, observations, application version, and next step.
2. Run `python scripts/record_experiment.py <unique-experiment-id> <scratch-json>`.
3. Put referenced Zemax designs and binary plots in `experiments/artifacts/<experiment-id>/`. Git LFS must remain enabled.
4. Run the relevant tests, inspect `git diff`, commit only the new milestone, and push it to GitHub.
5. Never commit `.env`, credentials, license information, machine-specific paths, or unredacted logs.

Experiment records are immutable. Corrections must be a new record whose notes identify the superseded experiment ID.
Never claim real OpticStudio verification unless the run actually used a licensed, installed OpticStudio instance.

"""Runtime helpers shared by scripts/phase1 entrypoints.

This package isolates config-loading and preflight-check helpers so that
Stage 2/3 runtime scripts do not inline their own file-existence and
config-shape validation. Pure Python — no Isaac Sim imports permitted.
"""

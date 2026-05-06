"""Runtime helpers shared by the ``marslab`` entrypoint.

This package isolates config-loading and preflight-check helpers so that
the ``marslab.main`` runtime script does not inline its own
file-existence and config-shape validation. Pure Python — no Isaac Sim
imports permitted.
"""

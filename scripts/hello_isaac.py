"""Minimal Isaac Sim verification script.

Run with: ~/isaacsim/python.sh scripts/hello_isaac.py

Verifies:
    - Isaac Sim SimulationApp launches in headless mode
    - A USD stage can be accessed
    - Simulation steps run without error
    - Clean shutdown
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

# omni imports must come after SimulationApp is created
import omni.usd  # noqa: E402

print("[hello_isaac] SimulationApp created successfully.")

stage = omni.usd.get_context().get_stage()
print(f"[hello_isaac] USD stage: {stage}")

for i in range(10):
    simulation_app.update()

print("[hello_isaac] 10 simulation steps completed.")

simulation_app.close()
print("[hello_isaac] Clean shutdown. Isaac Sim 5.1.0 is working.")

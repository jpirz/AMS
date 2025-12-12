# demo_sensors.py
#
# Feeds fake sensor data into the YachtOS backend for the
# "21ft Cabin Cruiser" profile.

import os
import asyncio
import random
from datetime import datetime, timezone

import httpx

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
YACHT_ID = os.getenv("YACHT_ID", "21ft Cabin Cruiser")

POLL_INTERVAL_SECONDS = 5


async def set_device_state(http: httpx.AsyncClient, device_id: str, state, source: str = "demo_sensors"):
    """
    Helper to POST device state to the backend.
    """
    url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/devices/{device_id}/state"
    body = {
        "state": state,
        "source": source,
    }
    try:
        resp = await http.post(url, json=body, timeout=5.0)
        resp.raise_for_status()
    except Exception as e:
        print(f"[demo_sensors] Failed to set {device_id}={state}: {e}")


async def one_cycle(http: httpx.AsyncClient, cycle: int):
    """
    One simulation tick: update a bunch of sensors in a semi-realistic way.
    """

    # --- Shore power present ---
    # Mostly ON, sometimes OFF to simulate unplugging.
    on_shore = random.random() < 0.8
    await set_device_state(http, "shore_power_present", on_shore)

    # --- House battery voltage ---
    # If on shore power: 13.6–14.2 V (charging)
    # If not: 12.0–12.8 V (discharging)
    if on_shore:
        voltage = round(random.uniform(13.6, 14.2), 2)
    else:
        voltage = round(random.uniform(12.0, 12.8), 2)
    await set_device_state(http, "battery_voltage_house", voltage)

    # --- Engine room temperature ---
    # Ambient-ish with some wiggle.
    engine_temp = round(random.uniform(20.0, 32.0), 1)
    await set_device_state(http, "engine_room_temp", engine_temp)

    # --- Bilge high float ---
    # Rare spikes to trigger bilge logic.
    bilge_high = random.random() < 0.05  # 5% chance
    await set_device_state(http, "bilge_float_high", bilge_high)

    # --- Cockpit motion + cabin door contact ---
    # If "people aboard", more motion.
    if random.random() < 0.6:
        # boat "occupied"
        motion = random.random() < 0.4
    else:
        # boat "unattended"
        motion = random.random() < 0.05

    door_open = motion and (random.random() < 0.5)

    await set_device_state(http, "motion_cockpit", motion)
    await set_device_state(http, "cabin_door_contact", door_open)

    # --- Cabin smoke detector ---
    # Almost always clear; tiny chance of alarm.
    smoke_alarm = random.random() < 0.01  # 1% chance
    await set_device_state(http, "smoke_cabin", smoke_alarm)

    # Small log line for your console
    now = datetime.now(timezone.utc).isoformat()
    print(
        f"[demo_sensors] {now} | shore={on_shore} "
        f"V_house={voltage}V EngTemp={engine_temp}°C "
        f"bilge_high={bilge_high} motion={motion} door_open={door_open} smoke={smoke_alarm}"
    )


async def main():
    async with httpx.AsyncClient() as http:
        cycle = 0
        while True:
            cycle += 1
            await one_cycle(http, cycle)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())

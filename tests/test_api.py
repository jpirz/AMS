import os
import tempfile
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient


class YachtOSApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.tmp.close()
        os.environ["YACHTOS_DB_PATH"] = cls.tmp.name

        from main import app

        cls.client = TestClient(app)
        cls.yacht_id = "marex-21-001"

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp.name)
        except FileNotFoundError:
            pass

    def test_seeded_yacht_devices_and_scenes(self):
        yachts = self.client.get("/yachts/")
        self.assertEqual(yachts.status_code, 200)
        self.assertEqual(yachts.json()[0]["id"], self.yacht_id)

        devices = self.client.get(f"/yachts/{self.yacht_id}/devices/")
        self.assertEqual(devices.status_code, 200)
        device_ids = {d["id"] for d in devices.json()}
        self.assertIn("motion_cockpit", device_ids)
        self.assertIn("smoke_cabin", device_ids)

        scenes = self.client.get(f"/yachts/{self.yacht_id}/scenes/")
        self.assertEqual(scenes.status_code, 200)
        self.assertGreaterEqual(len(scenes.json()), 4)

    def test_device_state_change_logs_event(self):
        normal = self.client.post(
            f"/yachts/{self.yacht_id}/simulator/run",
            json={"scenario": "normal"},
        )
        self.assertEqual(normal.status_code, 200)

        res = self.client.post(
            f"/yachts/{self.yacht_id}/devices/cabin_fan/state",
            json={"state": True, "source": "test"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["state"])

        events = self.client.get(f"/yachts/{self.yacht_id}/events/?limit=1")
        self.assertEqual(events.status_code, 200)
        latest = events.json()[0]
        self.assertEqual(latest["type"], "device_change")
        self.assertEqual(latest["details"]["device_id"], "cabin_fan")

    def test_sensor_values_can_be_numeric_but_outputs_must_be_boolean(self):
        sensor = self.client.post(
            f"/yachts/{self.yacht_id}/devices/battery_voltage_house/state",
            json={"state": 12.4, "source": "test"},
        )
        self.assertEqual(sensor.status_code, 200)
        self.assertEqual(sensor.json()["state"], 12.4)

        output = self.client.post(
            f"/yachts/{self.yacht_id}/devices/salon_lights/state",
            json={"state": 12.4, "source": "test"},
        )
        self.assertEqual(output.status_code, 400)

    def test_scene_activation_updates_devices_and_logs_event(self):
        res = self.client.post(
            f"/yachts/{self.yacht_id}/scenes/night_mode/activate",
            json={"source": "test"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], "night_mode")

        cabin_lights = self.client.get(
            f"/yachts/{self.yacht_id}/devices/cabin_lights"
        )
        self.assertEqual(cabin_lights.status_code, 200)
        self.assertTrue(cabin_lights.json()["state"])

        events = self.client.get(f"/yachts/{self.yacht_id}/events/?limit=1")
        self.assertEqual(events.json()[0]["type"], "scene_activation")

    def test_ai_logs_and_occupancy_are_persisted(self):
        log = self.client.post(
            f"/yachts/{self.yacht_id}/ai/logs",
            json={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": "test summary",
                "actions": [{"type": "no_op"}],
                "mode": "test",
            },
        )
        self.assertEqual(log.status_code, 200)

        logs = self.client.get(f"/yachts/{self.yacht_id}/ai/logs?limit=5")
        self.assertEqual(logs.status_code, 200)
        self.assertEqual(logs.json()[0]["summary"], "test summary")

        occupancy = self.client.post(
            f"/yachts/{self.yacht_id}/ai/occupancy",
            json={"occupancy": "unattended"},
        )
        self.assertEqual(occupancy.status_code, 200)

        snapshot = self.client.get(f"/yachts/{self.yacht_id}/ai/state_snapshot")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["occupancy"], "unattended")

    def test_ai_status_summary_and_ranked_suggestions(self):
        self.client.post(
            f"/yachts/{self.yacht_id}/simulator/run",
            json={"scenario": "low_battery"},
        )

        status = self.client.get(f"/yachts/{self.yacht_id}/ai/status")
        self.assertEqual(status.status_code, 200)
        status_json = status.json()
        self.assertIn(status_json["risk_level"], {"warning", "critical"})
        self.assertGreaterEqual(status_json["active_alarm_count"], 1)
        self.assertIn("recommended_actions", status_json)

        suggestions = self.client.get(f"/yachts/{self.yacht_id}/ai/suggestions")
        self.assertEqual(suggestions.status_code, 200)
        first = suggestions.json()["suggestions"][0]
        self.assertIn("severity", first)
        self.assertIn("confidence", first)
        self.assertIn("rank", first)
        self.assertIn("impact", first)

    def test_natural_language_device_control_executes_typed_command(self):
        self.client.post(
            f"/yachts/{self.yacht_id}/simulator/run",
            json={"scenario": "normal"},
        )
        reset = self.client.post(
            f"/yachts/{self.yacht_id}/devices/cabin_fan/state",
            json={"state": False, "source": "test_setup"},
        )
        self.assertEqual(reset.status_code, 200)

        command = self.client.post(
            f"/yachts/{self.yacht_id}/ai/nl-command",
            json={"message": "turn on cabin fan", "source": "test"},
        )
        self.assertEqual(command.status_code, 200)
        self.assertEqual(command.json()["intent"], "set_device_state")
        self.assertEqual(command.json()["status"], "executed")
        self.assertEqual(command.json()["translated_commands"][0]["device_id"], "cabin_fan")

        cabin_fan = self.client.get(f"/yachts/{self.yacht_id}/devices/cabin_fan")
        self.assertTrue(cabin_fan.json()["state"])

    def test_natural_language_mode_control_runs_scene(self):
        command = self.client.post(
            f"/yachts/{self.yacht_id}/ai/nl-command",
            json={"message": "activate anchor mode", "source": "test"},
        )
        self.assertEqual(command.status_code, 200)
        self.assertEqual(command.json()["intent"], "activate_anchor_mode")
        command_types = {cmd["type"] for cmd in command.json()["translated_commands"]}
        self.assertIn("set_vessel_mode", command_types)
        self.assertIn("activate_scene", command_types)

        mode = self.client.get(f"/yachts/{self.yacht_id}/mode/")
        self.assertEqual(mode.json()["mode"], "at_anchor")

    def test_ai_incidents_safety_explainer_and_maintenance(self):
        from app.services.core import device_service

        device_service.set_device_state(
            yacht_id=self.yacht_id,
            source="test_setup",
            device_id="cabin_heater",
            state=True,
        )

        smoke = self.client.post(
            f"/yachts/{self.yacht_id}/devices/smoke_cabin/state",
            json={"state": True, "source": "test"},
        )
        self.assertEqual(smoke.status_code, 200)

        incidents = self.client.get(f"/yachts/{self.yacht_id}/ai/incidents")
        self.assertEqual(incidents.status_code, 200)
        self.assertTrue(
            any(i["device_id"] == "smoke_cabin" for i in incidents.json()["incidents"])
        )

        explanations = self.client.get(f"/yachts/{self.yacht_id}/ai/safety-explanations")
        self.assertEqual(explanations.status_code, 200)
        self.assertTrue(
            any(e["device_id"] == "cabin_heater" for e in explanations.json()["explanations"])
        )

        for state in [True, False, True, False]:
            res = self.client.post(
                f"/yachts/{self.yacht_id}/devices/freshwater_pump/state",
                json={"state": state, "source": "test"},
            )
            self.assertEqual(res.status_code, 200)

        maintenance = self.client.get(f"/yachts/{self.yacht_id}/ai/maintenance")
        self.assertEqual(maintenance.status_code, 200)
        self.assertTrue(
            any(a["id"] == "repeat-freshwater_pump" for a in maintenance.json()["alerts"])
        )

    def test_ai_command_policy_rejects_never_controlled_device(self):
        command = {
            "yacht_id": self.yacht_id,
            "request_id": "test-command-reject",
            "requested_by": "ai_watchkeeper",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "actions": [
                {
                    "action_id": "try-horn",
                    "type": "set_device_state",
                    "device_id": "horn",
                    "target_state": True,
                    "priority": "critical",
                }
            ],
        }
        res = self.client.post(f"/yachts/{self.yacht_id}/ai/commands", json=command)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["results"][0]["status"], "rejected")

    def test_ai_suggestion_approval_executes_as_operator(self):
        from app.services.core import device_service, vessel_state

        vessel_state.set_mode(self.yacht_id, "at_anchor", source="test_setup")
        device_service.set_device_state(
            yacht_id=self.yacht_id,
            source="test_setup",
            device_id="anchor_light",
            state=False,
        )

        suggestions = self.client.get(f"/yachts/{self.yacht_id}/ai/suggestions")
        self.assertEqual(suggestions.status_code, 200)
        suggestion_ids = {s["id"] for s in suggestions.json()["suggestions"]}
        self.assertIn("suggest-anchor-light", suggestion_ids)

        approved = self.client.post(
            f"/yachts/{self.yacht_id}/ai/suggestions/suggest-anchor-light/approve",
            json={"source": "test_operator"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["results"][0]["status"], "executed")

        anchor_light = self.client.get(
            f"/yachts/{self.yacht_id}/devices/anchor_light"
        )
        self.assertTrue(anchor_light.json()["state"])

    def test_ai_command_policy_allows_safety_bilge_rule(self):
        command = {
            "yacht_id": self.yacht_id,
            "request_id": "test-command-bilge",
            "requested_by": "ai_watchkeeper",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "actions": [
                {
                    "action_id": "rule-bilge-test",
                    "type": "set_device_state",
                    "device_id": "bilge_pump_auto_override",
                    "target_state": True,
                    "priority": "critical",
                }
            ],
        }
        res = self.client.post(f"/yachts/{self.yacht_id}/ai/commands", json=command)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["results"][0]["status"], "executed")

    def test_control_authority_defers_ai_commands(self):
        control = self.client.post(
            f"/yachts/{self.yacht_id}/devices/cabin_fan/control",
            json={
                "authority": "ai_suggest_only",
                "reason": "operator wants approval",
                "source": "test",
            },
        )
        self.assertEqual(control.status_code, 200)
        self.assertEqual(control.json()["control_authority"], "ai_suggest_only")

        command = {
            "yacht_id": self.yacht_id,
            "request_id": "test-command-defer",
            "requested_by": "ai_watchkeeper",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "actions": [
                {
                    "action_id": "try-fan",
                    "type": "set_device_state",
                    "device_id": "cabin_fan",
                    "target_state": True,
                    "priority": "normal",
                }
            ],
        }
        res = self.client.post(f"/yachts/{self.yacht_id}/ai/commands", json=command)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["results"][0]["status"], "deferred")

        reset = self.client.post(
            f"/yachts/{self.yacht_id}/devices/cabin_fan/control",
            json={"authority": "ai_allowed", "source": "test"},
        )
        self.assertEqual(reset.status_code, 200)

    def test_control_pin_is_enforced_when_configured(self):
        old_pin = os.environ.get("YACHTOS_CONTROL_PIN")
        os.environ["YACHTOS_CONTROL_PIN"] = "1234"
        try:
            missing = self.client.post(
                f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
                json={"state": True, "source": "test"},
            )
            self.assertEqual(missing.status_code, 401)

            wrong = self.client.post(
                f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
                json={"state": True, "source": "test"},
                headers={"X-Control-PIN": "bad"},
            )
            self.assertEqual(wrong.status_code, 401)

            allowed = self.client.post(
                f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
                json={"state": True, "source": "test"},
                headers={"X-Control-PIN": "1234"},
            )
            self.assertEqual(allowed.status_code, 200)
            self.assertTrue(allowed.json()["state"])

            command = {
                "yacht_id": self.yacht_id,
                "request_id": "pin-command-test",
                "requested_by": "ai_watchkeeper",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "actions": [{"action_id": "noop", "type": "no_op"}],
            }
            ai_missing = self.client.post(
                f"/yachts/{self.yacht_id}/ai/commands",
                json=command,
            )
            self.assertEqual(ai_missing.status_code, 401)

            ai_allowed = self.client.post(
                f"/yachts/{self.yacht_id}/ai/commands",
                json=command,
                headers={"X-Control-PIN": "1234"},
            )
            self.assertEqual(ai_allowed.status_code, 200)
        finally:
            if old_pin is None:
                os.environ.pop("YACHTOS_CONTROL_PIN", None)
            else:
                os.environ["YACHTOS_CONTROL_PIN"] = old_pin

    def test_mode_endpoint_persists_and_enforces_navigation_lights(self):
        mode = self.client.post(
            f"/yachts/{self.yacht_id}/mode/",
            json={"mode": "underway", "source": "test"},
        )
        self.assertEqual(mode.status_code, 200)
        self.assertEqual(mode.json()["mode"], "underway")

        mode_read = self.client.get(f"/yachts/{self.yacht_id}/mode/")
        self.assertEqual(mode_read.status_code, 200)
        self.assertEqual(mode_read.json()["mode"], "underway")

        nav_lights = self.client.get(f"/yachts/{self.yacht_id}/devices/nav_lights")
        anchor_light = self.client.get(
            f"/yachts/{self.yacht_id}/devices/anchor_light"
        )
        self.assertTrue(nav_lights.json()["state"])
        self.assertFalse(anchor_light.json()["state"])

    def test_runtime_fields_are_tracked_for_outputs(self):
        reset = self.client.post(
            f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
            json={"state": False, "source": "runtime_setup"},
        )
        self.assertEqual(reset.status_code, 200)

        on = self.client.post(
            f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
            json={"state": True, "source": "runtime_test"},
        )
        self.assertEqual(on.status_code, 200)
        self.assertEqual(on.json()["last_changed_by"], "runtime_test")
        self.assertIsNotNone(on.json()["current_on_since"])

        off = self.client.post(
            f"/yachts/{self.yacht_id}/devices/deck_flood_light/state",
            json={"state": False, "source": "runtime_test"},
        )
        self.assertEqual(off.status_code, 200)
        self.assertIsNone(off.json()["current_on_since"])
        self.assertGreaterEqual(off.json()["total_runtime_seconds"], 0)

    def test_simulator_low_battery_derives_alarm_and_sheds_load(self):
        inverter_on = self.client.post(
            f"/yachts/{self.yacht_id}/devices/inverter_power/state",
            json={"state": True, "source": "test"},
        )
        self.assertEqual(inverter_on.status_code, 200)

        scenarios = self.client.get(f"/yachts/{self.yacht_id}/simulator/scenarios")
        self.assertEqual(scenarios.status_code, 200)
        self.assertIn("low_battery", scenarios.json()["scenarios"])

        run = self.client.post(
            f"/yachts/{self.yacht_id}/simulator/run",
            json={"scenario": "low_battery"},
        )
        self.assertEqual(run.status_code, 200)

        active = self.client.get(f"/yachts/{self.yacht_id}/alarms/active")
        self.assertEqual(active.status_code, 200)
        self.assertIn("battery_low_alarm", {a["device_id"] for a in active.json()})

        inverter = self.client.get(
            f"/yachts/{self.yacht_id}/devices/inverter_power"
        )
        self.assertFalse(inverter.json()["state"])

    def test_alarm_active_and_history_are_server_side(self):
        active_on = self.client.post(
            f"/yachts/{self.yacht_id}/devices/battery_low_alarm/state",
            json={"state": True, "source": "test"},
        )
        self.assertEqual(active_on.status_code, 200)

        active = self.client.get(f"/yachts/{self.yacht_id}/alarms/active")
        self.assertEqual(active.status_code, 200)
        self.assertIn("battery_low_alarm", {a["device_id"] for a in active.json()})

        ack = self.client.post(
            f"/yachts/{self.yacht_id}/alarms/acknowledge",
            json={"source": "test"},
        )
        self.assertEqual(ack.status_code, 200)
        self.assertGreaterEqual(ack.json()["acknowledged"], 1)

        active_after_ack = self.client.get(f"/yachts/{self.yacht_id}/alarms/active")
        battery_alarm = next(
            a for a in active_after_ack.json() if a["device_id"] == "battery_low_alarm"
        )
        self.assertIsNotNone(battery_alarm["acknowledged_at"])

        active_off = self.client.post(
            f"/yachts/{self.yacht_id}/devices/battery_low_alarm/state",
            json={"state": False, "source": "test"},
        )
        self.assertEqual(active_off.status_code, 200)

        history = self.client.get(f"/yachts/{self.yacht_id}/alarms/history?limit=10")
        self.assertEqual(history.status_code, 200)
        event_types = {event["type"] for event in history.json()}
        self.assertIn("ALARM", event_types)
        self.assertIn("ALARM_CLEAR", event_types)

        cleared = self.client.post(
            f"/yachts/{self.yacht_id}/alarms/clear-cleared",
            json={"source": "test"},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertGreaterEqual(cleared.json()["cleared"], 1)


if __name__ == "__main__":
    unittest.main()

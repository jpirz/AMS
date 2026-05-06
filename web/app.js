if (window.location.protocol === "file:") {
  window.location.replace("http://127.0.0.1:8000/ui/");
}

const apiBase = "";

    let yachtId = null;
    let yachtMeta = null;

    const READONLY_IDS = new Set([
      "helm_anchor_scene_button",
      "helm_night_scene_button"
    ]);

    const ALARM_IDS = new Set([
      "bilge_float_high",
      "battery_low_alarm"
    ]);

    const deviceContainer  = document.getElementById("deviceContainer");
    const sceneButtons     = document.getElementById("sceneButtons");
    const sensorContainer  = document.getElementById("sensorContainer");
    const eventsList       = document.getElementById("eventsList");
    const alarmsList       = document.getElementById("alarmsList");
    const lastActionEl     = document.getElementById("lastAction");
    const summaryLineEl    = document.getElementById("summaryLine");
    const themeToggleBtn   = document.getElementById("themeToggleBtn");
    const bgToggleBtn      = document.getElementById("bgToggleBtn");
    const muteAlarmBtn     = document.getElementById("muteAlarmBtn");
    const alarmBanner      = document.getElementById("alarmBanner");
    const alarmBannerText  = document.getElementById("alarmBannerText");
    const yachtTitleEl     = document.getElementById("yachtTitle");
    const yachtNameEl      = document.getElementById("yachtName");
    const yachtSelectEl    = document.getElementById("yachtSelect");
    const simulatorScenariosEl = document.getElementById("simulatorScenarios");

    const aiLogsEl         = document.getElementById("aiLogs");
    const aiStatusSummaryEl = document.getElementById("aiStatusSummary");
    const aiSuggestionsEl  = document.getElementById("aiSuggestions");
    const aiIncidentsEl    = document.getElementById("aiIncidents");
    const aiMaintenanceEl  = document.getElementById("aiMaintenance");
    const aiSafetyEl       = document.getElementById("aiSafetyExplanations");
    const aiChatInput      = document.getElementById("aiChatInput");
    const aiChatMessages   = document.getElementById("aiChatMessages");
    const aiChatSendBtn    = document.getElementById("aiChatSendBtn");

    const occupancyLabel   = document.getElementById("occupancyLabel");

    document.getElementById("apiBase").textContent  = window.location.origin;

    function controlHeaders(headers = {}) {
      const out = { ...headers };
      const pin = localStorage.getItem("ams_control_pin");
      if (pin) out["X-Control-PIN"] = pin;
      return out;
    }

    async function controlFetch(url, options = {}) {
      const request = {
        ...options,
        headers: controlHeaders(options.headers || {})
      };

      let res = await fetch(url, request);
      if (res.status !== 401) return res;

      const pin = window.prompt("Control PIN required");
      if (!pin) return res;

      localStorage.setItem("ams_control_pin", pin);
      res = await fetch(url, {
        ...options,
        headers: controlHeaders(options.headers || {})
      });
      return res;
    }

    /* THEME */

    let currentTheme = localStorage.getItem("ams_theme") || "dark";
    document.body.classList.remove("dark-theme","light-theme");
    document.body.classList.add(currentTheme + "-theme");

    /* BACKGROUND MODE */

    let bgMode = localStorage.getItem("ams_bg_mode") || "gradient";

    function updateThemeButtonLabel() {
      themeToggleBtn.textContent = currentTheme === "dark" ? "Light mode" : "Dark mode";
    }

    function updateBackgroundMode() {
      const isImage = bgMode === "image";
      document.body.classList.toggle("bg-image", isImage);
      if (bgToggleBtn) {
        bgToggleBtn.textContent = isImage ? "BG: Image" : "BG: Default";
      }
    }

    updateThemeButtonLabel();
    updateBackgroundMode();

    themeToggleBtn.addEventListener("click", () => {
      currentTheme = currentTheme === "dark" ? "light" : "dark";
      document.body.classList.remove("dark-theme","light-theme");
      document.body.classList.add(currentTheme + "-theme");
      localStorage.setItem("ams_theme", currentTheme);
      updateThemeButtonLabel();
    });

    if (bgToggleBtn) {
      bgToggleBtn.addEventListener("click", () => {
        bgMode = bgMode === "image" ? "gradient" : "image";
        localStorage.setItem("ams_bg_mode", bgMode);
        updateBackgroundMode();
      });
    }

    /* 🔇 MUTE ALARM (localStorage) + 🔊 audible alarm */

    let alarmMuted = localStorage.getItem("ams_alarm_mute") === "1";

    function updateMuteAlarmUI() {
      if (!muteAlarmBtn) return;
      muteAlarmBtn.textContent = alarmMuted ? "Alarm: MUTED" : "Alarm: Sound ON";
      muteAlarmBtn.style.opacity = alarmMuted ? "0.85" : "1";
    }

    if (muteAlarmBtn) {
      muteAlarmBtn.addEventListener("click", () => {
        alarmMuted = !alarmMuted;
        localStorage.setItem("ams_alarm_mute", alarmMuted ? "1" : "0");
        updateMuteAlarmUI();
        if (alarmMuted) stopAlarmBeep();
        // if unmuted and alarms are active, the next refresh will re-start beeping
      });
    }

    updateMuteAlarmUI();

    // Simple beep loop (browser requires user interaction before audio works)
    let audioCtx = null;
    let alarmBeepTimer = null;
    let wantBeep = false;

    function armAudio() {
      if (audioCtx) return;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      audioCtx = new Ctx();
    }

    // arm on first user interaction
    document.addEventListener("pointerdown", () => {
      armAudio();
      if (audioCtx && audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
      if (wantBeep && !alarmMuted) startAlarmBeep();
    }, { once: true });

    function beepOnce(durationSec = 0.18, freq = 880) {
      if (!audioCtx) return;
      try {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.value = 0.0001;
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        const now = audioCtx.currentTime;
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.linearRampToValueAtTime(0.08, now + 0.01);
        gain.gain.linearRampToValueAtTime(0.0001, now + durationSec);

        osc.start(now);
        osc.stop(now + durationSec + 0.02);
      } catch (e) {
        // ignore
      }
    }

    function startAlarmBeep() {
      if (!audioCtx) return; // will start after first click
      if (alarmBeepTimer) return;
      beepOnce();
      alarmBeepTimer = setInterval(() => beepOnce(), 1100);
    }

    function stopAlarmBeep() {
      if (alarmBeepTimer) {
        clearInterval(alarmBeepTimer);
        alarmBeepTimer = null;
      }
    }

    function updateAudibleAlarm(activeCount) {
      wantBeep = activeCount > 0;
      if (alarmMuted || activeCount === 0) {
        stopAlarmBeep();
        return;
      }
      if (!audioCtx) {
        // will arm on first click; keep wantBeep=true so it starts once armed
        return;
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume().catch(() => {});
      }
      startAlarmBeep();
    }

    /* TABS */

    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const page = btn.getAttribute("data-page");
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
        document.getElementById("page-" + page).classList.add("active");

        if (page === "alarms" && yachtId) {
          loadAlarmEvents();
        }
        if (page === "events" && yachtId) {
          loadAiDashboard();
        }
      });
    });

    /* MODE BUTTONS */

    const MODE_BY_SCENE = {
      underway: "underway",
      at_anchor: "at_anchor",
      harbour_mode: "in_port"
    };

    document.querySelectorAll(".mode-pill").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sceneId = btn.getAttribute("data-scene");
        if (!yachtId) return;
        const mode = MODE_BY_SCENE[sceneId];
        if (mode) await setVesselMode(mode);
        await activateScene(sceneId, btn.textContent.trim());
      });
    });

    function updateModePills(mode) {
      const sceneByMode = {
        underway: "underway",
        at_anchor: "at_anchor",
        in_port: "harbour_mode"
      };
      const activeScene = sceneByMode[mode] || null;
      document.querySelectorAll(".mode-pill").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-scene") === activeScene);
      });
    }

    async function loadVesselMode() {
      if (!yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/mode/`);
        if (!res.ok) throw new Error("Failed to load vessel mode");
        const data = await res.json();
        updateModePills(data.mode);
      } catch (err) {
        console.error(err);
      }
    }

    async function setVesselMode(mode) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/mode/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode, source: "web_ui" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to set mode: ${errText}`);
        }
        updateModePills(mode);
        setLastAction(`Mode: ${mode}`);
        await loadDevices();
      } catch (err) {
        console.error(err);
        setLastAction("Error setting mode");
      }
    }

    /* OCCUPANCY */

    let occupancyMode = localStorage.getItem("ams_occupancy") || "onboard";

    function updateOccupancyUI() {
      if (occupancyLabel) {
        occupancyLabel.textContent =
          occupancyMode === "unattended" ? "Unattended" : "Onboard";
      }
      document.querySelectorAll(".occ-pill").forEach(b => {
        const val = b.getAttribute("data-occupancy");
        b.classList.toggle("active", val === occupancyMode);
      });
    }

    async function sendOccupancyToBackend() {
      if (!yachtId) return;
      try {
        await fetch(`${apiBase}/yachts/${yachtId}/ai/occupancy`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            occupancy: occupancyMode,
            source: "web_ui"
          })
        });
        setLastAction(`Occupancy: ${occupancyMode}`);
      } catch (err) {
        console.error(err);
        setLastAction("Error updating occupancy");
      }
    }

    document.querySelectorAll(".occ-pill").forEach(btn => {
      btn.addEventListener("click", () => {
        const value = btn.getAttribute("data-occupancy");
        occupancyMode = value === "unattended" ? "unattended" : "onboard";
        localStorage.setItem("ams_occupancy", occupancyMode);
        updateOccupancyUI();
        sendOccupancyToBackend();
      });
    });

    updateOccupancyUI();

    /* HEADER BUTTONS */

    document.getElementById("refreshDevicesBtn").addEventListener("click", () => {
      if (!yachtId) return;
      loadDevices();
      loadScenes();
    });
    document.getElementById("refreshSensorsBtn").addEventListener("click", () => {
      if (!yachtId) return;
      loadDevices();
    });
    document.getElementById("refreshEventsBtn").addEventListener("click", () => {
      if (!yachtId) return;
      loadAiDashboard();
    });
    document.getElementById("refreshAlarmsBtn").addEventListener("click", () => {
      if (!yachtId) return;
      loadAlarmEvents();
    });
    document.getElementById("ackAlarmsBtn").addEventListener("click", acknowledgeAlarms);
    document.getElementById("clearAlarmsBtn").addEventListener("click", () => {
      if (!yachtId) return;
      clearAlarmSensors();
    });

    if (aiChatSendBtn) {
      aiChatSendBtn.addEventListener("click", sendAiChat);
    }

    if (aiChatInput) {
      aiChatInput.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
          ev.preventDefault();
          sendAiChat();
        }
      });
    }

    function setLastAction(text) {
      const now = new Date();
      lastActionEl.textContent = `${text} @ ${now.toLocaleTimeString()}`;
    }

    /* ALARM HELPERS */

    function isAlarmishSensor(dev) {
      const id = (dev.id || "").toLowerCase();
      const name = (dev.name || "").toLowerCase();
      const hay = id + " " + name;

      if (ALARM_IDS.has(dev.id)) return true;

      // Also treat obvious alarm-ish OUTPUTS (eg bilge pump running) as alarm candidates
      if (dev.type && String(dev.type).toLowerCase() === "pump" && hay.includes("bilge")) return true;

      return (
        hay.includes("bilge") ||
        hay.includes("battery") ||
        hay.includes("fuel") ||
        hay.includes("tank") ||
        hay.includes("temp") ||
        hay.includes("temperature") ||
        hay.includes("overheat") ||
        hay.includes("shore") ||
        hay.includes("ac_input") ||
        hay.includes("smoke") ||
        hay.includes("fire") ||
        hay.includes("co2") ||
        hay.includes("leak") ||
        hay.includes("water")
      );
    }

    function isDeviceInAlarmState(dev) {
      const v = dev.state;
      const id = (dev.id || "").toLowerCase();
      const name = (dev.name || "").toLowerCase();
      const hay = id + " " + name;

      if (ALARM_IDS.has(dev.id) && v === true) return true;

      // bilge pump running = alarm-ish (so it stays visible + logged)
      if ((dev.type || "").toLowerCase() === "pump" && hay.includes("bilge") && v === true) return true;

      if (typeof v === "boolean") {
        if (hay.includes("shore") || hay.includes("ac_input")) {
          return v === false;
        }

        if (
          hay.includes("bilge") ||
          hay.includes("battery") ||
          hay.includes("alarm") ||
          hay.includes("fault") ||
          hay.includes("smoke") ||
          hay.includes("fire") ||
          hay.includes("leak")
        ) {
          return v === true;
        }
        return false;
      }

      if (typeof v === "number") {
        if (hay.includes("fuel") || hay.includes("tank")) {
          return v <= 20 || v >= 95;
        }

        if (hay.includes("battery") && hay.includes("volt")) {
          return v < 11.5;
        }

        if (hay.includes("temp") || hay.includes("temperature")) {
          return v > 90;
        }
      }

      return false;
    }

    /* DEVICES & SENSORS */

    async function loadDevices() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/devices/`);
        if (!res.ok) throw new Error("Failed to load devices");
        const devices = await res.json();
        renderDevices(devices);
        renderSensors(devices);
        updateSummary(devices);

        const active = await loadActiveAlarms();
        updateAudibleAlarm(active.length);

        setLastAction("Devices refreshed");
      } catch (err) {
        console.error(err);
        setLastAction("Error loading devices");
      }
    }

    function updateSummary(devices) {
      const controllable = devices.filter(d => d.type !== "sensor" && !READONLY_IDS.has(d.id));
      const onCount  = controllable.filter(d => d.state === true).length;
      const pumpsOn  = controllable.filter(d => d.type === "pump" && d.state === true).length;
      const lightsOn = controllable.filter(d => d.type === "light" && d.state === true).length;
      summaryLineEl.textContent = `${onCount > 0 ? onCount : 0} outputs ON · ${lightsOn} lights · ${pumpsOn} pumps`;
    }

    function renderDevices(devices) {
      deviceContainer.innerHTML = "";

      const controls = devices
        .filter(dev => dev.type !== "sensor" && !READONLY_IDS.has(dev.id))
        .sort((a, b) => {
          if (a.zone === b.zone) return a.name.localeCompare(b.name);
          return a.zone.localeCompare(b.zone);
        });

      controls.forEach(dev => {
        const card = document.createElement("div");
        card.className = "device-card";

        const nameEl = document.createElement("div");
        nameEl.className = "device-name";
        nameEl.textContent = dev.name;

        const isOn = dev.state === true;
        const statePill = document.createElement("div");
        statePill.className = "state-pill btn-like " + (isOn ? "on" : "off");
        statePill.textContent = isOn ? "ON" : "OFF";
        statePill.addEventListener("click", () => {
          setDeviceState(dev.id, !isOn);
        });

        card.appendChild(nameEl);
        card.appendChild(statePill);
        deviceContainer.appendChild(card);
      });
    }

    function renderSensors(devices) {
      sensorContainer.innerHTML = "";

      const sensors = devices.filter(dev =>
        dev.type === "sensor" || READONLY_IDS.has(dev.id)
      );

      if (sensors.length === 0) {
        sensorContainer.textContent = "No sensors configured.";
        return;
      }

      sensors
        .sort((a, b) => {
          if (a.zone === b.zone) return a.name.localeCompare(b.name);
          return a.zone.localeCompare(b.zone);
        })
        .slice(0, 16)
        .forEach(dev => {
          const item = document.createElement("div");
          item.className = "sensor-item";

          const main = document.createElement("div");
          main.className = "sensor-main";

          const name = document.createElement("div");
          name.className = "sensor-name";
          name.textContent = dev.name;

          const meta = document.createElement("div");
          meta.className = "sensor-meta";
          meta.textContent = `${dev.zone} · ${dev.id}`;

          main.appendChild(name);
          main.appendChild(meta);

          const graphic = document.createElement("div");
          graphic.className = "sensor-graphic";

          const hay = ((dev.id || "") + " " + (dev.name || "")).toLowerCase();
          const isBoolean = typeof dev.state === "boolean";
          const isNumber  = typeof dev.state === "number";

          if (isNumber) {
            let raw = Number(dev.state) || 0;
            let level;

            if (hay.includes("battery") && hay.includes("volt")) {
              level = ((raw - 11) / 3) * 100;
            } else {
              level = raw;
            }
            if (!Number.isFinite(level)) level = 0;
            level = Math.max(0, Math.min(100, level));

            const bar = document.createElement("div");
            let barClass = "level-bar";
            if (hay.includes("fuel") || hay.includes("tank")) {
              barClass += " tank";
            } else if (hay.includes("battery")) {
              barClass += " battery";
            }
            bar.className = barClass;

            const fill = document.createElement("div");
            fill.className = "level-bar-fill";
            fill.style.width = `${level}%`;
            bar.appendChild(fill);
            graphic.appendChild(bar);
          } else if (isBoolean) {
            const boolDot = document.createElement("div");
            boolDot.className = "bool-dot " + (dev.state ? "on" : "off");
            graphic.appendChild(boolDot);
          }

          const state = document.createElement("div");
          state.className = "sensor-state";

          let text = "–";

          if (isBoolean && dev.state === true) {
            text = "ON";
            state.classList.add("on");
          } else if (isBoolean && dev.state === false) {
            text = "OFF";
          } else if (isNumber) {
            text = String(dev.state);
          } else if (dev.state !== null && dev.state !== undefined) {
            text = String(dev.state);
          }

          if (isDeviceInAlarmState(dev)) {
            state.classList.add("alarm");
          }

          state.textContent = text;

          if (!READONLY_IDS.has(dev.id)) {
            state.classList.add("btn-like");
            state.title = "Click to toggle test value";

            state.addEventListener("click", () => {
              let newVal;

              if (isBoolean || dev.state === null || dev.state === undefined) {
                newVal = !Boolean(dev.state);
              } else if (isNumber) {
                const current = Number(dev.state) || 0;

                if (dev.id.toLowerCase().includes("fuel") || dev.name.toLowerCase().includes("fuel")) {
                  if (current <= 20) {
                    newVal = 60;
                  } else if (current >= 95) {
                    newVal = 60;
                  } else {
                    newVal = 10;
                  }
                } else {
                  newVal = current > 50 ? 20 : 90;
                }
              } else {
                newVal = dev.state ? 0 : 1;
              }

              setSensorValue(dev.id, newVal);
            });
          }

          item.appendChild(main);
          item.appendChild(graphic);
          item.appendChild(state);
          sensorContainer.appendChild(item);
        });
    }

    async function setDeviceState(deviceId, newState) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/devices/${deviceId}/state`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ state: newState, source: "web_ui" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to set state: ${errText}`);
        }
        setLastAction(`Set ${deviceId} → ${newState ? "ON" : "OFF"}`);
        await loadDevices();
        await loadEvents();
        await loadAlarmEvents();
      } catch (err) {
        console.error(err);
        setLastAction(`Error setting ${deviceId}`);
      }
    }

    async function setSensorValue(deviceId, value) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/devices/${deviceId}/state`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ state: value, source: "web_ui_test" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to set sensor value: ${errText}`);
        }
        await loadDevices();
        await loadEvents();
        await loadAlarmEvents();
      } catch (err) {
        console.error(err);
        setLastAction(`Error setting ${deviceId}`);
      }
    }

    /* ALARM BANNER */

    async function acknowledgeAlarms() {
      if (!yachtId) return;
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/alarms/acknowledge`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "web_ui" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to acknowledge alarms: ${errText}`);
        }
        const data = await res.json();
        setLastAction(`Alarms acknowledged: ${data.acknowledged}`);
        await loadDevices();
        await loadAlarmEvents();
      } catch (err) {
        console.error(err);
        setLastAction("Error acknowledging alarms");
      }
    }

    async function loadActiveAlarms() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/alarms/active`);
        if (!res.ok) throw new Error("Failed to load active alarms");
        const alarms = await res.json();
        updateAlarmBannerFromAlarms(alarms);
        return alarms;
      } catch (err) {
        console.error(err);
        updateAlarmBannerFromAlarms([]);
        setLastAction("Error loading active alarms");
        return [];
      }
    }

    function updateAlarmBannerFromAlarms(alarms) {
      alarmBanner.classList.remove("ok","alarm");

      if (!alarms || alarms.length === 0) {
        alarmBanner.classList.add("ok");
        alarmBannerText.textContent = "No active alarms.";
        return;
      }

      alarmBanner.classList.add("alarm");
      alarmBannerText.textContent = alarms.map(a => a.name || a.device_id).join(" Â· ");
    }

    async function clearAlarmSensors() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/devices/`);
        if (!res.ok) throw new Error("Failed to load devices for clearing alarms");
        const devices = await res.json();

        const alarmish = devices.filter(d => isAlarmishSensor(d) && isDeviceInAlarmState(d));

        for (const d of alarmish) {
          if (typeof d.state === "boolean") {
            if (d.state) {
              await setSensorValue(d.id, false);
            }
          } else if (typeof d.state === "number") {
            await setSensorValue(d.id, 60);
          }
        }

        const clearRes = await controlFetch(`${apiBase}/yachts/${yachtId}/alarms/clear-cleared`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "web_ui" })
        });
        if (!clearRes.ok) {
          const errText = await clearRes.text();
          throw new Error(`Failed to clear acknowledged alarms: ${errText}`);
        }

        setLastAction("Test alarms cleared");
        await loadDevices();
        await loadAlarmEvents();
      } catch (err) {
        console.error(err);
        setLastAction("Error clearing alarms");
      }
    }

    /* SIMULATOR */

    function labelFromId(id) {
      return String(id || "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, ch => ch.toUpperCase());
    }

    async function loadSimulatorScenarios() {
      if (!simulatorScenariosEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/simulator/scenarios`);
        if (!res.ok) throw new Error("Failed to load simulator scenarios");
        const data = await res.json();
        renderSimulatorScenarios(data.scenarios || []);
      } catch (err) {
        console.error(err);
        simulatorScenariosEl.textContent = "Simulator unavailable.";
      }
    }

    function renderSimulatorScenarios(scenarios) {
      if (!simulatorScenariosEl) return;
      simulatorScenariosEl.innerHTML = "";

      if (!scenarios.length) {
        simulatorScenariosEl.textContent = "No simulator scenarios configured.";
        return;
      }

      scenarios.forEach(scenarioId => {
        const btn = document.createElement("button");
        btn.className = "scene-btn";
        btn.addEventListener("click", () => runSimulatorScenario(scenarioId));

        const name = document.createElement("div");
        name.className = "scene-name";
        name.textContent = labelFromId(scenarioId);

        const desc = document.createElement("div");
        desc.className = "scene-desc";
        desc.textContent = "Apply simulated state";

        btn.appendChild(name);
        btn.appendChild(desc);
        simulatorScenariosEl.appendChild(btn);
      });
    }

    async function runSimulatorScenario(scenarioId) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/simulator/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario: scenarioId })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to run scenario: ${errText}`);
        }
        setLastAction(`Simulator: ${labelFromId(scenarioId)}`);
        await loadVesselMode();
        await loadDevices();
        await loadEvents();
        await loadAlarmEvents();
        await loadAiDashboard();
      } catch (err) {
        console.error(err);
        setLastAction(`Error running ${scenarioId}`);
      }
    }

    /* SCENES */

    async function loadScenes() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/scenes/`);
        if (!res.ok) throw new Error("Failed to load scenes");
        const scenes = await res.json();
        renderScenes(scenes);
      } catch (err) {
        console.error(err);
        setLastAction("Error loading scenes");
      }
    }

    function renderScenes(scenes) {
      if (!sceneButtons) return;
      sceneButtons.innerHTML = "";
      scenes.forEach(scene => {
        const btn = document.createElement("button");
        btn.className = "scene-btn";
        btn.addEventListener("click", () => activateScene(scene.id, scene.name));

        const name = document.createElement("div");
        name.className = "scene-name";
        name.textContent = scene.name;

        const desc = document.createElement("div");
        desc.className = "scene-desc";
        desc.textContent = scene.description || scene.id;

        btn.appendChild(name);
        btn.appendChild(desc);
        sceneButtons.appendChild(btn);
      });
    }

    async function activateScene(sceneId, sceneName) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/scenes/${sceneId}/activate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "web_ui" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to activate scene: ${errText}`);
        }
        setLastAction(`Scene: ${sceneName}`);
        if (MODE_BY_SCENE[sceneId]) updateModePills(MODE_BY_SCENE[sceneId]);
        await loadDevices();
        await loadEvents();
        await loadAlarmEvents();
      } catch (err) {
        console.error(err);
        setLastAction(`Error activating scene: ${sceneName}`);
      }
    }

    /* EVENTS HISTORY */

    async function loadEvents() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/events/?limit=50`);
        if (!res.ok) throw new Error("Failed to load events");
        const events = await res.json();
        renderEvents(events);
      } catch (err) {
        console.error(err);
        setLastAction("Error loading events");
      }
    }

    function renderEvents(events) {
      if (!eventsList) return;
      eventsList.innerHTML = "";
      events.slice(0, 15).forEach(ev => {
        const item = document.createElement("div");
        item.className = "event-item";

        const ts = new Date(ev.timestamp).toLocaleTimeString();

        const meta = document.createElement("div");
        meta.className = "event-meta";
        meta.innerHTML = `<span class="event-type">${ev.type}</span> · ${ts} · ${ev.source}`;

        const detailsDiv = document.createElement("div");
        detailsDiv.className = "event-details";
        detailsDiv.textContent = JSON.stringify(ev.details);

        item.appendChild(meta);
        item.appendChild(detailsDiv);
        eventsList.appendChild(item);
      });
    }

    async function loadAlarmEvents() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/alarms/history?limit=200`);
        if (!res.ok) throw new Error("Failed to load alarm events");
        const alarms = await res.json();
        renderAlarmEvents(alarms);
      } catch (err) {
        console.error(err);
        setLastAction("Error loading alarm history");
        renderAlarmEvents([]);
      }
    }

    function renderAlarmEvents(alarms) {
      alarmsList.innerHTML = "";
      if (!alarms || alarms.length === 0) {
        alarmsList.textContent = "No alarm events in recent history.";
        return;
      }

      alarms
        .slice(0, 120)
        .forEach(ev => {
          const item = document.createElement("div");
          item.className = "event-item";

          const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "–";

          const meta = document.createElement("div");
          meta.className = "event-meta";

          const typeLabel = document.createElement("span");
          typeLabel.className = "event-type";
          typeLabel.textContent = ev.type || "ALARM";

          const tag = document.createElement("span");
          const isClear = String(ev.type || "").toLowerCase().includes("clear");
          tag.className = "alarm-tag" + (isClear ? " clear" : "");
          tag.textContent = isClear ? "CLEAR" : "ALARM";

          meta.appendChild(typeLabel);
          meta.appendChild(tag);
          meta.insertAdjacentText("beforeend", ` · ${ts} · ${ev.source || "–"}`);

          const details = document.createElement("div");
          details.className = "event-details";
          details.textContent = JSON.stringify(ev.details || {});

          item.appendChild(meta);
          item.appendChild(details);
          alarmsList.appendChild(item);
        });
    }

    /* AI WATCHKEEPER DASHBOARD */

    async function loadAiDashboard() {
      if (!yachtId) return;
      await Promise.all([
        loadAiStatus(),
        loadAiSuggestions(),
        loadAiIncidents(),
        loadAiMaintenance(),
        loadAiSafetyExplanations(),
        loadAiLogs()
      ]);
    }

    async function loadAiStatus() {
      if (!aiStatusSummaryEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/status`);
        if (!res.ok) throw new Error("Failed to load AI status");
        const data = await res.json();
        renderAiStatus(data);
      } catch (err) {
        console.error(err);
        renderAiStatus(null);
      }
    }

    function renderAiStatus(status) {
      if (!aiStatusSummaryEl) return;
      aiStatusSummaryEl.innerHTML = "";
      const item = document.createElement("div");
      item.className = "event-item ai-panel";

      const meta = document.createElement("div");
      meta.className = "event-meta";
      meta.textContent = "AI Status";

      const details = document.createElement("div");
      details.className = "event-details";
      if (!status) {
        details.textContent = "AI status unavailable.";
      } else {
        details.textContent =
          `Risk: ${status.risk_level} | Mode: ${status.mode} | Occupancy: ${status.occupancy}\n` +
          status.headline;
      }

      item.appendChild(meta);
      item.appendChild(details);
      aiStatusSummaryEl.appendChild(item);
    }

    async function loadAiIncidents() {
      if (!aiIncidentsEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/incidents?limit=8`);
        if (!res.ok) throw new Error("Failed to load AI incidents");
        const data = await res.json();
        renderAiIncidents(data.incidents || []);
      } catch (err) {
        console.error(err);
        renderAiIncidents([]);
      }
    }

    function renderAiIncidents(incidents) {
      renderAiList(aiIncidentsEl, "Incident Reports", incidents, "No recent AI incident reports.", incident => {
        const checks = (incident.recommended_checks || []).join(" | ");
        return `${incident.title}: ${incident.summary}\nLikely cause: ${incident.likely_cause}\nChecks: ${checks}`;
      });
    }

    async function loadAiMaintenance() {
      if (!aiMaintenanceEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/maintenance`);
        if (!res.ok) throw new Error("Failed to load AI maintenance");
        const data = await res.json();
        renderAiMaintenance(data.alerts || []);
      } catch (err) {
        console.error(err);
        renderAiMaintenance([]);
      }
    }

    function renderAiMaintenance(alerts) {
      renderAiList(aiMaintenanceEl, "Maintenance Intelligence", alerts, "No maintenance alerts.", alert => {
        return `${alert.title}: ${alert.reason}\nAction: ${alert.recommended_action}`;
      });
    }

    async function loadAiSafetyExplanations() {
      if (!aiSafetyEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/safety-explanations?limit=8`);
        if (!res.ok) throw new Error("Failed to load safety explanations");
        const data = await res.json();
        renderAiSafetyExplanations(data.explanations || []);
      } catch (err) {
        console.error(err);
        renderAiSafetyExplanations([]);
      }
    }

    function renderAiSafetyExplanations(explanations) {
      renderAiList(aiSafetyEl, "Safety Explainer", explanations, "No recent automatic safety actions.", item => {
        const state = item.state ? "ON" : "OFF";
        return `${item.device_id} -> ${state}: ${item.reason}`;
      });
    }

    function renderAiList(container, title, items, emptyText, detailBuilder) {
      if (!container) return;
      container.innerHTML = "";
      const header = document.createElement("div");
      header.className = "event-meta ai-section-title";
      header.textContent = title;
      container.appendChild(header);

      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "event-item";
        empty.textContent = emptyText;
        container.appendChild(empty);
        return;
      }

      items.slice(0, 8).forEach(itemData => {
        const item = document.createElement("div");
        item.className = "event-item";

        const meta = document.createElement("div");
        meta.className = "event-meta";
        meta.textContent = itemData.severity || itemData.status || itemData.source || "info";

        const details = document.createElement("div");
        details.className = "event-details";
        details.textContent = detailBuilder(itemData);

        item.appendChild(meta);
        item.appendChild(details);
        container.appendChild(item);
      });
    }

    /* AI SUGGESTIONS */

    async function loadAiSuggestions() {
      if (!aiSuggestionsEl || !yachtId) return;
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/suggestions`);
        if (!res.ok) throw new Error("Failed to load AI suggestions");
        const data = await res.json();
        renderAiSuggestions(data.suggestions || []);
      } catch (err) {
        console.error(err);
        renderAiSuggestions([]);
      }
    }

    function renderAiSuggestions(suggestions) {
      if (!aiSuggestionsEl) return;
      aiSuggestionsEl.innerHTML = "";

      const header = document.createElement("div");
      header.className = "event-meta ai-section-title";
      header.textContent = "Ranked Recommendations";
      aiSuggestionsEl.appendChild(header);

      if (!suggestions.length) {
        const empty = document.createElement("div");
        empty.className = "event-item";
        empty.textContent = "No pending AI suggestions.";
        aiSuggestionsEl.appendChild(empty);
        return;
      }

      suggestions.forEach(suggestion => {
        const item = document.createElement("div");
        item.className = "event-item";

        const meta = document.createElement("div");
        meta.className = "event-meta";
        const confidence = Math.round((suggestion.confidence || 0) * 100);
        meta.innerHTML = `<span class="event-type">Suggestion</span> - ${suggestion.severity || suggestion.priority || "normal"} - ${confidence}%`;

        const details = document.createElement("div");
        details.className = "event-details";
        details.textContent =
          `${suggestion.title || suggestion.id}: ${suggestion.reason || ""}\n` +
          `Impact: ${suggestion.impact || "Review recommended."}`;

        item.appendChild(meta);
        item.appendChild(details);

        if (suggestion.approveable && suggestion.action) {
          const approve = document.createElement("button");
          approve.className = "small-btn";
          approve.textContent = "Approve";
          approve.addEventListener("click", () => approveAiSuggestion(suggestion.id));
          item.appendChild(approve);
        }

        aiSuggestionsEl.appendChild(item);
      });
    }

    async function approveAiSuggestion(suggestionId) {
      try {
        const res = await controlFetch(`${apiBase}/yachts/${yachtId}/ai/suggestions/${encodeURIComponent(suggestionId)}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "web_ui" })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Failed to approve suggestion: ${errText}`);
        }
        const result = await res.json();
        const executed = result.results ? result.results.filter(r => r.status === "executed").length : 0;
        setLastAction(`AI suggestion approved: ${executed} executed`);
        await loadDevices();
        await loadEvents();
        await loadAlarmEvents();
        await loadAiDashboard();
      } catch (err) {
        console.error(err);
        setLastAction("Error approving AI suggestion");
      }
    }

    /* AI LOGS */

    async function loadAiLogs() {
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/logs?limit=50`);
          if (!res.ok) throw new Error("Failed to load AI logs");
          const logs = await res.json();
          renderAiLogs(logs);
          setLastAction("AI logs refreshed");
      } catch (err) {
        console.error(err);
        setLastAction("Error loading AI logs");
      }
    }

    function renderAiLogs(logs) {
      if (!aiLogsEl) return;
      aiLogsEl.innerHTML = "";

      logs.forEach(log => {
        const item = document.createElement("div");
        item.className = "event-item";

        const ts = new Date(log.generated_at).toLocaleString();
        const mode = log.mode ? ` · ${log.mode}` : "";

        const meta = document.createElement("div");
        meta.className = "event-meta";
        meta.innerHTML = `<span class="event-type">AI</span> · ${ts}${mode}`;

        const details = document.createElement("div");
        details.className = "event-details";
        details.textContent = log.summary || "";

        item.appendChild(meta);
        item.appendChild(details);
        aiLogsEl.appendChild(item);
      });

      if (logs.length === 0) {
        const empty = document.createElement("div");
        empty.className = "event-item";
        empty.textContent = "No AI logs yet.";
        aiLogsEl.appendChild(empty);
      }
    }

    /* AI CHAT */

    function addChatMessage(who, text) {
      if (!aiChatMessages) return;
      const item = document.createElement("div");
      item.className = "event-item";

      const meta = document.createElement("div");
      meta.className = "event-meta";
      meta.textContent = who;

      const details = document.createElement("div");
      details.className = "event-details";
      details.textContent = text;

      item.appendChild(meta);
      item.appendChild(details);

      aiChatMessages.prepend(item);
    }

    function isStatusQuestionText(text) {
      const lower = text.toLowerCase();
      return (
        lower.includes("status") ||
        lower.includes("health") ||
        lower.includes("what is wrong") ||
        lower.includes("what's wrong") ||
        lower.includes("anything wrong") ||
        lower.includes("battery ok") ||
        lower.includes("battery okay")
      );
    }

    function isNaturalLanguageControlText(text) {
      const lower = text.toLowerCase();
      return (
        lower.includes("turn on") ||
        lower.includes("turn off") ||
        lower.includes("switch on") ||
        lower.includes("switch off") ||
        lower.includes("enable") ||
        lower.includes("disable") ||
        lower.includes("activate") ||
        lower.includes("set mode") ||
        lower.includes("acknowledge alarm") ||
        lower.includes("ack alarm") ||
        lower.includes("clear alarm") ||
        lower.includes("start ") ||
        lower.includes("stop ")
      );
    }

    async function answerStatusQuestion() {
      const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/status`);
      if (!res.ok) throw new Error("Failed to load AI status");
      const status = await res.json();
      let reply = `${status.headline} Mode is ${status.mode}. Risk is ${status.risk_level}.`;
      if (status.risk_items && status.risk_items.length) {
        reply += ` Top issue: ${status.risk_items[0].title} - ${status.risk_items[0].reason}`;
      } else if (status.maintenance_alerts && status.maintenance_alerts.length) {
        reply += ` Maintenance: ${status.maintenance_alerts[0].title} - ${status.maintenance_alerts[0].reason}`;
      }
      addChatMessage("AI", reply);
      await loadAiDashboard();
    }

    async function sendNaturalLanguageControl(text) {
      const res = await controlFetch(`${apiBase}/yachts/${yachtId}/ai/nl-command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, source: "web_ui", execute: true })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Failed to run natural language command");
      }
      const data = await res.json();
      addChatMessage("AI Command", data.reply || JSON.stringify(data));
      setLastAction(`AI command: ${data.status}`);
      await loadVesselMode();
      await loadDevices();
      await loadEvents();
      await loadAlarmEvents();
      await loadAiDashboard();
    }

    async function sendAiChat() {
      if (!aiChatInput || !yachtId) return;
      const text = aiChatInput.value.trim();
      if (!text) return;

      aiChatInput.value = "";
      addChatMessage("You", text);

      try {
        if (isStatusQuestionText(text)) {
          await answerStatusQuestion();
          return;
        }

        if (isNaturalLanguageControlText(text)) {
          await sendNaturalLanguageControl(text);
          return;
        }

        const res = await fetch(`${apiBase}/yachts/${yachtId}/ai/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || "Failed to talk to AI");
        }
        const data = await res.json();
        addChatMessage("AI", data.reply);
        setLastAction("AI chat reply received");
      } catch (err) {
        console.error(err);
        addChatMessage("System", "Error talking to AI: " + err.message);
        setLastAction("AI chat error");
      }
    }

    /* YACHT SELECTOR */

    async function loadYachtsAndInitSelection() {
      try {
        const res = await fetch(`${apiBase}/yachts/`);
        if (!res.ok) throw new Error("Failed to load yachts");
        const yachts = await res.json();

        yachtSelectEl.innerHTML = "";

        if (!Array.isArray(yachts) || yachts.length === 0) {
          const opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "No yachts configured";
          yachtSelectEl.appendChild(opt);
          setLastAction("No yachts in registry");
          return;
        }

        const params = new URLSearchParams(window.location.search);
        const urlYacht = params.get("yacht");

        let initial = yachts[0];
        if (urlYacht) {
          const found = yachts.find(y => y.id === urlYacht);
          if (found) initial = found;
        }

        yachts.forEach(y => {
          const opt = document.createElement("option");
          opt.value = y.id;
          opt.textContent = `${y.name} (${y.id})`;
          if (y.id === initial.id) opt.selected = true;
          yachtSelectEl.appendChild(opt);
        });

        await selectYacht(initial.id);

        yachtSelectEl.addEventListener("change", async () => {
          const newId = yachtSelectEl.value;
          await selectYacht(newId);
        });
      } catch (err) {
        console.error(err);
        setLastAction("Error loading yachts");
      }
    }

    async function selectYacht(newYachtId) {
      yachtId = newYachtId;
      window.history.replaceState({}, "", `?yacht=${encodeURIComponent(yachtId)}`);

      // Load meta for pretty name
      try {
        const res = await fetch(`${apiBase}/yachts/${yachtId}/meta`);
        if (res.ok) {
          yachtMeta = await res.json();
          yachtNameEl.textContent = yachtMeta.id;
          yachtTitleEl.textContent = yachtMeta.name;
        } else {
          yachtMeta = null;
          yachtNameEl.textContent = yachtId;
          yachtTitleEl.textContent = "Boat Control Panel";
        }
      } catch (err) {
        console.error(err);
        yachtMeta = null;
        yachtNameEl.textContent = yachtId;
        yachtTitleEl.textContent = "Boat Control Panel";
      }

      await loadDevices();
      await loadScenes();
      await loadVesselMode();
      await loadSimulatorScenarios();
      await loadEvents();
      await loadAlarmEvents();
      await loadAiDashboard();
      sendOccupancyToBackend();
      setLastAction(`Switched to yacht ${yachtId}`);
    }

    /* INIT */

    (async function init() {
      await loadYachtsAndInitSelection();
    })();

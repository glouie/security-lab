import os, json, time, threading
import requests as req
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from lessons import LESSONS

app = Flask(__name__, static_folder="static", static_url_path="")
sio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ATTACKER = os.environ.get("ATTACKER_URL", "http://172.20.0.20:5001")
VICTIM   = os.environ.get("VICTIM_URL",   "http://172.20.0.10:8080")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/lessons")
def get_lessons():
    return jsonify(LESSONS)

@app.route("/mitm-event", methods=["POST"])
def mitm_event():
    sio.emit("mitm_capture", request.get_json(silent=True) or {})
    return "", 204

@sio.on("execute")
def handle_execute(data):
    action, params, sid = data.get("action"), data.get("params", {}), request.sid
    def run():
        try:
            r = req.post(f"{ATTACKER}/attack/{action}", json=params, timeout=30)
            for line in r.json().get("lines", []):
                sio.emit("terminal_line", line, to=sid)
                time.sleep(0.08)
            sio.emit("execute_done", {"action": action}, to=sid)
        except Exception as e:
            sio.emit("terminal_line", {"panel": "wire", "line": f"Error: {e}", "style": "red"}, to=sid)
            sio.emit("execute_done", {"action": action, "error": str(e)}, to=sid)
    threading.Thread(target=run, daemon=True).start()

@sio.on("set_config")
def handle_config(data):
    try:
        r = req.post(f"{VICTIM}/admin/config", json=data, timeout=5)
        sio.emit("config_updated", r.json(), to=request.sid)
    except Exception as e:
        sio.emit("config_updated", {"error": str(e)}, to=request.sid)

@sio.on("reset")
def handle_reset(data=None):
    try:
        req.post(f"{ATTACKER}/reset", timeout=5)
        sio.emit("reset_done", {}, to=request.sid)
    except Exception as e:
        sio.emit("reset_done", {"error": str(e)}, to=request.sid)

@sio.on("get_state")
def handle_state(data=None):
    try:
        r = req.get(f"{VICTIM}/admin/state", timeout=3)
        sio.emit("server_state", r.json(), to=request.sid)
    except Exception as e:
        sio.emit("server_state", {"error": str(e)}, to=request.sid)

@sio.on("connect")
def on_connect():
    emit("connected", {"msg": "Dashboard ready"})

if __name__ == "__main__":
    sio.run(app, host="0.0.0.0", port=3000, debug=False, allow_unsafe_werkzeug=True)

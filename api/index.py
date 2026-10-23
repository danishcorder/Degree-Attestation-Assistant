
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Loads .env locally if python-dotenv is installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

XAI_URL = "https://api.x.ai/v1"
MODEL = "grok-4.7"


def api_request(path, payload=None):
    key = os.environ.get("XAI_API_KEY")

    if not key:
        raise RuntimeError("XAI_API_KEY is not configured.")

    data = json.dumps(payload).encode() if payload is not None else None

    req = Request(
        XAI_URL + path,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST" if data is not None else "GET",
    )

    with urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode())


class handler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # A real test: call xAI with your key.
        try:
            result = api_request("/models")
            models = [m["id"] for m in result.get("data", [])]
            self.send_json(200, {
                "ok": True,
                "api_key": "valid",
                "model_available": MODEL in models,
                "model": MODEL,
                "message": (
                    "API key works."
                    if MODEL in models
                    else "Key works, but check model availability."
                ),
            })
        except HTTPError as e:
            self.send_json(502, {
                "ok": False,
                "message": f"xAI returned HTTP {e.code}. Check your key and account."
            })
        except Exception:
            self.send_json(500, {
                "ok": False,
                "message": "API test failed. Check server configuration and logs."
            })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10000:
                return self.send_json(400, {"error": "Invalid request size."})

            body = json.loads(self.rfile.read(length))
            message = str(body.get("message", "")).strip()

            if not message:
                return self.send_json(400, {"error": "Enter a message."})

            if len(message) > 4000:
                return self.send_json(400, {"error": "Message is too long."})

            result = api_request("/chat/completions", {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an independent HEC Degree Attestation "
                            "information assistant in Pakistan. Explain things "
                            "simply. Never claim to be an official HEC agent. "
                            "Do not invent official rules, fees or application "
                            "status. Direct users to official HEC sources when "
                            "uncertain. Never request passwords or OTPs."
                        )
                    },
                    {"role": "user", "content": message},
                ],
            })

            reply = result["choices"][0]["message"]["content"]
            self.send_json(200, {"reply": reply})

        except HTTPError as e:
            # Keep API credentials and provider error details private.
            self.send_json(502, {
                "error": f"xAI request failed (HTTP {e.code})."
            })
        except (URLError, TimeoutError):
            self.send_json(502, {"error": "Could not reach xAI. Try again."})
        except Exception:
            self.send_json(500, {"error": "Server error. Check deployment logs."})

    def log_message(self, format, *args):
        # Avoid logging request details unnecessarily.
        pass

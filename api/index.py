import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


GROQ_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
FREE_MODELS = {
    "openai/gpt-oss-20b": "GPT OSS 20B",
    "openai/gpt-oss-120b": "GPT OSS 120B",
    "qwen/qwen3.8-27b": "Qwen 3.8 27B",
}
MAX_BODY_SIZE = 20_000
MAX_MESSAGE_LENGTH = 4_000
HTTP_STATUSES = {
    200: "200 OK",
    400: "400 Bad Request",
    405: "405 Method Not Allowed",
    413: "413 Request Entity Too Large",
    415: "415 Unsupported Media Type",
    429: "429 Too Many Requests",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
}


def api_request(path, payload=None):
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not configured.")

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        GROQ_URL + path,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST" if data is not None else "GET",
    )

    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def json_response(start_response, status, data, extra_headers=None):
    body = json.dumps(data).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    start_response(HTTP_STATUSES[status], headers)
    return [body]


def get_status(start_response):
    configured_model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
    try:
        result = api_request("/models")
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ValueError("Invalid models response.")
        available_ids = {
            item.get("id")
            for item in result["data"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        models = [
            {"id": model_id, "name": name}
            for model_id, name in FREE_MODELS.items()
            if model_id in available_ids
        ]
        model = next(
            (item["id"] for item in models if item["id"] == configured_model),
            models[0]["id"] if models else None,
        )
        available = bool(models)
        return json_response(start_response, 200 if available else 503, {
            "ok": available,
            "model": model,
            "models": models,
            "message": (
                "Groq connection is ready."
                if available
                else "The Groq key works, but no supported free chat models are available."
            ),
        })
    except RuntimeError:
        return json_response(start_response, 503, {
            "ok": False,
            "message": "XAI_API_KEY is not configured in the server environment.",
        })
    except HTTPError as error:
        return json_response(start_response, 502, {
            "ok": False,
            "message": f"Groq rejected the model check (HTTP {error.code}). Verify the key and account.",
        })
    except (URLError, TimeoutError):
        return json_response(start_response, 502, {
            "ok": False,
            "message": "Could not reach Groq. Please try again.",
        })
    except (ValueError, KeyError, TypeError):
        return json_response(start_response, 502, {
            "ok": False,
            "message": "Groq returned an unexpected response.",
        })


def post_message(environ, start_response):
    content_type = environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip()
    if content_type != "application/json":
        return json_response(start_response, 415, {
            "error": "Send the message as JSON.",
        })

    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        return json_response(start_response, 400, {"error": "Invalid request size."})

    if length <= 0:
        return json_response(start_response, 400, {"error": "Invalid request size."})
    if length > MAX_BODY_SIZE:
        return json_response(start_response, 413, {"error": "Request is too large."})

    try:
        body = json.loads(environ["wsgi.input"].read(length))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return json_response(start_response, 400, {
            "error": "Request body must be valid JSON.",
        })

    if not isinstance(body, dict):
        return json_response(start_response, 400, {
            "error": "Request body must be a JSON object.",
        })

    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return json_response(start_response, 400, {"error": "Enter a message."})

    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        return json_response(start_response, 400, {"error": "Message is too long."})

    model = body.get("model", os.environ.get("GROQ_MODEL", DEFAULT_MODEL))
    if not isinstance(model, str) or model not in FREE_MODELS:
        return json_response(start_response, 400, {
            "error": "Choose a supported free model.",
        })

    try:
        result = api_request("/chat/completions", {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an independent HEC Degree Attestation "
                        "information assistant in Pakistan. Explain things "
                        "simply. Never claim to be an official HEC agent. "
                        "Do not invent official rules, fees, timelines, or "
                        "application status. Direct users to official HEC "
                        "sources when uncertain. Never request passwords, "
                        "one-time codes, or other sensitive credentials."
                    ),
                },
                {"role": "user", "content": message},
            ],
            "temperature": 0.4,
            "max_tokens": 700,
        })

        reply = result["choices"][0]["message"]["content"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("Groq returned an empty reply.")
        return json_response(start_response, 200, {"reply": reply.strip()})
    except RuntimeError:
        return json_response(start_response, 503, {
            "error": "XAI_API_KEY is not configured in the server environment.",
        })
    except HTTPError as error:
        if error.code == 429:
            return json_response(start_response, 429, {
                "error": "Groq's free-tier limit was reached. Please try again later.",
            })
        if error.code in (401, 403):
            return json_response(start_response, 502, {
                "error": "Groq rejected the API key. Check XAI_API_KEY in Vercel and confirm it contains a Groq API key.",
            })
        if error.code == 404:
            return json_response(start_response, 502, {
                "error": "The configured Groq model is unavailable. Check GROQ_MODEL.",
            })
        return json_response(start_response, 502, {
            "error": f"Groq request failed (HTTP {error.code}).",
        })
    except (URLError, TimeoutError):
        return json_response(start_response, 502, {
            "error": "Could not reach Groq. Please try again.",
        })
    except (ValueError, KeyError, IndexError, TypeError):
        return json_response(start_response, 502, {
            "error": "Groq returned an unexpected response.",
        })


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if method == "GET":
        return get_status(start_response)
    if method == "POST":
        return post_message(environ, start_response)
    return json_response(
        start_response,
        405,
        {"error": "Method not allowed."},
        [("Allow", "GET, POST")],
    )

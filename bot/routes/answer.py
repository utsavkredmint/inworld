import logging
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from config import SERVER_URL
from database import get_call_by_uuid, update_call

log = logging.getLogger(__name__)
router = APIRouter()


@router.api_route("/api/plivo/answer", methods=["GET", "POST"], response_class=PlainTextResponse)
async def plivo_answer(request: Request):
    log.info(f"[ANSWER] Incoming request from Plivo: {request.method}")
    
    # Try to get params from query string or form data
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            form_data = await request.form()
            params.update(dict(form_data))
        except Exception as e:
            log.warning(f"[ANSWER] Could not parse form data: {e}")
            
    call_uuid = params.get("CallUUID", "unknown")
    to_number = params.get("To", "").replace(" ", "+")
    ws_url = SERVER_URL.replace("https://", "wss://").replace("http://", "ws://")

    # Look up call_id from DB (if triggered via API)
    call_id = ""
    db_call = get_call_by_uuid(call_uuid)
    if db_call:
        call_id = db_call["id"]
        log.info(f"[ANSWER] Matched call_id={call_id} for CallUUID={call_uuid}")

    stream_url = f"{ws_url}/api/plivo/stream?call_uuid={call_uuid}&amp;call_id={call_id}&amp;to_number={to_number}"

    xml = f"""<Response><Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">{stream_url}</Stream></Response>"""

    log.info(f"[ANSWER] XML: {xml[:200]}")

    return PlainTextResponse(xml, media_type="application/xml")


@router.api_route("/api/plivo/record_callback", methods=["GET", "POST"])
async def record_callback(request: Request):
    """Plivo sends recording URL here after call ends."""
    import json
    from urllib.parse import parse_qs, unquote

    params = dict(request.query_params)
    call_id = params.get("call_id", "")
    recording_url = ""

    try:
        body_raw = (await request.body()).decode()
        log.info(f"[RECORD-CB] Raw body: {body_raw[:400]}")

        # Parse URL-encoded body: call_id=X&response=<url-encoded-json>
        parsed = parse_qs(body_raw)

        # Plivo nests recording info inside a "response" field as JSON
        response_str = parsed.get("response", [""])[0]
        if response_str:
            response_data = json.loads(unquote(response_str))
            recording_url = response_data.get("record_url", "") or response_data.get("RecordUrl", "")
            log.info(f"[RECORD-CB] Parsed response JSON: {response_data}")

        # Also check direct fields
        if not recording_url:
            recording_url = (
                parsed.get("record_url", [""])[0]
                or parsed.get("RecordUrl", [""])[0]
                or parsed.get("RecordingUrl", [""])[0]
            )
    except Exception as e:
        log.error(f"[RECORD-CB] Parse error: {e}")

    if call_id and recording_url:
        update_call(call_id, recording_url=recording_url)
        log.info(f"[RECORD] Recording saved for call {call_id}: {recording_url[:100]}")
    else:
        log.warning(f"[RECORD] Missing data — call_id={call_id}, recording_url={recording_url[:50] if recording_url else 'EMPTY'}")

    return {"status": "ok"}

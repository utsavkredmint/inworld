import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from plivo import RestClient
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_NUMBER, SERVER_URL
from database import (
    create_agent, get_agent, list_agents, update_agent, delete_agent,
    create_call, get_call, get_call_by_uuid, list_calls, update_call,
    get_messages,
    create_campaign, list_campaigns, get_campaign, update_campaign_status, 
    delete_campaign, add_campaign_contacts, get_next_pending_contact, update_contact_status
)
import asyncio

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard")
plivo_client = RestClient(auth_id=PLIVO_AUTH_ID, auth_token=PLIVO_AUTH_TOKEN)


# ── Request Models ──

class CreateAgentRequest(BaseModel):
    name: str
    greeting: str
    system_prompt: str
    persona: str = ""
    voice: str = "Riya"
    language: str = "hi"


class TriggerCallRequest(BaseModel):
    agent_id: str
    phone_number: str


class CampaignContact(BaseModel):
    phone_number: str
    name: Optional[str] = None


class CreateCampaignRequest(BaseModel):
    name: str
    agent_id: str
    contacts: list[CampaignContact]


# ── Agent Endpoints ──

@router.post("/agents")
async def api_create_agent(req: CreateAgentRequest):
    agent = create_agent(
        name=req.name,
        greeting=req.greeting,
        system_prompt=req.system_prompt,
        persona=req.persona,
        voice=req.voice,
        language=req.language,
    )
    log.info(f"[API] Agent created: {agent['id']} ({agent['name']})")
    return agent


@router.get("/agents")
async def api_list_agents():
    agents = list_agents()
    return {"agents": agents}


@router.get("/agents/{agent_id}")
async def api_get_agent(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    return agent


@router.put("/agents/{agent_id}")
async def api_update_agent(agent_id: str, req: CreateAgentRequest):
    agent = get_agent(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    updated = update_agent(
        agent_id,
        name=req.name,
        greeting=req.greeting,
        system_prompt=req.system_prompt,
        persona=req.persona,
        voice=req.voice,
        language=req.language,
    )
    return updated


@router.delete("/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    delete_agent(agent_id)
    log.info(f"[API] Agent deleted: {agent_id}")
    return {"status": "deleted"}


# ── Campaign Endpoints ──

@router.get("/campaigns")
async def api_list_campaigns():
    campaigns = list_campaigns()
    return {"campaigns": campaigns}


@router.post("/campaigns")
async def api_create_campaign(req: CreateCampaignRequest):
    agent = get_agent(req.agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    
    # Create campaign
    campaign = create_campaign(req.name, req.agent_id)
    
    # Add contacts
    contacts_data = [{"phone_number": c.phone_number, "name": c.name} for c in req.contacts]
    add_campaign_contacts(campaign["id"], contacts_data)
    
    # Start background runner
    asyncio.create_task(run_campaign(campaign["id"]))
    
    return campaign


@router.put("/campaigns/{campaign_id}/status")
async def api_update_campaign_status(campaign_id: str, req: dict):
    status = req.get("status")
    if status not in ["running", "paused", "completed"]:
        return JSONResponse(status_code=400, content={"error": "Invalid status"})
    
    update_campaign_status(campaign_id, status)
    if status == "running":
        asyncio.create_task(run_campaign(campaign_id))
    
    return {"status": status}


@router.delete("/campaigns/{campaign_id}")
async def api_delete_campaign(campaign_id: str):
    delete_campaign(campaign_id)
    return {"status": "deleted"}


async def run_campaign(campaign_id: str):
    """Background worker to process campaign contacts."""
    log.info(f"[CAMPAIGN] Starting runner for {campaign_id}")
    
    while True:
        # Check if campaign is still running
        campaign = get_campaign(campaign_id)
        if not campaign or campaign["status"] != "running":
            log.info(f"[CAMPAIGN] Runner stopped for {campaign_id} (status: {campaign['status'] if campaign else 'deleted'})")
            break
        
        # Get next pending contact
        contact = get_next_pending_contact(campaign_id)
        if not contact:
            # All done!
            update_campaign_status(campaign_id, "completed")
            log.info(f"[CAMPAIGN] Completed: {campaign_id}")
            break
        
        # Trigger call
        agent_id = campaign["agent_id"]
        phone_number = contact["phone_number"]
        
        log.info(f"[CAMPAIGN] Calling {phone_number} ({contact['name']}) for campaign {campaign_id}")
        
        try:
            # Reusing triggering logic
            call_res = await trigger_outbound_call(agent_id, phone_number)
            update_contact_status(contact["id"], "completed", call_id=call_res["id"])
        except Exception as e:
            log.error(f"[CAMPAIGN] Call failed for {phone_number}: {e}")
            update_contact_status(contact["id"], "failed")
            
        # Throttling between calls (e.g., 5 seconds)
        await asyncio.sleep(5)


async def trigger_outbound_call(agent_id, phone_number):
    """Helper to trigger an outbound call (extracted from api_trigger_call)."""
    call = create_call(agent_id=agent_id, phone_number=phone_number)
    try:
        response = plivo_client.calls.create(
            from_=PLIVO_NUMBER,
            to_=phone_number,
            answer_url=f"{SERVER_URL}/api/plivo/answer",
            answer_method="GET",
        )
        call_uuid = response.request_uuid if hasattr(response, 'request_uuid') else str(response)
        update_call(call["id"], call_uuid=call_uuid, status="ringing")
        call["call_uuid"] = call_uuid
        call["status"] = "ringing"
        
        # Pre-setup STT + TTS + Greeting
        from call_sessions import prepare_session
        agent = get_agent(agent_id)
        if agent:
            asyncio.create_task(prepare_session(
                call["id"], 
                greeting=agent["greeting"], 
                voice_id=agent["voice"], 
                language=agent["language"]
            ))
        else:
            asyncio.create_task(prepare_session(call["id"]))
        
        return call
    except Exception as e:
        update_call(call["id"], status="failed")
        raise e


# ── Call Endpoints ──

@router.post("/calls")
async def api_trigger_call(req: TriggerCallRequest):
    try:
        call = await trigger_outbound_call(req.agent_id, req.phone_number)
        return call
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/calls")
async def api_list_calls(agent_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    calls, total = list_calls(agent_id=agent_id, limit=limit, offset=offset)
    
    # Transform metadata for frontend: replace -1 with 'not_provided'
    import json
    for call in calls:
        meta_raw = call.get("metadata", "{}")
        try:
            meta = json.loads(meta_raw)
            if "stock" in meta:
                for k, v in meta["stock"].items():
                    if v == -1:
                        meta["stock"][k] = "not_provided"
            call["metadata"] = json.dumps(meta)
        except:
            pass

    return {"calls": calls, "total": total}


@router.get("/calls/{call_id}")
async def api_get_call(call_id: str):
    call = get_call(call_id)
    if not call:
        return JSONResponse(status_code=404, content={"error": "Call not found"})

    messages = get_messages(call_id)
    agent = get_agent(call["agent_id"])

    # Transform metadata for frontend: replace -1 with 'not_provided'
    meta_raw = call.get("metadata", "{}")
    import json
    try:
        meta = json.loads(meta_raw)
        if "stock" in meta:
            for k, v in meta["stock"].items():
                if v == -1:
                    meta["stock"][k] = "not_provided"
        call["metadata"] = json.dumps(meta)
    except:
        pass

    return {
        **call,
        "agent_name": agent["name"] if agent else "Unknown",
        "messages": messages,
    }


@router.get("/calls/{call_id}/recording")
async def api_get_recording(call_id: str):
    from fastapi.responses import RedirectResponse
    call = get_call(call_id)
    if not call or not call.get("recording_url"):
        return JSONResponse(status_code=404, content={"error": "Recording not available"})
    return RedirectResponse(url=call["recording_url"])


# ── Plivo Recording Callback ──

@router.api_route("/api/plivo/record_callback", methods=["GET", "POST"], include_in_schema=False)
async def record_callback(request: Request):
    params = dict(request.query_params)
    form_data = {}
    try:
        form_data = dict(await request.form())
    except:
        pass
    call_id = params.get("call_id", "")
    recording_url = form_data.get("RecordUrl", "") or form_data.get("RecordingUrl", "")
    if call_id and recording_url:
        update_call(call_id, recording_url=recording_url)
        log.info(f"[API] Recording saved for call {call_id}")
    return {"status": "ok"}

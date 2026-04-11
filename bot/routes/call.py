from fastapi import APIRouter
from plivo import RestClient
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_NUMBER, SERVER_URL

router = APIRouter()
plivo_client = RestClient(auth_id=PLIVO_AUTH_ID, auth_token=PLIVO_AUTH_TOKEN)


@router.get("/call/test")
async def trigger_call():
    plivo_client.calls.create(
        from_=PLIVO_NUMBER,
        to_="+918707550471",
        # to_="+918810757656",
        answer_url=f"{SERVER_URL}/api/plivo/answer",
        answer_method="GET"
    )
    return {"status": "calling"}

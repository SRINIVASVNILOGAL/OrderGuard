import hashlib
import secrets
import base64
import requests
from fastapi import APIRouter

router=APIRouter()
code_verifier = None



def create_pkce():
    code_verifier = secrets.token_urlsafe(32)

    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("utf-8")).digest()
        )
        .decode("utf-8")
        .rstrip("=")
    )

    return code_verifier, code_challenge
def register_client():
    response=requests.post(
        "https://mcp.swiggy.com/auth/register",
        json={
            "client_name":"OrderGuard",
            "redirect_uris":[
                "http://localhost/callback"
            ],
        },
    )
    response.raise_for_status()
    return response.json()

def create_authorization_url():
    global code_verifier

    client = register_client()

    code_verifier, code_challenge = create_pkce()

    params = {
        "client_id": client["client_id"],
        "redirect_uri": "http://localhost/callback",
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    response = requests.Request(
        "GET",
        "https://mcp.swiggy.com/auth/authorize",
        params=params,
    ).prepare()

    return response.url



@router.get("/callback")
def oauth_callback(code: str):
    token_response = requests.post(
        "https://mcp.swiggy.com/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost/callback",
            "client_id": "swiggy-mcp",
            "code_verifier": code_verifier,
        },
    )

    token_response.raise_for_status()

    return token_response.json()
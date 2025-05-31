
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.services.auth_jwt_service import create_access_token, verify_token, blacklist_token
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/refresh")
async def refresh_token(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = verify_token(token, scope="refresh_token")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_data = {k: payload[k] for k in payload if k != "exp" and k != "scope"}
    new_access = create_access_token(user_data)
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/logout")
async def logout(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    blacklist_token(token)
    return JSONResponse({"message": "Successfully logged out."})
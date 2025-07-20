from fastapi.responses import JSONResponse


def success_response(
    data: dict = None, message: str = "Request successful"
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": data or {}, "message": message},
    )


def error_response(
    error_message: str = "Something went wrong", status_code: int = 400
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"detail": error_message}},
    )

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ClientErrorReport(BaseModel):
    """Error report uploaded by the mobile app (ErrorReport.toJson()).

    Every field except `error` is optional and size-capped: reports are sent
    from crashed/degraded clients, so validation must be lenient — a rejected
    report is a lost signal, and the app would retry it forever.
    """

    id: Optional[str] = Field(default=None, max_length=64)
    timestamp: Optional[str] = Field(default=None, max_length=64)
    error: str = Field(min_length=1, max_length=4096)
    stackTrace: Optional[str] = Field(default=None, max_length=16384)
    severity: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)
    context: Optional[Dict[str, Any]] = None
    appVersion: Optional[str] = Field(default=None, max_length=64)
    platform: Optional[str] = Field(default=None, max_length=64)
    deviceInfo: Optional[str] = Field(default=None, max_length=512)
    isConnected: Optional[bool] = None
    userId: Optional[str] = Field(default=None, max_length=64)


class ClientErrorAck(BaseModel):
    status: str = "received"
    report_id: Optional[str] = None

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.transactions.schemas import TxnIn, TxnOut
from app.api.transactions.services import add_transaction_background
from app.core.session import get_db
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/transactions/v2", tags=["transactions"])


@router.post("/", response_model=TxnOut)
async def create_transaction_v2(
    txn: TxnIn,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = add_transaction_background(user, txn, db, background_tasks)
    return success_response(result)

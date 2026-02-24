from datetime import datetime as DateTime

from pydantic import BaseModel


class Ticket(BaseModel):
    id: int
    event_id: int
    attendee_id: int
    price: float
    purchase_time: DateTime

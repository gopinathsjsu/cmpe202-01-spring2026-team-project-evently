from pydantic import BaseModel


class EventFavorite(BaseModel):
    event_id: int
    user_id: int

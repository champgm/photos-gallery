from pydantic import BaseModel
from typing import Optional
import datetime as dt


class CsvEntry(BaseModel):
    file_name: str
    thumbnail_file_name: Optional[str] = None
    aspect_ratio: float
    created_date: dt.datetime

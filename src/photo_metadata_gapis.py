from pydantic import BaseModel
from typing import Union

class MediaMetadata(BaseModel):
    creationTime: str
    width: str
    height: str

class PhotoMetadata(MediaMetadata):
    photo: dict

class VideoMetadata(MediaMetadata):
    video: dict

class GapisMetadata(BaseModel):
    id: str
    productUrl: str
    baseUrl: str
    mimeType: str
    mediaMetadata: Union[PhotoMetadata, VideoMetadata]
    filename: str

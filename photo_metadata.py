from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Union

class TimeStamp(BaseModel):
    timestamp: str
    formatted: str

class GeoData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    latitudeSpan: float
    longitudeSpan: float

class Person(BaseModel):
    name: str

class DeviceFolder(BaseModel):
    localFolderName: str

class MobileUpload(BaseModel):
    deviceFolder: DeviceFolder
    deviceType: str

class ComputerUpload(BaseModel):
    # Assuming structure based on your error message; adjust as needed
    localFolderName: Optional[str] = None

# Use a Union to allow for different upload types
class UploadTypes(BaseModel):
    mobileUpload: Optional[MobileUpload] = None
    webUpload: Optional[ComputerUpload] = None  # Or however the structure needs to be defined

class GooglePhotosOrigin(BaseModel):
    uploadType: Union[MobileUpload, ComputerUpload, None] = None

class PhotoMetadata(BaseModel):
    title: str
    description: str
    imageViews: int
    creationTime: TimeStamp
    photoTakenTime: TimeStamp
    geoData: GeoData
    geoDataExif: GeoData
    people: Optional[List[Person]] = []  # Marked as optional with a default empty list
    url: HttpUrl
    googlePhotosOrigin: Optional[GooglePhotosOrigin] = None  # Marked as optional


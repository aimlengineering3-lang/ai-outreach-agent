from fastapi import APIRouter, HTTPException

from src.core.config import load_settings, save_settings
from api.schemas import SettingsOut, SendingWindow, TargetCity

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings():
    return load_settings()


@router.put("/sending-window", response_model=SettingsOut)
def update_sending_window(payload: SendingWindow):
    settings = load_settings()
    settings["sending_window"] = {"start_hour": payload.start_hour, "end_hour": payload.end_hour}
    save_settings(settings)
    return settings


@router.post("/target-cities", response_model=SettingsOut)
def add_target_city(payload: TargetCity):
    settings = load_settings()
    cities = settings.get("target_cities", [])
    cities.append({"city": payload.city.strip(), "state": payload.state.strip().upper()})
    settings["target_cities"] = cities
    save_settings(settings)
    return settings


@router.delete("/target-cities/{index}", response_model=SettingsOut)
def remove_target_city(index: int):
    settings = load_settings()
    cities = settings.get("target_cities", [])
    if index < 0 or index >= len(cities):
        raise HTTPException(status_code=404, detail="No city at that index")
    cities.pop(index)
    settings["target_cities"] = cities
    save_settings(settings)
    return settings

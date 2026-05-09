"""In-process rover registry for V1."""
from core.models.rover import Rover


class RoverRegistry:
    def __init__(self) -> None:
        self._rovers: dict[str, Rover] = {}

    def register(self, rover: Rover) -> Rover:
        self._rovers[rover.id] = rover
        return rover

    def get(self, rover_id: str) -> Rover | None:
        return self._rovers.get(rover_id)

    def list(self) -> list[Rover]:
        return list(self._rovers.values())

    def list_for_mission(self, mission_id: str) -> list[Rover]:
        return [r for r in self._rovers.values() if r.mission_id == mission_id]

    def update(self, rover: Rover) -> Rover:
        self._rovers[rover.id] = rover
        return rover

    def delete(self, rover_id: str) -> bool:
        return self._rovers.pop(rover_id, None) is not None


rover_registry = RoverRegistry()

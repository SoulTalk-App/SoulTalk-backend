from pydantic import BaseModel, computed_field


class SoulBarResponse(BaseModel):
    points: int
    total_filled: int

    @computed_field
    @property
    def is_full(self) -> bool:
        return self.points == 6

    model_config = {"from_attributes": True}

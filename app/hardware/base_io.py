from abc import ABC, abstractmethod


class HardwareIO(ABC):
    @abstractmethod
    def set_output(self, hw_id: str, value: bool) -> None:
        ...

    @abstractmethod
    def get_input(self, hw_id: str) -> bool:
        ...

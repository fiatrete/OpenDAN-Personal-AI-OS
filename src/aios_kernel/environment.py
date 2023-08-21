class environment_event(ABC):
    @abstractmethod
    def display(self) -> str:
        pass    


class environment:
    def __init__(self) -> None:
        pass

    def event_to_msg(self,) -> environment_event:
        pass
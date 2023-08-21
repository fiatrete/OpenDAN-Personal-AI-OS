
class llm_work_task:
    def __init__(self) -> None:
        pass


class llm_kernel:
    def __init__(self) -> None:
        pass
    def completion(self,prompt:str,max_token:int) -> llm_work_task:
        # craete a llm_work_task ,push on queue's end
        # then task_schedule would run this task.(might schedule some work_task to another host)
        pass
    
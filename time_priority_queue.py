from queue import Empty, PriorityQueue
from datetime import datetime
from typing import Any, Optional


class TimePriorityQueue(PriorityQueue):

    def __init__(self, maxsize: int) -> None:
        super().__init__(maxsize=maxsize)

    def put(self, time:float, item:Any, block:bool=True, timeout:Optional[float]=None):
        priority_time = datetime.now().timestamp() + time
        return super().put((priority_time, item), block=block, timeout=timeout)

    def get_n(self, n:int, block:bool=True, timeout:Optional[float]=None):
        return_items = []
        if timeout is None:
            timeout = float("inf")
        for i in range(n):
            try:
                timestamp, item = self.get(block=block, timeout=timeout)
                timeout = min(timeout, timestamp-datetime.now().timestamp())
                return_items.append(item)
                if timeout < 0:
                    return return_items
            except Empty:
                return return_items
        return return_items

    def peek(self) -> Any:
        if self.empty():
            return None
        return self.queue[0]


if __name__ == "__main__":
    tpq = TimePriorityQueue(0)

    print(tpq.empty())
    print(tpq.peek())
    tpq.put(50, "1")
    tpq.put(10, "2")
    print(tpq.empty())
    print(tpq.peek())
    print(tpq.get_n(3))

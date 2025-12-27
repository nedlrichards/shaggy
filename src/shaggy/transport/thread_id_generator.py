class ThreadIDGenerator:
    def __init__(self):
        self.thread_id = 0

    def __call__(self):
        thread_id = self.thread_id
        self.thread_id += 1
        return f"{thread_id:05d}"

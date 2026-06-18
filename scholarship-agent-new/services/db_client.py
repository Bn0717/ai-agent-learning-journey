class FakeDB:
    def __init__(self):
        self.storage = []

    def insert_one(self, data):
        self.storage.append(data)
        print("DB stored:", data)


db = FakeDB()
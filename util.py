import ujson
import os


if __name__ == "__main__":
    print("don't execute this file")
    exit()


with open(os.path.join(os.path.dirname(__file__), "tokens.json"), "rb") as f:
    tokens = ujson.loads(f.read())

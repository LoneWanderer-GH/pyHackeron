# stream.py
class StreamParser:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buf.extend(data)

        frames :list[bytes]= []

        while True:
            if len(self.buf) < 17:
                break

            # recherche sync 42 ... 42
            start = self.buf.find(42)
            if start == -1:
                self.buf.clear()
                break

            if len(self.buf) < start + 17:
                break

            candidate = self.buf[start:start+17]

            if candidate[16] == 42:
                frames.append(bytes(candidate))
                del self.buf[:start+17]
            else:
                del self.buf[:start+1]

        return frames
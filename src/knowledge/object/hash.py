import hashlib
import base58
import base36

class HashValue:
    def __init__(self, value: bytes):
        assert len(value) == 32, "HashValue must be 32 bytes long"
        self.value = value

    def __str__(self) -> str:
        return self.to_base58()
        
    @staticmethod
    def hash_data(data):
        return hash_data(data)

    def to_base58(self):
        return base58.b58encode(self.value).decode()

    @staticmethod
    def from_base58(s):
        return HashValue(base58.b58decode(s))

    def to_base36(self):
        # Convert the bytes to int before encoding
        num = int.from_bytes(self.value, 'big')
        return base36.dumps(num)

    @staticmethod
    def from_base36(s):
        # Decode to int and then convert to bytes
        num = base36.loads(s)
        return HashValue(num.to_bytes((num.bit_length() + 7) // 8, 'big'))
    
    
HASH_VALUE_LEN = 32


def hash_data(data: bytes):
    sha256 = hashlib.sha256()
    sha256.update(data)
    return HashValue(sha256.digest())

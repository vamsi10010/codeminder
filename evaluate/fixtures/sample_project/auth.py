import base64
import hmac
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass
class TokenPayload:
    sub: str
    exp: int
    scope: str


class AuthService:
    def __init__(self, secret: str) -> None:
        self.secret = secret.encode("utf-8")

    def _sign(self, message: bytes) -> str:
        digest = hmac.new(self.secret, message, sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def encode_token(self, payload: TokenPayload) -> str:
        body = json.dumps(payload.__dict__).encode("utf-8")
        signature = self._sign(body)
        return f"{base64.urlsafe_b64encode(body).decode('utf-8').rstrip('=')}.{signature}"

    def verify_token(self, token: str) -> TokenPayload:
        try:
            encoded_body, signature = token.split(".")
            body = base64.urlsafe_b64decode(encoded_body + "==")
            expected_sig = self._sign(body)
            if not hmac.compare_digest(signature, expected_sig):
                raise ValueError("invalid signature")
            payload_data: dict[str, Any] = json.loads(body)
            return TokenPayload(**payload_data)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid token: {exc}") from exc

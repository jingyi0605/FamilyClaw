import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.v1.endpoints.channel_gateways import router as channel_gateways_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.channel.schemas import ChannelAccountCreate
from app.modules.channel.service import create_channel_account
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class ChannelGatewayWecomHandshakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

        app = FastAPI()
        app.include_router(channel_gateways_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_wecom_app_builtin_get_handshake_returns_plaintext(self) -> None:
        aes_key = self._build_wecom_aes_key()
        token = "token-001"
        corp_id = "wxcorp001"
        timestamp = "1710500000"
        nonce = "nonce-001"

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="WeCom Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            account = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-wecom-app",
                    account_code="wecom-main",
                    display_name="浼佸井涓昏处鍙?,
                    connection_mode="webhook",
                    config={
                        "callback_token": token,
                        "encoding_aes_key": aes_key,
                        "corp_id": corp_id,
                    },
                    status="active",
                ),
            )
            db.commit()

        echostr = self._encrypt_wecom_payload("hello-wecom", aes_key, corp_id)
        signature = self._build_wecom_signature(token, timestamp, nonce, echostr)
        response = self.client.get(
            f"{settings.api_v1_prefix}/channel-gateways/accounts/{account.id}/webhook",
            params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
                "echostr": echostr,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("hello-wecom", response.text)

    def _build_wecom_aes_key(self) -> str:
        return base64.b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii").rstrip("=")

    def _encrypt_wecom_payload(self, plaintext: str, aes_key: str, corp_id: str) -> str:
        key = base64.b64decode(aes_key + "=")
        raw = b"abcdefghijklmnop" + len(plaintext.encode("utf-8")).to_bytes(4, "big") + plaintext.encode("utf-8") + corp_id.encode("utf-8")
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(raw) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")

    def _build_wecom_signature(self, token: str, timestamp: str, nonce: str, encrypted: str) -> str:
        return hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()


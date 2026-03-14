from __future__ import annotations

import asyncio
import logging

from open_xiaoai_gateway.bridge import OpenXiaoAIGateway
from open_xiaoai_gateway.settings import settings


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(OpenXiaoAIGateway().run())


if __name__ == "__main__":
    main()

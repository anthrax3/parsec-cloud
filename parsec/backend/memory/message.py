# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

from typing import List, Tuple
from collections import defaultdict
from pendulum import Pendulum

from parsec.api.protocol import UserID, DeviceID, OrganizationID
from parsec.backend.message import BaseMessageComponent


class MemoryMessageComponent(BaseMessageComponent):
    def __init__(self, send_event):
        self._send_event = send_event
        self._organizations = defaultdict(lambda: defaultdict(list))

    def register_components(self, **other_components):
        pass

    async def send(
        self,
        organization_id: OrganizationID,
        sender: DeviceID,
        recipient: UserID,
        timestamp: Pendulum,
        body: bytes,
    ) -> None:
        messages = self._organizations[organization_id]
        messages[recipient].append((sender, timestamp, body))
        index = len(messages[recipient])
        await self._send_event(
            "message.received",
            organization_id=organization_id,
            author=sender,
            recipient=recipient,
            index=index,
        )

    async def get(
        self, organization_id: OrganizationID, recipient: UserID, offset: int
    ) -> List[Tuple[DeviceID, bytes]]:
        messages = self._organizations[organization_id]
        return messages[recipient][offset:]

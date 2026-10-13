"""Final hardware service-call guard, including private startup/reset/fallback paths."""


class HardwareAuthority:
    def __init__(self, client, *, shadow: bool):
        self._client = client
        self.shadow = shadow
        self.suppressed_writes = 0

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def call_service(self, domain, service, data):
        if self.shadow:
            self.suppressed_writes += 1
            return
        await self._client.call_service(domain, service, data)

"""Final hardware service-call guard, including private startup/reset/fallback paths."""


class HardwareAuthority:
    def __init__(self, client, *, enabled):
        self._client = client
        self._enabled = enabled
        self.suppressed_writes = 0

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def call_service(self, domain, service, data):
        if not self._enabled():
            self.suppressed_writes += 1
            return
        await self._client.call_service(domain, service, data)

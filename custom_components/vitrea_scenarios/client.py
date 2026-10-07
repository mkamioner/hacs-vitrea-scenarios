"""Minimal Vitrea V-Box client: login and run scenarios (protocol v2).

The V-Box appears to accept only one TCP client at a time, so each call opens
a short-lived connection instead of holding one open.
"""
from __future__ import annotations

import asyncio

PREFIX = b"VTU"
DIR_OUT = 0x3E
INCOMING_PREFIX = PREFIX + bytes([0x3C])

CMD_ACK = 0
CMD_LOGIN = 1
CMD_TOGGLE_HEARTBEAT = 8
CMD_RUN_SCENARIO = 52

# Trailing byte of the RUN_SCENARIO payload; meaning unknown, always 0x03 in captures.
SCENARIO_ARG = 0x03


class VitreaError(Exception):
    """Base error."""


class VitreaConnectionError(VitreaError):
    """Could not connect, or the V-Box dropped the connection."""


class VitreaTimeoutError(VitreaError):
    """The V-Box did not acknowledge a command in time."""


def build_datagram(cmd: int, msg_id: int, data: bytes = b"") -> bytes:
    length = len(data) + 2  # msg_id byte + checksum byte
    body = bytearray(PREFIX)
    body += bytes([DIR_OUT, cmd, (length >> 8) & 0xFF, length & 0xFF, msg_id])
    body += data
    body.append(sum(body) & 0xFF)
    return bytes(body)


def encode_login(user: str, pwd: str) -> bytes:
    u = user.encode("utf-16-le")
    p = pwd.encode("utf-16-le")
    return bytes([len(u)]) + u + bytes([len(p)]) + p


class VitreaClient:
    def __init__(self, host: str, port: int, username: str, password: str, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self._msg_id = 0
        self._lock = asyncio.Lock()

    def _next_id(self) -> int:
        self._msg_id = (self._msg_id % 255) + 1
        return self._msg_id

    async def test_connection(self) -> None:
        """Connect and log in, then disconnect."""
        async with self._lock:
            reader, writer = await self._open()
            await self._close(writer)

    async def run_scenario(self, scenario_id: int) -> None:
        async with self._lock:
            reader, writer = await self._open()
            try:
                await self._send_expect_ack(
                    reader, writer, CMD_RUN_SCENARIO, bytes([scenario_id, SCENARIO_ARG])
                )
            finally:
                await self._close(writer)

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
        except asyncio.TimeoutError as e:
            raise VitreaTimeoutError(f"timed out connecting to {self.host}:{self.port}") from e
        except OSError as e:
            raise VitreaConnectionError(f"cannot connect to {self.host}:{self.port}: {e}") from e
        try:
            # Handshake mirrors the official client: ToggleHeartbeat, then Login.
            await self._send_expect_ack(reader, writer, CMD_TOGGLE_HEARTBEAT, bytes([1, 1]))
            await self._send_expect_ack(
                reader, writer, CMD_LOGIN, encode_login(self.username, self.password)
            )
        except BaseException:
            await self._close(writer)
            raise
        return reader, writer

    @staticmethod
    async def _close(writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass

    async def _send_expect_ack(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cmd: int, data: bytes
    ) -> None:
        msg_id = self._next_id()
        try:
            writer.write(build_datagram(cmd, msg_id, data))
            await writer.drain()
            await asyncio.wait_for(self._wait_ack(reader, msg_id), timeout=self.timeout)
        except asyncio.TimeoutError as e:
            raise VitreaTimeoutError(f"no ACK for cmd={cmd} msg_id={msg_id}") from e
        except (OSError, asyncio.IncompleteReadError) as e:
            raise VitreaConnectionError(f"connection lost during cmd={cmd}: {e}") from e

    @staticmethod
    async def _wait_ack(reader: asyncio.StreamReader, msg_id: int) -> None:
        buf = bytearray()
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                raise VitreaConnectionError("V-Box closed the connection")
            buf += chunk
            # Split datagrams: prefix(4) cmd(1) len(2) then len bytes (msg_id..checksum).
            while True:
                i = buf.find(INCOMING_PREFIX)
                if i < 0:
                    buf.clear()
                    break
                del buf[:i]
                if len(buf) < 8:
                    break
                total = 7 + ((buf[5] << 8) | buf[6])
                if len(buf) < total:
                    break
                dgram = bytes(buf[:total])
                del buf[:total]
                if (sum(dgram[:-1]) & 0xFF) != dgram[-1]:
                    continue
                if dgram[4] == CMD_ACK and dgram[7] == msg_id:
                    return

"""Bounded ASGI request bodies before FastAPI/Pydantic parse JSON.

All current mutating endpoints use small JSON bodies (including transcript imports).
This middleware deliberately buffers only within a documented bounded budget and
replays every ASGI frame, preserving FastAPI's normal request-body handling.
It is not a general-purpose streaming-upload implementation.
"""
from __future__ import annotations

from starlette.responses import JSONResponse

DEFAULT_MAX_BODY = 512 * 1024  # ordinary operations: 512 KiB
TRANSCRIPT_MAX_BODY = 2 * 1024 * 1024  # large JSON with escaped Unicode


def body_budget(path: str) -> int:
    """Permit larger, still bounded imports without exempting generic endpoints."""
    if path.startswith('/api/events/') and path.endswith('/transcripts'):
        return TRANSCRIPT_MAX_BODY
    if path.startswith('/api/meeting-review/transcripts/') and path.endswith('/analyses'):
        return TRANSCRIPT_MAX_BODY
    return DEFAULT_MAX_BODY


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in {'POST', 'PATCH', 'PUT', 'DELETE'}:
            await self.app(scope, receive, send)
            return

        max_bytes = body_budget(scope.get('path', ''))
        length_headers = [value for key, value in scope.get('headers', [])
                          if key.lower() == b'content-length']
        if length_headers:
            try:
                # Multiple or invalid Content-Length fields must not bypass checks.
                if len(length_headers) != 1:
                    raise ValueError('ambiguous Content-Length')
                declared = int(length_headers[0].decode('ascii'))
                if declared < 0:
                    raise ValueError('negative Content-Length')
            except (ValueError, UnicodeError):
                await JSONResponse({'detail': 'Content-Length inválido'}, status_code=400)(
                    scope, receive, send)
                return
            if declared > max_bytes:
                await JSONResponse({'detail': 'Corpo da requisição excede o limite permitido'},
                                   status_code=413)(scope, receive, send)
                return

        # Do not depend on Content-Length: chunked frames must also be bounded.
        # The local API has no multipart/streaming write routes; no frame is
        # forwarded downstream until its complete size has been checked.
        frames = []
        received = 0
        while True:
            frame = await receive()
            if frame['type'] == 'http.disconnect':
                return  # Client left before a complete request: do not process.
            if frame['type'] != 'http.request':
                return
            received += len(frame.get('body', b''))
            if received > max_bytes:
                await JSONResponse({'detail': 'Corpo da requisição excede o limite permitido'},
                                   status_code=413)(scope, receive, send)
                return
            frames.append(frame)
            if not frame.get('more_body', False):
                break

        index = 0
        async def replay():
            nonlocal index
            if index < len(frames):
                item = frames[index]
                index += 1
                return item
            return await receive()

        await self.app(scope, replay, send)

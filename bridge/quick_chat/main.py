"""Quick Chat bridge entry point."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from .adapters.registry import AdapterRegistry
from .engine import BusyError, Engine
from .context.app import ActiveAppProvider
from .context.base import AttachmentRecord, ContextManager
from .context.capture import CaptureProvider
from .context.ocr import OcrProvider
from .context.omarchy import OmarchyQueryProvider
from .context.selection import SelectionProvider
from .history import HistoryStore
from .menu import install_menu_entry
from .models import Config, Conversation, Message
from .paths import PathSet
from .protocol import Event, MAX_REQUEST_BYTES, ProtocolError, Request
from .storage import ConfigStore
from .shortcuts import sync_shortcuts
from .transports.process import ProcessTransport


def _write_event(
    output_stream: TextIO,
    event: Event,
    lock: threading.Lock | None = None,
) -> None:
    if lock is None:
        output_stream.write(event.to_json() + "\n")
        output_stream.flush()
        return
    with lock:
        output_stream.write(event.to_json() + "\n")
        output_stream.flush()


def _handle_local_request(
    request: Request,
    registry: AdapterRegistry | None = None,
) -> list[Event]:
    paths = PathSet.from_env()
    config_store = ConfigStore(paths)
    config = config_store.load()
    history_store = HistoryStore(paths, config)
    events: list[Event] = []

    if config_store.last_diagnostic is not None:
        events.append(Event("status", request.request_id, config_store.last_diagnostic))

    if request.type == "profiles":
        adapter_states = []
        if registry is not None:
            for adapter_id in registry.keys:
                try:
                    adapter = registry.get(adapter_id)
                    adapter_states.append({
                        "id": adapter_id,
                        "availability": "unknown",
                        "capabilities": asdict(adapter.capabilities),
                    })
                except KeyError:
                    adapter_states.append({
                        "id": adapter_id,
                        "availability": "unregistered",
                        "capabilities": None,
                    })
        events.append(Event("complete", request.request_id, {
            "config": config.to_dict(),
            "adapters": adapter_states,
        }))
        return events
    if request.type == "profiles.save":
        if request.configuration is None:
            raise ProtocolError("profiles.save requires config")
        updated = Config.from_dict(request.configuration)
        config_store.save(updated)
        events.append(Event("complete", request.request_id, {
            "config": updated.to_dict(),
        }))
        return events
    if request.type == "history.list":
        conversations = history_store.list()
        if history_store.last_diagnostic is not None:
            events.append(Event("status", request.request_id, history_store.last_diagnostic))
        events.append(Event("complete", request.request_id, {
            "conversations": [{
                "id": conversation.id,
                "title": conversation.title,
                "profileId": conversation.profile_id,
                "updatedAt": conversation.updated_at,
            } for conversation in conversations],
        }))
        return events
    if request.type == "history.get":
        if not request.conversation_id:
            raise ProtocolError("history.get requires conversationId")
        conversation = next(
            (
                item
                for item in history_store.list()
                if item.id == request.conversation_id
            ),
            None,
        )
        if conversation is None:
            raise ProtocolError("conversation was not found", "not_found")
        events.append(Event("complete", request.request_id, {
            "conversation": conversation.to_dict(),
        }))
        return events
    if request.type == "history.clear":
        if not request.confirm:
            raise ProtocolError("history.clear requires confirm: true", "confirmation_required")
        history_store.clear()
        events.append(Event("complete", request.request_id, {"cleared": True}))
        return events

    events.append(Event("status", request.request_id, {"status": "accepted"}))
    return events


def run(input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve JSONL until the input stream reaches EOF."""
    output_lock = threading.Lock()
    paths = PathSet.from_env()
    config = ConfigStore(paths).load()
    registry = AdapterRegistry()
    context_manager = ContextManager(paths)
    context_manager.sweep()
    engine = Engine(
        registry,
        ProcessTransport(),
        config,
        attachment_cleanup=context_manager.remove_many,
    )
    workers: dict[str, threading.Thread] = {}
    _write_event(
        output_stream,
        Event("ready", "bridge", {"protocolVersion": 1}),
        output_lock,
    )

    def run_request(request: Request) -> None:
        emitted: list[Event] = []
        persisted = False

        def persist_conversation() -> None:
            nonlocal persisted
            if persisted or request.private or not emitted:
                return
            history = HistoryStore(paths, engine.config)
            existing = next((
                item
                for item in history.list()
                if item.id == request.conversation_id
            ), None)
            now = datetime.now(UTC).isoformat()
            messages = list(existing.messages) if existing else []
            messages.append(Message("user", request.prompt or "", now))
            answer = "".join(
                str(event.data.get("text", ""))
                for event in emitted
                if event.type == "text_delta"
            )
            if answer:
                messages.append(Message("assistant", answer, now))
            sessions = dict(existing.cli_sessions) if existing else {}
            for event in emitted:
                if event.type == "session" and isinstance(event.data.get("sessionId"), str):
                    profile = engine.config.profile(request.profile_id or "")
                    if profile is not None:
                        sessions[profile.adapter_id] = str(event.data["sessionId"])
            history.upsert(Conversation(
                id=request.conversation_id or request.request_id,
                title=(existing.title if existing else (request.prompt or "New chat")[:80]),
                profile_id=request.profile_id or engine.config.selected_profile_id,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                messages=tuple(messages),
                cli_sessions=sessions,
            ), private=False)
            persisted = True

        try:
            for event in engine.handle(request):
                emitted.append(event)
                if event.type in {"complete", "error"}:
                    persist_conversation()
                _write_event(output_stream, event, output_lock)
        except BusyError as error:
            _write_event(output_stream, Event("error", request.request_id, {
                "code": "busy",
                "message": str(error),
            }), output_lock)
        except (KeyError, OSError, ValueError) as error:
            _write_event(output_stream, Event("error", request.request_id, {
                "code": "request_failed",
                "message": str(error),
            }), output_lock)
        finally:
            try:
                persist_conversation()
            except (OSError, ValueError):
                pass
            workers.pop(request.request_id, None)

    def resolve_session(conversation_id: str, adapter_id: str) -> str | None:
        history = HistoryStore(paths, engine.config)
        conversation = next(
            (item for item in history.list() if item.id == conversation_id),
            None,
        )
        return conversation.cli_sessions.get(adapter_id) if conversation else None

    engine.session_resolver = resolve_session

    for line in input_stream:
        request_id = "bridge"
        request: Request | None = None
        try:
            if len(line.encode("utf-8")) > MAX_REQUEST_BYTES:
                raise ProtocolError(
                    "request body exceeds 1 MiB",
                    "request_too_large",
                )
            decoded = json.loads(line)
            if isinstance(decoded, dict) and isinstance(decoded.get("requestId"), str):
                request_id = decoded["requestId"] or "bridge"
            request = Request.from_dict(decoded)
            if request.type == "run":
                paths.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                paths.state_dir.chmod(0o700)
                config = ConfigStore(paths).load()
                engine.config = config
                for attachment in request.attachments:
                    try:
                        context_manager.get(attachment.id)
                    except ValueError:
                        context_manager.add(AttachmentRecord(
                            id=attachment.id,
                            kind=attachment.kind,
                            mime_type=attachment.mime_type,
                            path=Path(attachment.path) if attachment.path else None,
                            text=attachment.text,
                            size=(
                                Path(attachment.path).stat().st_size
                                if attachment.path and Path(attachment.path).is_file()
                                else len((attachment.text or "").encode("utf-8"))
                            ),
                        ))
                worker = threading.Thread(target=run_request, args=(request,), daemon=True)
                workers[request.request_id] = worker
                worker.start()
            elif request.type == "cancel":
                cancelled = engine.cancel(request.request_id)
                event = Event(
                    "status" if cancelled else "error",
                    request.request_id,
                    {"status": "cancelling"}
                    if cancelled
                    else {"code": "not_running", "message": "Request is not running."},
                )
                _write_event(output_stream, event, output_lock)
            elif request.type in {"approve", "deny"}:
                if not request.approval_id:
                    raise ProtocolError("approvalId is required")
                resolved = engine.resolve_approval(
                    request.request_id,
                    request.approval_id,
                    request.type == "approve",
                )
                _write_event(output_stream, Event(
                    "status" if resolved else "error",
                    request.request_id,
                    {"status": "approval_recorded"}
                    if resolved
                    else {"code": "approval_not_pending", "message": "Approval is no longer pending."},
                ), output_lock)
            elif request.type == "probe" and request.profile_id:
                profile = config.profile(request.profile_id)
                if profile is None:
                    raise ProtocolError("profile was not found", "profile_not_found")
                detection = registry.detect(profile.adapter_id, refresh=True)
                _write_event(
                    output_stream,
                    Event("complete", request.request_id, detection),
                    output_lock,
                )
            elif request.type == "context.capture":
                if request.mode == "window":
                    attachment = CaptureProvider(paths).active_window()
                    try:
                        metadata = ActiveAppProvider().get()
                        attachment = replace(
                            attachment,
                            app_name=metadata.app_name,
                            window_title=metadata.window_title,
                        )
                    except (OSError, RuntimeError, ValueError):
                        pass
                elif request.mode == "screen":
                    attachment = CaptureProvider(paths).fullscreen()
                elif request.mode == "app":
                    attachment = ActiveAppProvider().get().to_attachment()
                elif request.mode == "selection":
                    attachment = SelectionProvider().capture()
                elif request.mode == "omarchy" and request.query:
                    attachment = OmarchyQueryProvider().query(request.query)
                else:
                    raise ProtocolError("unsupported context capture mode")
                context_manager.add(attachment)
                _write_event(output_stream, Event("complete", request.request_id, {
                    "attachment": attachment.to_wire(),
                }), output_lock)
            elif request.type == "context.ocr":
                if not request.attachment_id:
                    raise ProtocolError("context.ocr requires attachmentId")
                source = context_manager.get(request.attachment_id)
                if source.path is None:
                    raise ProtocolError("OCR attachment has no image path")
                attachment = context_manager.add(OcrProvider().convert(source.path))
                _write_event(output_stream, Event("complete", request.request_id, {
                    "attachment": attachment.to_wire(),
                    "sourceAttachmentId": source.id,
                }), output_lock)
            elif request.type == "context.remove":
                if not request.attachment_id:
                    raise ProtocolError("context.remove requires attachmentId")
                removed = context_manager.remove(request.attachment_id)
                _write_event(output_stream, Event("complete", request.request_id, {
                    "removed": removed,
                    "attachmentId": request.attachment_id,
                }), output_lock)
            else:
                for event in _handle_local_request(request, registry):
                    _write_event(output_stream, event, output_lock)
        except (json.JSONDecodeError, OSError, ProtocolError, RuntimeError, ValueError) as error:
            code = error.code if isinstance(error, ProtocolError) else (
                "capture_failed"
                if request is not None and request.type.startswith("context.")
                else "invalid_request"
            )
            _write_event(
                output_stream,
                Event(
                    "error",
                    request_id,
                    {"code": code, "message": str(error)},
                ),
                output_lock,
            )

    for request_id, worker in list(workers.items()):
        if worker.is_alive():
            engine.cancel(request_id)
        worker.join(timeout=4)
    context_manager.cleanup_all()
    registry.close()


def main(
    arguments: list[str],
    input_stream: TextIO,
    output_stream: TextIO,
) -> int:
    if arguments == ["shortcuts", "sync"]:
        paths = PathSet.from_env()
        config = ConfigStore(paths).load()
        result = sync_shortcuts(config)
        output_stream.write(json.dumps({
            "conflicts": [asdict(conflict) for conflict in result.conflicts],
            "applied": list(result.applied),
            "removed": list(result.removed),
        }) + "\n")
        output_stream.flush()
        return 0
    if arguments == ["menu", "install"]:
        result = install_menu_entry(PathSet.from_env().menu_extension_file)
        output_stream.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        output_stream.flush()
        return 0
    if arguments:
        output_stream.write(json.dumps({"error": "unsupported bridge command"}) + "\n")
        output_stream.flush()
        return 2
    run(input_stream, output_stream)
    return 0

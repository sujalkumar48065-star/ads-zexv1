"""
Telegram-as-a-Database storage controller.

Permanent storage lives in a private Telegram channel:
  * a pinned root document points to the current index document
  * the index document maps logical keys -> uploaded document message/file ids
  * each value is stored as one document, or as N chunks for big payloads
Local files are only a write-through cache (never the source of truth).
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from telegram import InputFile
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError, TimedOut

logger = logging.getLogger("TGStorage")

ROOT_CAPTION = "ADS_ROOT"
DATA_MARK = "ADS_DATA"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _short(value: str, n: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:n]


class TelegramStorage:
    def __init__(self, channel_id=None, namespace=None, chunk_size=None,
                 debounce=None, cache_dir=None, bot=None):
        raw = str(channel_id if channel_id is not None else os.environ.get("STORAGE_CHANNEL_ID", "")).strip()
        self.channel_id = int(raw) if raw and raw.lstrip("-").isdigit() else 0
        self.namespace = (namespace or os.environ.get("STORAGE_NAMESPACE")
                          or "ads-default").strip()
        self.chunk_size = int(chunk_size or os.environ.get("STORAGE_CHUNK_SIZE", 8 * 1024 * 1024))
        self.chunk_size = max(64 * 1024, min(self.chunk_size, 20 * 1024 * 1024))
        self.debounce = float(debounce or os.environ.get("STORAGE_DEBOUNCE", 1.5))
        self.cache_dir = Path(cache_dir or os.environ.get("STORAGE_CACHE_DIR", "cache_storage"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.bot = bot
        self.available = False
        self.last_error = ""
        self.last_sync = 0.0
        self.version = 0
        self.index: Dict[str, Any] = {"namespace": self.namespace, "version": 0, "keys": {}}
        self.index_msg_id = None
        self.root_msg_id = None

        self._lock = asyncio.Lock()
        self._pending: Dict[str, bytes] = {}
        self._flusher = None
        self._json_cache: Dict[str, Any] = {}
        self._blob_cache: Dict[str, Tuple[bytes, float]] = {}
        self._log_bases: Dict[str, bytes] = {}
        self._cache_ttl = float(os.environ.get("STORAGE_CACHE_TTL", 300))
        self._log_buffers: Dict[str, List[str]] = {}
        self._log_flusher = None
        self._log_interval = float(os.environ.get("STORAGE_LOG_INTERVAL", 45))
        self._stats = {"writes": 0, "reads": 0, "deletes": 0, "errors": 0, "chunks": 0}

    # ---------------------------------------------------------------- helpers
    @property
    def enabled(self) -> bool:
        return bool(self.channel_id)

    def key_hash(self, key: str) -> str:
        return _short(self.namespace + "::" + key)

    def _cache_file(self, name: str) -> Path:
        return self.cache_dir / name

    def _write_local_cache(self, name: str, payload: bytes):
        try:
            tmp = self._cache_file(name + ".tmp")
            with open(tmp, "wb") as f:
                f.write(payload)
            tmp.replace(self._cache_file(name))
        except Exception:
            pass

    def _read_local_cache(self, name: str) -> Optional[bytes]:
        try:
            p = self._cache_file(name)
            if p.exists():
                return p.read_bytes()
        except Exception:
            pass
        return None

    async def _call(self, fn, *args, retries=3, **kwargs):
        delay = 2.0
        for attempt in range(retries):
            try:
                return await fn(*args, **kwargs)
            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 5)) + 2
                logger.warning("Telegram retry_after %ss", wait)
                await asyncio.sleep(wait)
            except (TimedOut, NetworkError) as e:
                logger.warning("Telegram network error (%s/%s): %s", attempt + 1, retries, e)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
            except BadRequest:
                raise
        raise RuntimeError("telegram call failed after retries")

    # ------------------------------------------------------------- upload core
    async def _send_doc(self, payload: bytes, filename: str, caption: str):
        doc = InputFile(io.BytesIO(payload), filename=filename)
        msg = await self._call(
            self.bot.send_document,
            chat_id=self.channel_id,
            document=doc,
            caption=caption[:1000],
            disable_notification=True,
        )
        file_id = None
        try:
            file_id = msg.document.file_id
        except Exception:
            pass
        return msg.message_id, file_id

    async def _download_file(self, file_id: str) -> bytes:
        tg_file = await self._call(self.bot.get_file, file_id)
        data = await self._call(tg_file.download_as_bytearray)
        if isinstance(data, bytearray):
            data = bytes(data)
        return data

    async def _upload_blob(self, key: str, payload: bytes, content_type: str) -> Dict[str, Any]:
        total_sha = _sha256(payload)
        chunks = []
        if len(payload) <= self.chunk_size:
            parts = [payload]
        else:
            parts = [payload[i:i + self.chunk_size] for i in range(0, len(payload), self.chunk_size)]

        sent = []
        try:
            for idx, part in enumerate(parts):
                psha = _sha256(part)
                caption = "%s|ns=%s|k=%s|p=%d/%d|sha=%s|sz=%d" % (
                    DATA_MARK, _short(self.namespace, 8), self.key_hash(key),
                    idx + 1, len(parts), psha, len(part))
                fname = "ads_%s_%03d.bin" % (total_sha[:10], idx)
                mid, fid = await self._send_doc(part, fname, caption)
                if not fid:
                    raise RuntimeError("document file_id missing")
                rec = {"file_id": fid, "msg_id": mid, "sha": psha, "size": len(part)}
                chunks.append(rec)
                sent.append(rec)
                self._stats["chunks"] += 1
        except Exception:
            for rec in sent:
                try:
                    await self._call(self.bot.delete_message, self.channel_id, rec["msg_id"])
                except Exception:
                    pass
            raise

        return {
            "sha": total_sha,
            "size": len(payload),
            "content_type": content_type,
            "chunks": chunks,
            "updated": int(time.time()),
        }

    async def _delete_meta(self, meta: Dict[str, Any]):
        for rec in meta.get("chunks", []):
            try:
                await self._call(self.bot.delete_message, self.channel_id, rec["msg_id"])
            except Exception:
                pass

    # --------------------------------------------------------------- index/root
    async def _load_root(self) -> Dict[str, Any]:
        root = {"namespaces": {}}
        pinned = None
        try:
            chat = await self._call(self.bot.get_chat, self.channel_id)
            pinned = getattr(chat, "pinned_message", None)
        except Exception as e:
            logger.warning("get_chat failed: %s", e)

        if pinned is not None:
            try:
                caption = pinned.caption or pinned.text or ""
                doc = getattr(pinned, "document", None)
                if doc and (caption.startswith(ROOT_CAPTION) or doc.file_name == "ads_root.json"):
                    raw = await self._download_file(doc.file_id)
                    parsed = json.loads(raw.decode("utf-8"))
                    if isinstance(parsed, dict) and "namespaces" in parsed:
                        root = parsed
                        self.root_msg_id = pinned.message_id
                        self._write_local_cache("root.json", raw)
                        return root
            except Exception as e:
                logger.warning("pinned root read failed: %s", e)

        raw = self._read_local_cache("root.json")
        if raw:
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, dict) and "namespaces" in parsed:
                    return parsed
            except Exception:
                pass
        return root

    async def _commit_root(self, root: Dict[str, Any]):
        payload = json.dumps(root, separators=(",", ":")).encode("utf-8")
        mid, _fid = await self._send_doc(
            payload, "ads_root.json",
            "%s|ns=%s|v=%d" % (ROOT_CAPTION, _short(self.namespace, 8), int(time.time())))
        old = self.root_msg_id
        try:
            await self._call(self.bot.pin_chat_message, self.channel_id, mid,
                             disable_notification=True)
        except Exception as e:
            logger.warning("pin root failed: %s", e)
        if old and old != mid:
            try:
                await self._call(self.bot.unpin_chat_message, self.channel_id, old)
            except Exception:
                pass
            try:
                await self._call(self.bot.delete_message, self.channel_id, old)
            except Exception:
                pass
        self.root_msg_id = mid
        self._write_local_cache("root.json", payload)

    async def _commit_index(self):
        payload = json.dumps(self.index, separators=(",", ":")).encode("utf-8")
        mid, _fid = await self._send_doc(
            payload, "ads_index_%s.json" % _short(self.namespace, 8),
            "%s_INDEX|ns=%s|v=%d" % (DATA_MARK, _short(self.namespace, 8), self.version))
        old = self.index_msg_id
        self.index_msg_id = mid
        self._write_local_cache("index.json", payload)

        root = await self._load_root()
        root.setdefault("namespaces", {})[self.namespace] = {
            "index_msg_id": mid,
            "index_file_id": _fid,
            "version": self.version,
            "updated": int(time.time()),
        }
        await self._commit_root(root)

        if old and old != mid:
            try:
                await self._call(self.bot.delete_message, self.channel_id, old)
            except Exception:
                pass
        self.last_sync = time.time()

    # ------------------------------------------------------------- public async
    async def initialize(self, bot=None) -> bool:
        if bot is not None:
            self.bot = bot
        if not self.enabled or self.bot is None:
            self.last_error = "STORAGE_CHANNEL_ID not set"
            logger.error("Telegram storage disabled: %s", self.last_error)
            return False
        try:
            root = await self._load_root()
            info = root.get("namespaces", {}).get(self.namespace, {})
            if info.get("index_msg_id"):
                self.index_msg_id = info["index_msg_id"]
                raw = None
                if info.get("index_file_id"):
                    try:
                        raw = await self._download_file(info["index_file_id"])
                    except Exception as e:
                        logger.warning("index download failed: %s", e)
                if raw is None:
                    raw = self._read_local_cache("index.json")
                parsed = None
                if raw:
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                    except Exception:
                        parsed = None
                if not isinstance(parsed, dict) or parsed.get("namespace") != self.namespace:
                    raise RuntimeError("index unrecoverable from Telegram; refusing to start empty")
                self.index = parsed
                self.version = int(parsed.get("version", 0) or 0)
                self._write_local_cache("index.json", raw)
            else:
                self.index = {"namespace": self.namespace, "version": 0, "keys": {}}
                await self._commit_index()

            self.available = True
            self.last_error = ""
            self.last_sync = time.time()
            await self._preload_json_keys()
            logger.info("Telegram storage READY  ns=%s  keys=%d  channel=%s",
                        self.namespace, len(self.index.get("keys", {})), self.channel_id)
            return True
        except Exception as e:
            self.available = False
            self.last_error = str(e)[:300]
            logger.error("Telegram storage init failed: %s", self.last_error)
            return False

    async def _preload_json_keys(self):
        keys = [k for k in self.index.get("keys", {})
                if k.endswith(":data") or k.startswith("config:") or k.startswith("meta:")]
        if not keys:
            return
        sem = asyncio.Semaphore(3)

        async def one(k):
            async with sem:
                try:
                    raw = await self.get_bytes(k, use_cache=False)
                    self._json_cache[k] = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    logger.warning("preload %s failed: %s", k, e)

        await asyncio.gather(*[one(k) for k in keys[:2000]])

    async def put_bytes(self, key: str, data: bytes, content_type="application/octet-stream",
                        commit=True) -> Dict[str, Any]:
        if not data and data != b"":
            raise ValueError("empty payload")
        if not self.available:
            raise RuntimeError("storage unavailable: %s" % (self.last_error or "not initialized"))
        meta = await self._upload_blob(key, data, content_type)
        if commit:
            async with self._lock:
                old = self.index.get("keys", {}).get(key)
                self.index.setdefault("keys", {})[key] = meta
                self.version += 1
                self.index["version"] = self.version
                self.index["updated"] = int(time.time())
                await self._commit_index()
                if old:
                    await self._delete_meta(old)
        self._stats["writes"] += 1
        self._cache_put(key, data)
        return meta

    async def get_bytes(self, key: str, use_cache=True) -> bytes:
        if use_cache:
            hit = self._cache_get(key)
            if hit is not None:
                return hit
        meta = self.index.get("keys", {}).get(key)
        if not meta:
            raise KeyError("storage key not found: %s" % key)
        buf = bytearray()
        for rec in meta.get("chunks", []):
            part = await self._download_file(rec["file_id"])
            if _sha256(part) != rec.get("sha"):
                raise RuntimeError("chunk checksum mismatch for %s" % key)
            buf.extend(part)
        data = bytes(buf)
        if _sha256(data) != meta.get("sha"):
            raise RuntimeError("checksum mismatch for %s" % key)
        self._stats["reads"] += 1
        self._cache_put(key, data)
        return data

    async def delete(self, key: str) -> bool:
        async with self._lock:
            meta = self.index.get("keys", {}).pop(key, None)
            if not meta:
                return False
            self.version += 1
            self.index["version"] = self.version
            self.index["updated"] = int(time.time())
            await self._commit_index()
            await self._delete_meta(meta)
        self._json_cache.pop(key, None)
        self._blob_cache.pop(key, None)
        self._stats["deletes"] += 1
        return True

    async def put_json_async(self, key: str, obj: Any, commit=True) -> Dict[str, Any]:
        payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        meta = await self.put_bytes(key, payload, "application/json", commit=commit)
        self._json_cache[key] = obj
        return meta

    async def flush_logs(self):
        if not self.available:
            return
        for key, lines in list(self._log_buffers.items()):
            if not lines:
                continue
            text = "".join(lines)
            self._log_buffers[key] = []
            try:
                old = self._log_bases.get(key)
                if old is None:
                    old = b""
                    if key in self.index.get("keys", {}):
                        try:
                            old = await self.get_bytes(key, use_cache=False)
                        except Exception:
                            old = b""
                merged = (old + text.encode("utf-8"))[-512 * 1024:]
                await self.put_bytes(key, merged, "text/plain")
                self._log_bases[key] = merged
            except Exception as e:
                logger.warning("log flush failed %s: %s", key, e)
                self._log_buffers[key] = lines + self._log_buffers.get(key, [])

    # --------------------------------------------------------------- sync facade
    def get_json(self, key: str, default=None):
        if key in self._json_cache:
            return self._json_cache[key]
        raw = self._read_local_cache("kv_" + self.key_hash(key) + ".json")
        if raw:
            try:
                obj = json.loads(raw.decode("utf-8"))
                self._json_cache[key] = obj
                return obj
            except Exception:
                pass
        return default

    def put_json(self, key: str, obj: Any, debounce=None):
        try:
            payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except Exception as e:
            logger.error("json encode failed %s: %s", key, e)
            return
        self._json_cache[key] = obj
        self._pending[key] = payload
        if not key.startswith("user:"):
            self._write_local_cache("kv_" + self.key_hash(key) + ".json", payload)
        self._ensure_flusher()

    def append_log(self, key: str, line: str):
        buf = self._log_buffers.setdefault(key, [])
        buf.append(line if line.endswith("\n") else line + "\n")
        if len(buf) > 4000:
            del buf[:1000]
        try:
            self._ensure_log_flusher()
        except Exception:
            pass

    def _ensure_flusher(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._flusher is None or self._flusher.done():
            self._flusher = loop.create_task(self._flush_loop())

    def _ensure_log_flusher(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._log_flusher is None or self._log_flusher.done():
            self._log_flusher = loop.create_task(self._log_loop())

    async def _flush_loop(self):
        while self._pending:
            if not self.available:
                await asyncio.sleep(30)
                continue
            await asyncio.sleep(self.debounce)
            snapshot = list(self._pending.items())
            for key, payload in snapshot:
                if self._pending.get(key) is not payload:
                    continue
                try:
                    meta = await self._upload_blob(key, payload, "application/json")
                    async with self._lock:
                        old = self.index.get("keys", {}).get(key)
                        self.index.setdefault("keys", {})[key] = meta
                        self.version += 1
                        self.index["version"] = self.version
                        self.index["updated"] = int(time.time())
                        await self._commit_index()
                        if old:
                            await self._delete_meta(old)
                    if self._pending.get(key) is payload:
                        self._pending.pop(key, None)
                    self._stats["writes"] += 1
                    self.last_error = ""
                except Exception as e:
                    self._stats["errors"] += 1
                    self.last_error = str(e)[:300]
                    logger.error("storage flush %s failed: %s", key, e)
                    await asyncio.sleep(5)

    async def _log_loop(self):
        while True:
            await asyncio.sleep(self._log_interval)
            try:
                await self.flush_logs()
            except Exception as e:
                logger.warning("log loop: %s", e)

    async def flush(self):
        for _ in range(3):
            if not self._pending:
                break
            try:
                await self._flush_once()
            except Exception as e:
                logger.error("flush error: %s", e)
                await asyncio.sleep(2)
        try:
            await self.flush_logs()
        except Exception:
            pass

    async def _flush_once(self):
        snapshot = list(self._pending.items())
        for key, payload in snapshot:
            if self._pending.get(key) is not payload:
                continue
            meta = await self._upload_blob(key, payload, "application/json")
            async with self._lock:
                old = self.index.get("keys", {}).get(key)
                self.index.setdefault("keys", {})[key] = meta
                self.version += 1
                self.index["version"] = self.version
                self.index["updated"] = int(time.time())
                await self._commit_index()
                if old:
                    await self._delete_meta(old)
            if self._pending.get(key) is payload:
                self._pending.pop(key, None)

    # ------------------------------------------------------------------- queries
    def list_keys(self, prefix: str = "") -> List[str]:
        keys = list(self.index.get("keys", {}))
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return sorted(keys)

    def search(self, contains: str = "", prefix: str = "") -> List[Dict[str, Any]]:
        out = []
        for k in self.list_keys(prefix):
            if contains and contains.lower() not in k.lower():
                continue
            meta = self.index["keys"][k]
            out.append({"key": k, "size": meta.get("size", 0),
                        "updated": meta.get("updated", 0)})
        return out

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "channel": self.channel_id,
            "namespace": self.namespace,
            "keys": len(self.index.get("keys", {})),
            "version": self.version,
            "pending": len(self._pending),
            "chunk_size": self.chunk_size,
            "last_sync": self.last_sync,
            "last_error": self.last_error,
            "stats": dict(self._stats),
        }

    async def fetch_json(self, key: str, default=None):
        try:
            raw = await self.get_bytes(key)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return default

    async def export_keys(self, prefix: str = "") -> Dict[str, bytes]:
        result = {}
        for key in self.list_keys(prefix):
            try:
                result[key] = await self.get_bytes(key, use_cache=False)
            except Exception as e:
                logger.warning("export %s failed: %s", key, e)
        return result

    def _cache_put(self, key: str, data: bytes):
        now = time.time()
        self._blob_cache[key] = (data, now + self._cache_ttl)
        if len(self._blob_cache) > 64:
            oldest = sorted(self._blob_cache.items(), key=lambda kv: kv[1][1])[:16]
            for k, _ in oldest:
                self._blob_cache.pop(k, None)

    def _cache_get(self, key: str) -> Optional[bytes]:
        item = self._blob_cache.get(key)
        if not item:
            return None
        data, exp = item
        if time.time() > exp:
            self._blob_cache.pop(key, None)
            return None
        return data


STORAGE = TelegramStorage()

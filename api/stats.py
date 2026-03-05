from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timezone, timedelta


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Track a conversion from the client-side converter."""
        url = os.environ.get("UPSTASH_REDIS_REST_URL")
        token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token:
            self._json(200, {"ok": True})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}
            file_count = int(body.get("files", 0))
            page_count = int(body.get("pages", 0))

            from upstash_redis import Redis
            redis = Redis(url=url, token=token)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            pipe = redis.pipeline()
            pipe.incr("stats:total_conversions")
            pipe.incrby("stats:total_files", file_count)
            pipe.incrby("stats:total_pages", page_count)
            pipe.incr(f"stats:daily:{today}")
            pipe.execute()
        except Exception:
            pass

        self._json(200, {"ok": True})

    def do_GET(self):
        url = os.environ.get("UPSTASH_REDIS_REST_URL")
        token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token:
            self._json(500, {"error": "Redis nicht konfiguriert"})
            return

        try:
            from upstash_redis import Redis
            redis = Redis(url=url, token=token)

            total_conversions = int(redis.get("stats:total_conversions") or 0)
            total_files = int(redis.get("stats:total_files") or 0)
            total_pages = int(redis.get("stats:total_pages") or 0)

            # Last 30 days
            today = datetime.now(timezone.utc)
            daily = {}
            keys = []
            for i in range(30):
                day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                keys.append(f"stats:daily:{day}")

            values = redis.mget(*keys) if keys else []
            for i, val in enumerate(values):
                day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                daily[day] = int(val or 0)

            self._json(200, {
                "total_conversions": total_conversions,
                "total_files": total_files,
                "total_pages": total_pages,
                "daily": daily,
            })
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

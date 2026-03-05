from http.server import BaseHTTPRequestHandler
import io
import json
from PIL import Image


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._error(400, "Keine Datei hochgeladen")
            return

        # Max 50 MB
        if content_length > 50 * 1024 * 1024:
            self._error(413, "Datei zu gross (max 50 MB)")
            return

        body = self.rfile.read(content_length)

        # Parse multipart form data manually
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._error(400, "Content-Type muss multipart/form-data sein")
            return

        boundary = content_type.split("boundary=")[1].strip()
        parts = body.split(f"--{boundary}".encode())

        files = []
        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            # Split headers from body
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            part_body = part[header_end + 4:]
            # Remove trailing \r\n
            if part_body.endswith(b"\r\n"):
                part_body = part_body[:-2]
            if len(part_body) == 0:
                continue
            files.append(part_body)

        if not files:
            self._error(400, "Keine TIFF-Dateien gefunden")
            return

        try:
            pages = []
            for file_data in files:
                img = Image.open(io.BytesIO(file_data))
                for i in range(getattr(img, "n_frames", 1)):
                    img.seek(i)
                    pages.append(img.copy().convert("RGB"))

            pdf_buffer = io.BytesIO()
            if len(pages) == 1:
                pages[0].save(pdf_buffer, format="PDF", resolution=150.0)
            else:
                pages[0].save(
                    pdf_buffer,
                    format="PDF",
                    save_all=True,
                    append_images=pages[1:],
                    resolution=150.0,
                )

            pdf_bytes = pdf_buffer.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", 'attachment; filename="converted.pdf"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self._error(500, f"Konvertierungsfehler: {str(e)}")

    def _error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

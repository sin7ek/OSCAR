"""Prepare an edition-bound front cover for explicit archive approval."""
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, ImageOps, UnidentifiedImageError

from oscar import discogs_readonly, musicbrainz
from oscar.boxsets import RELEASE_ID
from oscar.mb_client import fetch_json

MAX_UPLOAD = 8 * 1024 * 1024
_MAX_PIXELS = 24_000_000
_MAX_EDGE = 1600
_NAME = ".reviewed-front-cover.json"
_HOSTS = {"coverartarchive.org", "archive.org", "i.discogs.com", "img.discogs.com"}


class CoverError(ValueError):
    pass


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _image_url(url):
    parts = urlparse(url)
    host = parts.hostname or ""
    if (parts.scheme not in {"http", "https"} or parts.username or parts.password
            or parts.port not in {None, 443}
            or (host not in _HOSTS and not host.endswith(".archive.org"))):
        raise CoverError("Unexpected cover image host")
    return urlunparse(parts._replace(scheme="https"))


class _CoverRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _image_url(newurl))


def _download(url):
    request = Request(_image_url(url), headers={"User-Agent": musicbrainz._UA,
                                               "Accept": "image/jpeg,image/png,image/webp"})
    with build_opener(_CoverRedirect()).open(request, timeout=12) as response:
        raw = response.read(MAX_UPLOAD + 1)
    return raw


def _normalize(raw):
    if not 0 < len(raw) <= MAX_UPLOAD:
        raise CoverError("Choose a JPEG, PNG or WebP image up to 8 MiB")
    try:
        with Image.open(BytesIO(raw), formats=("JPEG", "PNG", "WEBP")) as image:
            if image.width * image.height > _MAX_PIXELS or getattr(image, "is_animated", False):
                raise CoverError("Cover must be a still image of at most 24 megapixels")
            upright = ImageOps.exif_transpose(image)
            upright.thumbnail((_MAX_EDGE, _MAX_EDGE), Image.Resampling.LANCZOS)
            rgba = upright.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, "white")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
            output = BytesIO()
            rgb.save(output, "JPEG", quality=92, optimize=True)
            return output.getvalue(), rgb.size
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise CoverError("The cover could not be decoded as JPEG, PNG or WebP") from exc


def _discogs_release(release_id):
    request = Request(f"https://musicbrainz.org/ws/2/release/{release_id}?inc=url-rels&fmt=json",
                      headers={"User-Agent": musicbrainz._UA, "Accept": "application/json"})
    result = fetch_json(request)
    if result.get("id") != release_id:
        return None
    links = set()
    for relation in result.get("relations", []):
        url = (relation.get("url") or {}).get("resource", "")
        if relation.get("type") == "discogs" and url:
            try:
                value = discogs_readonly.pressing_release_id(url)
            except discogs_readonly.DiscogsError:
                continue
            if value:
                links.add(value)
    return next(iter(links)) if len(links) == 1 else None


def _source_image(source, release_id, discogs_release):
    if source == "musicbrainz":
        url = f"https://coverartarchive.org/release/{release_id}/front-1200"
        try:
            return _download(url), url
        except HTTPError as exc:
            if exc.code != 404:
                raise
            url = f"https://coverartarchive.org/release/{release_id}/front"
            return _download(url), url
    if not discogs_readonly.configured():
        raise CoverError("Discogs artwork requires the configured personal token")
    chosen = discogs_readonly.pressing_release_id(discogs_release) or _discogs_release(release_id)
    if not chosen:
        raise CoverError("No unique Discogs release link; enter the Discogs release ID or URL")
    info = discogs_readonly._get(f"/releases/{chosen}")
    if info.get("id") != chosen or not any(
        f.get("name") == "CD" for f in info.get("formats", []) if isinstance(f, dict)
    ):
        raise CoverError("The Discogs listing is not a matching CD candidate")
    front = next((image.get("uri") for image in info.get("images", [])
                  if image.get("type") == "primary" and image.get("uri")), None)
    if not front:
        raise CoverError("Discogs returned no primary image for this release")
    if urlparse(front).hostname not in {"i.discogs.com", "img.discogs.com"}:
        raise CoverError("Unexpected Discogs image host")
    return _download(front), f"https://www.discogs.com/release/{chosen}"


def load(folder, release_id):
    path = folder / _NAME
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_UPLOAD * 2:
        raise CoverError("Unsafe saved cover selection")
    value = json.loads(path.read_text(encoding="utf-8"))
    raw = base64.b64decode(value.pop("jpeg"), validate=True)
    if value["release_id"] != release_id or _digest(raw) != value["sha256"]:
        raise CoverError("Saved cover no longer matches its review evidence")
    return value, raw


def select(folder, release_id, source, *, upload=b"", discogs_release=""):
    if not RELEASE_ID.fullmatch(release_id):
        raise CoverError("Invalid MusicBrainz release ID")
    if source == "auto":
        previous = load(folder, release_id)
        if previous:
            return previous
        providers = ("musicbrainz", "discogs")
    else:
        providers = (source,)
    for provider in providers:
        try:
            if provider == "upload":
                raw, url = upload, None
            else:
                raw, url = _source_image(provider, release_id, discogs_release)
            jpeg, (width, height) = _normalize(raw)
        except (CoverError, OSError, URLError, musicbrainz.MusicBrainzError,
                discogs_readonly.DiscogsError) as exc:
            if source == "auto":
                continue
            if isinstance(exc, CoverError):
                raise
            raise CoverError("Cover source is unavailable") from exc
        summary = {"release_id": release_id, "provider": provider, "source": url,
                   "sha256": _digest(jpeg), "width": width, "height": height,
                   "filename": "folder.jpg", "mime": "image/jpeg"}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, delete=False) as out:
            temp = Path(out.name)
            try:
                json.dump({**summary, "jpeg": base64.b64encode(jpeg).decode("ascii")}, out)
                out.close()
                os.replace(temp, folder / _NAME)
            finally:
                temp.unlink(missing_ok=True)
        return summary, jpeg
    return None

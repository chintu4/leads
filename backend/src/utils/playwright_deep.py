from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag


logger = logging.getLogger(__name__)


ProgressCallback = Callable[[Dict[str, Any]], None]


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}"
)


@dataclass(frozen=True)
class CrawlConfig:
    max_pages: int = 25
    max_depth: int = 3
    total_timeout_s: int = 120
    navigation_timeout_ms: int = 45_000
    same_domain_only: bool = True
    deny_domains: Tuple[str, ...] = (
        # Default deny list for sites that often block automation or require auth.
        # We still *extract* links pointing to these.
        "linkedin.com",
        "www.linkedin.com",
    )


def _normalize_url(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None

    href = href.strip()
    if not href or href.startswith("#"):
        return None

    lowered = href.lower()
    if lowered.startswith(("mailto:", "tel:", "javascript:")):
        return None

    abs_url = urljoin(base_url, href)
    abs_url, _frag = urldefrag(abs_url)

    try:
        parsed = urlparse(abs_url)
    except Exception:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    # Normalize: remove default ports
    netloc = parsed.netloc
    if netloc.endswith(":80") and parsed.scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and parsed.scheme == "https":
        netloc = netloc[:-4]

    normalized = parsed._replace(netloc=netloc).geturl()
    return normalized


def _is_same_domain(seed: str, candidate: str) -> bool:
    try:
        a = urlparse(seed)
        b = urlparse(candidate)
        ah = a.hostname.replace("www.", "").lower() if a.hostname else ""
        bh = b.hostname.replace("www.", "").lower() if b.hostname else ""
        return ah == bh
    except Exception:
        return False


def _looks_like_people_directory(u: str) -> bool:
    path = (urlparse(u).path or "").lower()
    tokens = ("/team", "/people", "/leadership", "/about", "/our-team", "/staff", "/management")
    return any(t in path for t in tokens)


def _safe_json_loads(s: str) -> Optional[Any]:
    try:
        return json.loads(s)
    except Exception:
        return None


def _iter_json_objects(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_json_objects(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_json_objects(it)


def _extract_people_from_jsonld(jsonld_texts: List[str]) -> List[Dict[str, Any]]:
    people: List[Dict[str, Any]] = []

    for raw in jsonld_texts:
        if not raw or not raw.strip():
            continue

        parsed = _safe_json_loads(raw)
        if parsed is None:
            continue

        for obj in _iter_json_objects(parsed):
            t = obj.get("@type") or obj.get("type")
            if isinstance(t, list):
                is_person = any(str(x).lower() == "person" for x in t)
            else:
                is_person = str(t).lower() == "person"

            if not is_person:
                continue

            same_as = obj.get("sameAs") or obj.get("same_as") or []
            if isinstance(same_as, str):
                same_as = [same_as]

            profile_url = ""
            for s in same_as:
                if isinstance(s, str) and "linkedin.com/in/" in s:
                    profile_url = s
                    break

            works_for = obj.get("worksFor")
            company = ""
            if isinstance(works_for, dict):
                company = works_for.get("name") or ""
            elif isinstance(works_for, list):
                company = next((wf.get("name") for wf in works_for if isinstance(wf, dict) and wf.get("name")), "")

            person: Dict[str, Any] = {
                "name": obj.get("name") or "",
                "title": obj.get("jobTitle") or obj.get("job_title") or "",
                "company": company,
                "email": obj.get("email") or "",
                "phone": obj.get("telephone") or obj.get("phone") or "",
                # More general: a person's public profile URL
                "profile_url": profile_url,
                # Backward-compat alias (existing code/UI expects linkedin_url).
                "linkedin_url": profile_url,
            }

            people.append(person)

    return people


def _extract_contacts(text: str) -> Tuple[List[str], List[str]]:
    emails = []
    phones = []

    if text:
        emails = list({e for e in _EMAIL_RE.findall(text) if "example.com" not in e.lower()})
        phones = list({p.strip() for p in _PHONE_RE.findall(text) if p and len(re.sub(r"\D", "", p)) >= 7})

    return emails[:10], phones[:10]


def crawl_people_deep(
    start_url: str,
    *,
    config: Optional[CrawlConfig] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """Crawl a site using Playwright, following internal links, extracting people signals.

    Outputs a list of "person" dicts (name/title/company/email/phone/profile_url) plus
    a few metadata fields: source_url, page_url.

    Notes:
    - By default it only visits URLs on the same domain as start_url.
    - It does NOT attempt to bypass logins or scrape restricted sites.
    """

    cfg = config or CrawlConfig()

    visited: Set[str] = set()
    queued: Set[str] = set()

    start_url_norm = _normalize_url(start_url, start_url)
    if not start_url_norm:
        return []

    q: List[Tuple[str, int]] = [(start_url_norm, 0)]
    queued.add(start_url_norm)

    people_out: List[Dict[str, Any]] = []
    seen_people_keys: Set[str] = set()

    deadline = time.time() + max(5, int(cfg.total_timeout_s))

    def emit(evt: Dict[str, Any]) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(evt)
        except Exception:
            logger.exception("progress_callback failed")

    # Local import to avoid adding startup cost when module is imported
    try:
        from src.utils.profile import is_profile_url
    except Exception:
        # Fallback stub; safest default is to not mark things as profiles
        def is_profile_url(url: str, page_text: Optional[str] = None, jsonld_texts: Optional[List[str]] = None):
            return (False, 0)

    # Import Playwright lazily inside the function to avoid import-time side effects
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except Exception:
        # We don't raise here; the caller will handle unavailability when attempting to crawl
        sync_playwright = None  # type: ignore
        PlaywrightTimeoutError = Exception  # type: ignore

    if sync_playwright is None:
        # If Playwright isn't installed, emit and return early from the function
        emit({"type": "progress", "phase": "deep", "msg": f"playwright not available, skipping deep crawl: {start_url_norm}"})
        return people_out

    emit({"type": "progress", "phase": "deep", "msg": f"deep crawl started: {start_url_norm}"})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Speed: block heavy resources
        def _route(route, request):
            try:
                if request.resource_type in ("image", "media", "font"):
                    route.abort()
                else:
                    route.continue_()
            except Exception:
                try:
                    route.continue_()
                except Exception:
                    pass

        try:
            context.route("**/*", _route)
        except Exception:
            # Some environments disallow routing; continue without it.
            pass

        page = context.new_page()
        page.set_default_timeout(cfg.navigation_timeout_ms)

        pages_visited = 0

        while q and pages_visited < cfg.max_pages and time.time() < deadline:
            url, depth = q.pop(0)
            if url in visited:
                continue
            visited.add(url)

            # Skip denied domains (still allow extraction from pages we did visit).
            try:
                host = (urlparse(url).hostname or "").lower()
            except Exception:
                host = ""
            if host in cfg.deny_domains:
                continue

            emit({"type": "progress", "phase": "deep", "url": url, "depth": depth})

            try:
                page.goto(url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                emit({"type": "error", "phase": "deep", "url": url, "msg": "navigation timeout"})
                continue
            except Exception as e:
                emit({"type": "error", "phase": "deep", "url": url, "msg": str(e)})
                continue

            pages_visited += 1

            # Extract content
            try:
                title = page.title() or ""
            except Exception:
                title = ""

            try:
                body_text = page.inner_text("body")
            except Exception:
                body_text = ""

            emails, phones = _extract_contacts(body_text)

            # Extract anchor links (href + visible text)
            try:
                anchors = page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(a => ({href: a.getAttribute('href') || '', text: (a.innerText || '').trim()}))",
                )
            except Exception:
                anchors = []

            # Extract json-ld blobs
            try:
                jsonlds = page.eval_on_selector_all(
                    'script[type="application/ld+json"]',
                    "els => els.map(s => s.textContent || '')",
                )
            except Exception:
                jsonlds = []

            people = _extract_people_from_jsonld([str(x) for x in (jsonlds or [])])

            # Heuristic: LinkedIn person profile links found on-page
            for a in anchors or []:
                href = str(a.get("href") or "")
                text = str(a.get("text") or "")
                abs_u = _normalize_url(url, href)
                if not abs_u:
                    continue
                if "linkedin.com/in/" in abs_u:
                    people.append(
                        {
                            "name": text,
                            "title": "",
                            "company": "",
                            "email": "",
                            "phone": "",
                            "profile_url": abs_u,
                            "linkedin_url": abs_u,
                        }
                    )

                # Use the profile URL heuristic to detect other profile links
                try:
                    is_profile, score = is_profile_url(abs_u, page_text=body_text, jsonld_texts=jsonlds)
                except Exception:
                    is_profile, score = False, 0

                if is_profile:
                    # If it's a profile link but not already captured, add as a person
                    people.append(
                        {
                            "name": text,
                            "title": "",
                            "company": "",
                            "email": "",
                            "phone": "",
                            "profile_url": abs_u,
                            "linkedin_url": abs_u if "linkedin.com" in abs_u else "",
                            "_profile_score": score,
                        }
                    )

            # Attach metadata and de-dupe
            for person in people:
                profile_url = (person.get("profile_url") or "").strip()
                linkedin_url = (person.get("linkedin_url") or profile_url).strip()
                email = (person.get("email") or "").strip().lower()
                name = (person.get("name") or "").strip().lower()

                key = profile_url or linkedin_url or email or (name + "|" + url)
                if not key or key in seen_people_keys:
                    continue

                seen_people_keys.add(key)

                enriched = {
                    **person,
                    "profile_url": profile_url or linkedin_url,
                    "page_url": url,
                    "source_url": start_url_norm,
                    "page_title": title,
                    "page_emails": emails,
                    "page_phones": phones,
                    "page_text": (body_text or "")[:2000],
                }
                people_out.append(enriched)

            # Enqueue next links
            if depth < cfg.max_depth:
                # prefer directory pages early
                next_links: List[str] = []
                preferred: List[str] = []

                for a in anchors or []:
                    href = str(a.get("href") or "")
                    abs_u = _normalize_url(url, href)
                    if not abs_u:
                        continue
                    if abs_u in visited or abs_u in queued:
                        continue

                    if cfg.same_domain_only and not _is_same_domain(start_url_norm, abs_u):
                        continue

                    if "linkedin.com" in abs_u:
                        # keep as extracted link, but don't crawl
                        continue

                    if _looks_like_people_directory(abs_u):
                        preferred.append(abs_u)
                    else:
                        # Prioritize single-person profile links as preferred so we crawl them early
                        try:
                            is_profile, _score = is_profile_url(abs_u)
                        except Exception:
                            is_profile = False
                        if is_profile:
                            preferred.append(abs_u)
                        else:
                            next_links.append(abs_u)

                # Add preferred links first
                for link in preferred + next_links:
                    if link in visited or link in queued:
                        continue
                    queued.add(link)
                    q.append((link, depth + 1))

        try:
            page.close()
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    emit({"type": "progress", "phase": "deep", "msg": f"deep crawl done: pages={len(visited)} people={len(people_out)}"})
    return people_out

"""Web Analysis Tracker for ralph-gold.

This tracker performs reconnaissance on web applications to discover and generate
tasks for issues, optimizations, and areas needing investigation.

Example .ralph/config.toml configuration:

    [tracker]
    kind = "web_analysis"

    [tracker.web]
    base_url = "https://example.com"
    sitemap_url = ""  # Optional: defaults to {base_url}/sitemap.xml
    crawl_depth = 2
    max_pages = 100
    api_discovery = true
    js_analysis = true
    normalize_hashes = true
    headless_nav = false
    cache_ttl_seconds = 3600
    output_path = ".ralph/web_analysis.json"
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests

from ..config import WebTrackerConfig
from ..prd import SelectedTask, TaskId

logger = logging.getLogger(__name__)


# Optional dependencies for enhanced functionality
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class WebEndpoint:
    """Represents a discovered web endpoint."""

    url: str
    method: str = "GET"
    content_type: str = ""
    group: str = "default"
    normalized_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.normalized_url:
            self.normalized_url = normalize_url(self.url, strip_hash=False)


@dataclass
class WebAnalysisResult:
    """Results from web analysis."""

    base_url: str
    scanned_at: str
    endpoints: List[WebEndpoint] = field(default_factory=list)
    api_endpoints: List[WebEndpoint] = field(default_factory=list)
    js_bundles: List[WebEndpoint] = field(default_factory=list)
    pages: List[WebEndpoint] = field(default_factory=list)
    tasks: List[SelectedTask] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "base_url": self.base_url,
            "scanned_at": self.scanned_at,
            "endpoints": [
                {
                    "url": e.url,
                    "method": e.method,
                    "content_type": e.content_type,
                    "group": e.group,
                    "normalized_url": e.normalized_url,
                    "metadata": e.metadata,
                }
                for e in self.endpoints
            ],
            "api_endpoints": [
                {
                    "url": e.url,
                    "method": e.method,
                    "content_type": e.content_type,
                    "group": e.group,
                }
                for e in self.api_endpoints
            ],
            "js_bundles": [
                {
                    "url": e.url,
                    "group": e.group,
                    "normalized_url": e.normalized_url,
                    "metadata": e.metadata,
                }
                for e in self.js_bundles
            ],
            "pages": [
                {
                    "url": e.url,
                    "group": e.group,
                    "metadata": e.metadata,
                }
                for e in self.pages
            ],
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "kind": t.kind,
                    "acceptance": t.acceptance,
                    "depends_on": t.depends_on,
                    "group": t.group,
                }
                for t in self.tasks
            ],
            "metadata": self.metadata,
        }


# URL normalization patterns
_CACHE_HASH_RE = re.compile(r"\.[a-f0-9]{8,}\.(js|css|png|jpg|jpeg|gif|svg|webp)", re.IGNORECASE)
_QUERY_PARAMS_TO_STRIP = re.compile(r"[?&](fbclid|gclid|utm_source|utm_medium|utm_campaign|utm_term|utm_content)=[^&]*", re.IGNORECASE)


def normalize_url(url: str, strip_hash: bool = True) -> str:
    """Normalize URL by removing cache-busting hashes and unnecessary query params.

    Args:
        url: URL to normalize
        strip_hash: Whether to strip cache-busting hashes

    Returns:
        Normalized URL
    """
    # Strip common tracking query parameters
    url = _QUERY_PARAMS_TO_STRIP.sub("", url)
    # Remove trailing ? or & if params were stripped
    url = re.sub(r"[?&]$", "", url)

    if strip_hash:
        # Strip webpack/cache hashes: /main.abc123def.js -> /main.js
        url = _CACHE_HASH_RE.sub(r".\1", url)

    return url


def extract_url_group(url: str) -> str:
    """Extract a group name from a URL path.

    Examples:
        /api/v1/users -> "api-v1"
        /static/css -> "static"
        /products -> "default"

    Args:
        url: URL to extract group from

    Returns:
        Group name string
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return "default"

    # Get first 2-3 path segments for grouping
    segments = path.split("/")[:2]

    # Common path patterns to group
    if "api" in segments:
        return "-".join(segments)
    if "static" in segments or "assets" in segments or "public" in segments:
        return "static"
    if "admin" in segments:
        return "admin"
    if "auth" in segments or "login" in segments or "signup" in segments:
        return "auth"

    return "-".join(segments) if segments else "default"


@dataclass
class WebTracker:
    """Web Analysis tracker for discovering and tracking web-related tasks.

    This tracker analyzes web applications through:
    - Sitemap-driven crawling to enumerate pages
    - API discovery for data endpoints
    - JavaScript bundle analysis
    - Endpoint normalization for cache-busting hashes
    - Optional headless navigation with Playwright
    - Content taxonomy generation

    Tasks are generated from discovered issues, optimization opportunities,
    and areas needing investigation.
    """

    project_root: Path
    config: WebTrackerConfig
    cache_path: Path
    output_path: Path

    def __init__(
        self,
        project_root: Path,
        base_url: str,
        sitemap_url: str = "",
        crawl_depth: int = 2,
        max_pages: int = 100,
        api_discovery: bool = True,
        js_analysis: bool = True,
        normalize_hashes: bool = True,
        headless_nav: bool = False,
        cache_ttl_seconds: int = 3600,
        output_path: str = ".ralph/web_analysis.json",
    ):
        """Initialize Web Analysis tracker.

        Args:
            project_root: Project root directory
            base_url: Target web application URL
            sitemap_url: Optional explicit sitemap URL (default: {base_url}/sitemap.xml)
            crawl_depth: How deep to crawl (default: 2)
            max_pages: Maximum pages to analyze (default: 100)
            api_discovery: Enable XHR/fetch detection (default: true)
            js_analysis: Enable bundle analysis (default: true)
            normalize_hashes: Remove cache-busting hashes (default: true)
            headless_nav: Enable headless browser navigation (default: false)
            cache_ttl_seconds: Cache duration (default: 3600)
            output_path: Where to save analysis results (default: ".ralph/web_analysis.json")
        """
        self.project_root = project_root

        # Build config
        self.config = WebTrackerConfig(
            base_url=base_url,
            sitemap_url=sitemap_url,
            crawl_depth=crawl_depth,
            max_pages=max_pages,
            api_discovery=api_discovery,
            js_analysis=js_analysis,
            normalize_hashes=normalize_hashes,
            headless_nav=headless_nav,
            cache_ttl_seconds=cache_ttl_seconds,
            output_path=output_path,
        )

        # Setup paths
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = ralph_dir / "web_analysis_cache.json"
        self.output_path = project_root / output_path

        # Normalize base URL
        self.base_url = self.config.base_url.rstrip("/")

        # Derive sitemap URL if not provided
        self.sitemap_url = self.config.sitemap_url or f"{self.base_url}/sitemap.xml"

        # Load or perform analysis
        self._result = self._load_or_analyze()

    @property
    def kind(self) -> str:
        """Return tracker kind identifier."""
        return "web_analysis"

    def _cache_is_fresh(self) -> bool:
        """Check if cache is fresh (within TTL)."""
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path, "r") as f:
                cache_data = json.load(f)

            cached_at = cache_data.get("scanned_at")
            if not cached_at:
                return False

            cached_time = datetime.fromisoformat(cached_at)
            age = datetime.now() - cached_time

            return age.total_seconds() < self.config.cache_ttl_seconds

        except (json.JSONDecodeError, ValueError, KeyError):
            return False

    def _load_cache(self) -> Optional[WebAnalysisResult]:
        """Load analysis from cache."""
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)

            # Reconstruct endpoints
            endpoints = [
                WebEndpoint(
                    url=e["url"],
                    method=e.get("method", "GET"),
                    content_type=e.get("content_type", ""),
                    group=e.get("group", "default"),
                    normalized_url=e.get("normalized_url", ""),
                    metadata=e.get("metadata", {}),
                )
                for e in data.get("endpoints", [])
            ]

            # Reconstruct API endpoints
            api_endpoints = [
                WebEndpoint(
                    url=e["url"],
                    method=e.get("method", "GET"),
                    content_type=e.get("content_type", ""),
                    group=e.get("group", "default"),
                )
                for e in data.get("api_endpoints", [])
            ]

            # Reconstruct JS bundles
            js_bundles = [
                WebEndpoint(
                    url=e["url"],
                    group=e.get("group", "default"),
                    normalized_url=e.get("normalized_url", ""),
                    metadata=e.get("metadata", {}),
                )
                for e in data.get("js_bundles", [])
            ]

            # Reconstruct pages
            pages = [
                WebEndpoint(
                    url=e["url"],
                    group=e.get("group", "default"),
                    metadata=e.get("metadata", {}),
                )
                for e in data.get("pages", [])
            ]

            # Reconstruct tasks
            tasks = [
                SelectedTask(
                    id=t["id"],
                    title=t["title"],
                    kind=t.get("kind", "web_analysis"),
                    acceptance=t.get("acceptance", []),
                    depends_on=t.get("depends_on", []),
                    group=t.get("group", "default"),
                )
                for t in data.get("tasks", [])
            ]

            return WebAnalysisResult(
                base_url=data.get("base_url", ""),
                scanned_at=data.get("scanned_at", ""),
                endpoints=endpoints,
                api_endpoints=api_endpoints,
                js_bundles=js_bundles,
                pages=pages,
                tasks=tasks,
                metadata=data.get("metadata", {}),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug("Failed to load cache: %s", e)
            return None

    def _save_cache(self, result: WebAnalysisResult) -> None:
        """Save analysis to cache."""
        with open(self.cache_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def _load_or_analyze(self) -> WebAnalysisResult:
        """Load from cache or perform fresh analysis."""
        if self._cache_is_fresh():
            cached = self._load_cache()
            if cached:
                return cached

        # Perform fresh analysis
        result = self._analyze()

        # Save to cache
        self._save_cache(result)

        # Also save to output path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        return result

    def _analyze(self) -> WebAnalysisResult:
        """Perform web analysis.

        Returns:
            WebAnalysisResult with discovered endpoints and generated tasks
        """
        result = WebAnalysisResult(
            base_url=self.base_url,
            scanned_at=datetime.now().isoformat(),
        )

        # Step 1: Discover pages from sitemap (or headless if enabled)
        headless_discovered: List[WebEndpoint] = []
        if self.config.headless_nav and PLAYWRIGHT_AVAILABLE:
            discovered = self._discover_with_headless()
            # Separate pages from API endpoints discovered during headless navigation
            pages = [e for e in discovered if e.metadata.get("source") != "headless-network"]
            headless_discovered = [e for e in discovered if e.metadata.get("source") == "headless-network"]
        else:
            if self.config.headless_nav and not PLAYWRIGHT_AVAILABLE:
                logger.warning(
                    "headless_nav is enabled but Playwright is not installed. "
                    "Falling back to sitemap-based discovery. "
                    "Install with: uv add --optional web-headless"
                )
            pages = self._discover_from_sitemap()
        result.pages = pages

        # Step 2: Discover API endpoints from pages
        api_endpoints: List[WebEndpoint] = []
        if self.config.api_discovery:
            # Only scan actual pages, not headless-discovered API endpoints
            actual_pages = [p for p in pages if p.metadata.get("source") != "headless-network"]
            api_endpoints = self._discover_api_endpoints(actual_pages)

        # Merge with headless-discovered API endpoints
        api_endpoints.extend(headless_discovered)
        result.api_endpoints = api_endpoints

        # Step 3: Analyze JavaScript bundles
        if self.config.js_analysis:
            js_bundles = self._analyze_js_bundles(pages)
            result.js_bundles = js_bundles

        # Step 4: Compile all endpoints
        all_endpoints: List[WebEndpoint] = []
        all_endpoints.extend(result.pages)
        all_endpoints.extend(result.api_endpoints)
        all_endpoints.extend(result.js_bundles)
        result.endpoints = all_endpoints

        # Step 5: Generate tasks from findings
        tasks = self._generate_tasks(result)
        result.tasks = tasks

        # Add metadata
        result.metadata = {
            "pages_count": len(result.pages),
            "api_endpoints_count": len(result.api_endpoints),
            "js_bundles_count": len(result.js_bundles),
            "total_endpoints": len(all_endpoints),
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "headless_nav_used": self.config.headless_nav and PLAYWRIGHT_AVAILABLE,
            "headless_discovered_apis": len(headless_discovered),
            "config": {
                "crawl_depth": self.config.crawl_depth,
                "max_pages": self.config.max_pages,
                "api_discovery": self.config.api_discovery,
                "js_analysis": self.config.js_analysis,
                "normalize_hashes": self.config.normalize_hashes,
                "headless_nav": self.config.headless_nav,
            },
        }

        return result

    def _discover_from_sitemap(self) -> List[WebEndpoint]:
        """Discover pages from sitemap.xml.

        Returns:
            List of WebEndpoint for discovered pages
        """
        pages: List[WebEndpoint] = []
        seen_urls: Set[str] = set()

        try:
            response = requests.get(self.sitemap_url, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # Handle standard sitemap format
            namespaces = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = root.findall(".//ns:url", namespaces) or root.findall(".//url")

            for url_elem in urls[: self.config.max_pages]:
                loc_elem = url_elem.find("loc") or url_elem.find(
                    "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
                )
                if loc_elem is not None and loc_elem.text:
                    url = loc_elem.text.strip()
                    # Only include URLs under base_url
                    if url.startswith(self.base_url):
                        if url not in seen_urls:
                            seen_urls.add(url)
                            pages.append(
                                WebEndpoint(
                                    url=url,
                                    group=extract_url_group(url),
                                    metadata={"source": "sitemap"},
                                )
                            )

        except (requests.RequestException, ET.ParseError) as e:
            logger.debug("Sitemap discovery failed: %s", e)
            # Fallback: add base URL as single page
            pages.append(
                WebEndpoint(
                    url=self.base_url,
                    group=extract_url_group(self.base_url),
                    metadata={"source": "fallback"},
                )
            )

        return pages

    async def _discover_with_headless_async(self) -> List[WebEndpoint]:
        """Discover pages using Playwright headless browser.

        Uses async Playwright API for efficient concurrent page discovery.
        Captures network requests for API endpoint discovery.

        Returns:
            List of WebEndpoint for discovered pages
        """
        if not PLAYWRIGHT_AVAILABLE:
            # This should never be called directly, but return gracefully
            return []

        # Import here to avoid type errors when Playwright is not installed
        from playwright.async_api import async_playwright

        pages: List[WebEndpoint] = []
        seen_urls: Set[str] = set()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Track discovered URLs and API endpoints
                discovered_urls: Set[str] = set()
                api_endpoints: Set[str] = set()

                async def handle_request(request):
                    """Capture network requests for API discovery."""
                    url = request.url
                    resource_type = request.resource_type

                    # Track API endpoints
                    if resource_type in ("fetch", "xhr") or "api" in url.lower():
                        if self.config.normalize_hashes:
                            url = normalize_url(url)
                        api_endpoints.add(url)

                page.on("request", handle_request)

                # Start at base URL
                await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                discovered_urls.add(self.base_url)

                # Find all links on the page
                links = await page.locator("a[href]").all()
                max_pages = min(len(links), self.config.max_pages)

                for link in links[:max_pages]:
                    try:
                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        # Build absolute URL
                        if href.startswith("/"):
                            full_url = urljoin(self.base_url, href)
                        elif href.startswith(("http://", "https://")):
                            full_url = href
                        else:
                            full_url = urljoin(self.base_url, href)

                        # Only include URLs under base_url
                        if not full_url.startswith(self.base_url):
                            continue

                        # Skip common non-page URLs
                        if any(
                            skip in full_url.lower()
                            for skip in (".pdf", ".zip", ".jpg", ".png", ".gif", ".svg")
                        ):
                            continue

                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            discovered_urls.add(full_url)

                            # Navigate to discover more resources
                            await page.goto(full_url, wait_until="networkidle", timeout=15000)

                    except Exception as e:
                        logger.debug("Failed to navigate to link: %s", e)
                        continue

                await browser.close()

                # Convert discovered URLs to WebEndpoint objects
                for url in discovered_urls:
                    pages.append(
                        WebEndpoint(
                            url=url,
                            group=extract_url_group(url),
                            metadata={"source": "headless"},
                        )
                    )

                # Also capture API endpoints discovered during navigation
                # These will be merged with api_endpoints in the main analysis
                if api_endpoints:
                    for api_url in api_endpoints:
                        pages.append(
                            WebEndpoint(
                                url=api_url,
                                method="GET",
                                content_type="application/json",
                                group=extract_url_group(api_url),
                                metadata={"source": "headless-network"},
                            )
                        )

        except Exception as e:
            logger.warning("Headless navigation failed: %s", e)
            # Fallback to sitemap discovery
            return self._discover_from_sitemap()

        return pages

    def _discover_with_headless(self) -> List[WebEndpoint]:
        """Synchronous wrapper for async headless discovery.

        Returns:
            List of WebEndpoint for discovered pages
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available for headless navigation")
            return self._discover_from_sitemap()

        try:
            # Run async discovery in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                pages = loop.run_until_complete(self._discover_with_headless_async())
            finally:
                loop.close()
            return pages
        except Exception as e:
            logger.warning("Headless navigation failed: %s", e)
            # Fallback to sitemap discovery
            return self._discover_from_sitemap()

    def _discover_api_endpoints(self, pages: List[WebEndpoint]) -> List[WebEndpoint]:
        """Discover API endpoints from page content.

        This looks for common API patterns in JavaScript, HTML, etc.

        Args:
            pages: List of discovered pages

        Returns:
            List of WebEndpoint for API endpoints
        """
        api_endpoints: List[WebEndpoint] = []
        seen_urls: Set[str] = set()

        # API path patterns to look for
        api_patterns = [
            re.compile(r'["\'](/api/[^"\']+)["\']'),
            re.compile(r'["\'](/v\d+/[^"\']+)["\']'),
            re.compile(r'fetch\(["\']([^"\']+)["\']'),
            re.compile(r'\.get\(["\']([^"\']+)["\']'),
            re.compile(r'\.post\(["\']([^"\']+)["\']'),
            re.compile(r'axios\.(get|post|put|delete)\(["\']([^"\']+)["\']'),
        ]

        for page in pages[: self.config.max_pages]:
            try:
                response = requests.get(page.url, timeout=30)
                response.raise_for_status()

                content = response.text

                # Extract potential API endpoints
                for pattern in api_patterns:
                    for match in pattern.finditer(content):
                        api_path = match.group(1) if match.lastindex >= 1 else match.group(0)

                        # Build full URL
                        if api_path.startswith("/"):
                            full_url = urljoin(self.base_url, api_path)
                        else:
                            full_url = api_path

                        # Only include URLs under base_url domain
                        if not full_url.startswith(self.base_url):
                            continue

                        # Normalize if configured
                        if self.config.normalize_hashes:
                            full_url = normalize_url(full_url)

                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            api_endpoints.append(
                                WebEndpoint(
                                    url=full_url,
                                    method="GET",
                                    content_type="application/json",
                                    group=extract_url_group(full_url),
                                    metadata={"source": "discovered", "source_page": page.url},
                                )
                            )

            except requests.RequestException as e:
                logger.debug("Failed to fetch page %s: %s", page.url, e)

        return api_endpoints

    def _analyze_js_bundles(self, pages: List[WebEndpoint]) -> List[WebEndpoint]:
        """Analyze JavaScript bundles for framework/component info.

        Args:
            pages: List of discovered pages

        Returns:
            List of WebEndpoint for JS bundles
        """
        js_bundles: List[WebEndpoint] = []
        seen_urls: Set[str] = set()

        # Script patterns
        script_patterns = [
            re.compile(r'<script[^>]+src=["\']([^"\']+)["\']'),
            re.compile(r'"bundle":\s*"([^"]+\.js)"'),
            re.compile(r'"chunk":\s*"([^"]+\.js)"'),
        ]

        for page in pages[: self.config.max_pages]:
            try:
                response = requests.get(page.url, timeout=30)
                response.raise_for_status()

                content = response.text

                # Extract script sources
                for pattern in script_patterns:
                    for match in pattern.finditer(content):
                        script_url = match.group(1)

                        # Build full URL if relative
                        if script_url.startswith("/"):
                            full_url = urljoin(self.base_url, script_url)
                        elif script_url.startswith(("http://", "https://")):
                            full_url = script_url
                        else:
                            full_url = urljoin(page.url, script_url)

                        # Only include JS files
                        if not any(ext in full_url.lower() for ext in (".js", ".mjs")):
                            continue

                        # Normalize if configured
                        normalized = full_url
                        if self.config.normalize_hashes:
                            normalized = normalize_url(full_url)

                        # Use normalized URL for deduplication
                        dedup_key = normalized if self.config.normalize_hashes else full_url
                        if dedup_key not in seen_urls:
                            seen_urls.add(dedup_key)

                            # Get bundle size if possible
                            size_bytes = 0
                            try:
                                head_response = requests.head(full_url, timeout=10)
                                if head_response.status_code == 200:
                                    size_bytes = int(head_response.headers.get("content-length", 0))
                            except requests.RequestException:
                                pass

                            js_bundles.append(
                                WebEndpoint(
                                    url=full_url,
                                    group=extract_url_group(full_url),
                                    normalized_url=normalized,
                                    metadata={
                                        "source": "discovered",
                                        "source_page": page.url,
                                        "size_bytes": size_bytes,
                                    },
                                )
                            )

            except requests.RequestException as e:
                logger.debug("Failed to fetch page %s: %s", page.url, e)

        return js_bundles

    def _generate_tasks(self, result: WebAnalysisResult) -> List[SelectedTask]:
        """Generate tasks from analysis results.

        Args:
            result: Web analysis results

        Returns:
            List of SelectedTask generated from findings
        """
        tasks: List[SelectedTask] = []
        task_id = 0

        # Group endpoints by category for task generation
        by_group: Dict[str, List[WebEndpoint]] = {}
        for endpoint in result.endpoints:
            group = endpoint.group or "default"
            if group not in by_group:
                by_group[group] = []
            by_group[group].append(endpoint)

        # Generate tasks for large JS bundles (>500KB)
        for bundle in result.js_bundles:
            size = bundle.metadata.get("size_bytes", 0)
            if size > 500_000:  # 500KB
                task_id += 1
                size_mb = size / (1024 * 1024)
                tasks.append(
                    SelectedTask(
                        id=f"bundle-optimize-{task_id}",
                        title=f"Optimize large bundle: {bundle.normalized_url} ({size_mb:.1f}MB)",
                        kind="web_analysis",
                        acceptance=[
                            f"Analyze bundle at {bundle.url}",
                            "Implement code splitting or lazy loading",
                            "Remove unused dependencies",
                            "Enable compression/brotli",
                            f"Target: reduce size below 500KB (currently {size_mb:.1f}MB)",
                        ],
                        group="performance",
                    )
                )

        # Generate tasks for unauthenticated API endpoints
        for api in result.api_endpoints:
            if "auth" not in api.group and "admin" not in api.group:
                task_id += 1
                tasks.append(
                    SelectedTask(
                        id=f"api-review-{task_id}",
                        title=f"Review API endpoint security: {api.normalized_url}",
                        kind="web_analysis",
                        acceptance=[
                            f"Test endpoint {api.url} for authentication requirements",
                            "Verify rate limiting is configured",
                            "Check for sensitive data exposure",
                            "Validate input sanitization",
                        ],
                        group="security",
                    )
                )

        # Generate tasks for each section with many endpoints
        for group, endpoints in by_group.items():
            if len(endpoints) > 10:
                task_id += 1
                tasks.append(
                    SelectedTask(
                        id=f"section-audit-{group}-{task_id}",
                        title=f"Audit {group} section: {len(endpoints)} endpoints discovered",
                        kind="web_analysis",
                        acceptance=[
                            f"Review all {len(endpoints)} endpoints in /{group}/",
                            "Identify redundant or deprecated endpoints",
                            "Check for consistent error handling",
                            "Verify documentation coverage",
                            "Consider API versioning strategy",
                        ],
                        group="architecture",
                    )
                )

        # Generate general discovery tasks
        task_id += 1
        tasks.append(
            SelectedTask(
                id=f"web-inventory-{task_id}",
                title=f"Complete web application inventory: {len(result.pages)} pages, {len(result.api_endpoints)} API endpoints",
                kind="web_analysis",
                acceptance=[
                    f"Document all {len(result.pages)} discovered pages",
                    f"Document all {len(result.api_endpoints)} API endpoints",
                    f"Review {len(result.js_bundles)} JavaScript bundles",
                    "Create API documentation",
                    "Map page dependencies and data flow",
                ],
                group="documentation",
            )
        )

        # Generate accessibility tasks for pages
        for page in result.pages[:5]:  # Limit to first 5 pages
            task_id += 1
            path = urlparse(page.url).path or "home"
            tasks.append(
                SelectedTask(
                    id=f"a11y-{path.replace('/', '-')}-{task_id}",
                    title=f"Review accessibility on /{path} page",
                    kind="web_analysis",
                    acceptance=[
                        f"Check page {page.url} with aXe or Lighthouse",
                        "Verify keyboard navigation works",
                        "Check ARIA labels and semantic HTML",
                        "Test with screen reader",
                        "Verify color contrast ratios",
                    ],
                    group="accessibility",
                )
            )

        return tasks

    def select_next_task(
        self, exclude_ids: Optional[Set[str]] = None
    ) -> Optional[SelectedTask]:
        """Return the next available task.

        Args:
            exclude_ids: Task IDs to exclude from selection

        Returns:
            Next uncompleted task, or None if no tasks available
        """
        exclude = exclude_ids or set()
        for task in self._result.tasks:
            if task.id not in exclude:
                return task
        return None

    def peek_next_task(self) -> Optional[SelectedTask]:
        """Look at next task without claiming."""
        return self.select_next_task()

    def claim_next_task(self) -> Optional[SelectedTask]:
        """Claim the next available task.

        For web analysis, this is the same as peek since tasks
        are discovered, not modified.

        Returns:
            Next uncompleted task, or None if no tasks available
        """
        return self.select_next_task()

    def counts(self) -> Tuple[int, int]:
        """Return (completed_count, total_count) for tasks.

        For web analysis, completed is always 0 since we only
        discover tasks, not track their completion.

        Returns:
            Tuple of (0, total_tasks_count)
        """
        return (0, len(self._result.tasks))

    def all_done(self) -> bool:
        """Check if all tasks are completed.

        For web analysis, always returns False since we only
        discover tasks, not track completion.

        Returns:
            False (web analysis doesn't track task completion)
        """
        return False

    def all_blocked(self) -> bool:
        """Check if all remaining tasks are blocked.

        For web analysis, always returns False.

        Returns:
            False
        """
        return False

    def is_task_done(self, task_id: TaskId) -> bool:
        """Check if a specific task is marked done.

        For web analysis, always returns False.

        Args:
            task_id: Task identifier to check

        Returns:
            False (web analysis doesn't track task completion)
        """
        return False

    def force_task_open(self, task_id: TaskId) -> bool:
        """Force a task to be marked as open.

        Not implemented for web analysis tracker.

        Args:
            task_id: Task identifier to reopen

        Returns:
            False (not implemented)
        """
        return False

    def block_task(self, task_id: TaskId, reason: str) -> bool:
        """Mark a task as blocked.

        Not implemented for web analysis tracker.

        Args:
            task_id: Task identifier to block
            reason: Reason for blocking

        Returns:
            False (not implemented)
        """
        return False

    def get_task_by_id(self, task_id: TaskId) -> Optional[SelectedTask]:
        """Return task by ID from discovered tasks."""
        tid = str(task_id)
        for task in self._result.tasks:
            if str(task.id) == tid:
                return task
        return None

    def get_task_status(self, task_id: TaskId) -> str:
        """Return task status by ID: open|done|blocked|missing.

        Web analysis tracker does not track completion state, so discovered tasks
        are always considered "open".
        """
        return "open" if self.get_task_by_id(task_id) is not None else "missing"

    def branch_name(self) -> Optional[str]:
        """Return the branch name for the current task.

        For web analysis, returns None since each task
        would have its own branch.

        Returns:
            None
        """
        return None

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return tasks grouped by parallel group.

        Tasks are grouped by their category (performance, security,
        accessibility, architecture, documentation).

        Returns:
            Dictionary mapping group names to lists of SelectedTask instances
        """
        groups: Dict[str, List[SelectedTask]] = {}

        for task in self._result.tasks:
            group = task.group or "default"
            if group not in groups:
                groups[group] = []
            groups[group].append(task)

        return groups

    def refresh_analysis(self) -> WebAnalysisResult:
        """Force a refresh of the web analysis.

        Invalidates cache and performs a fresh analysis.

        Returns:
            Updated WebAnalysisResult
        """
        # Invalidate cache by setting old timestamp
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r") as f:
                    cache_data = json.load(f)
                cache_data["scanned_at"] = "2000-01-01T00:00:00"
                with open(self.cache_path, "w") as f:
                    json.dump(cache_data, f)
            except (json.JSONDecodeError, ValueError):
                self.cache_path.unlink()

        # Reload analysis
        self._result = self._load_or_analyze()
        return self._result

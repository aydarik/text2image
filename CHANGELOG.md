# Changelog

## [1.3.8] - 2026-08-13

### Changed
- Bump Playwright version.

## [1.3.7] - 2026-07-16

### Fixes
- Create directory for cache only when requested.

## [1.3.6] - 2026-07-05

### Added
- Jitter to /render endpoint to randomize requests.

## [1.3.5] - 2026-04-30

### Added
- Rate-limiting/Blacklisting by IP.
- Save failed requests.

### Fixed
- Restart browser automatically on disconnect.

## [1.3.4] - 2026-03-07

### Fixed
- Clear cache by IP.

## [1.3.3] - 2026-03-06

### Changed
- Cache management UI improvements.

## [1.3.2] - 2026-03-06

### Changed
- Split cached images by IP address.

## [1.3.1] - 2026-03-05

### Fixed
- /render endpoint documentation and validation.

## [1.3.0] - 2026-03-05

### Added
- Cache management.

## [1.2.1] - 2026-01-04

### Changed
- Improved performance by keeping the browser instance persistent across requests.

## [1.2.0] - 2025-12-25

### Changed
- Moved `cache` flag from `CACHE_ENABLED` environment variable to `/render` endpoint as a request parameter (default: `true`).

### Fixed
- Updated README logo to use a direct link to GitHub raw content to fix visibility on the Home Assistant addon page.

## [1.1.0] - 2025-12-23

### Added
- Image caching mechanism based on request hash.
- `/status` endpoint to monitor service health and performance.
- MIT License.

## [1.0.0] - 2025-12-10

### Added
- Initial release with HTML to JPG rendering using Playwright and FastAPI.

# Changelog

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

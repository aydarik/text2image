# Text2Image (GeekMagic HTML renderer)

[![License](https://img.shields.io/github/license/aydarik/text2image)](/LICENSE) [![Release](https://img.shields.io/github/v/release/aydarik/text2image)](https://github.com/aydarik/text2image/releases)

This project provides a simple API to render HTML content into JPG images. It is primarily designed to work with the **[GeekMagic Home Assistant Integration](https://github.com/aydarik/hass-geekmagic)** to verify and generate layouts for GeekMagic.

## Features

-   **HTML to JPG Rendering**: Renders generic HTML/CSS into a 240x240 (default) JPG image.
-   **Playwright Backend**: Uses a headless Chromium browser for accurate rendering.
-   **FastAPI**: Built with FastAPI for high performance.
-   **Caching**: Caches generated images based on request content to speed up subsequent requests.

## Home Assistant Add-on

This project can be installed as a Home Assistant Add-on.

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Faydarik%2Fhass-addons)

### Installation

1.  Add the repository URL to your Home Assistant Add-on Store repositories:
    `https://github.com/aydarik/hass-addons`
2.  Install the "Text2Image" add-on.
3.  Start the add-on.

### Configuration

The add-on runs on port `8000` by default.

> Remember to reconfigure the **Render URL** in the [GeegMagic integration](https://github.com/aydarik/hass-geekmagic) settings to point to your local instance (e.g., `http://0.0.0.0:8000/render`).

## Docker Usage

You can also run this service standalone using Docker.

### Docker Compose

```yaml
services:
  text2image:
    image: ghcr.io/aydarik/text2image
    container_name: text2image
    ports:
      - "8000:8000"
    environment:
      - CACHE_ENABLED=true  # Optional: set to 'false' to disable caching
```

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `CACHE_ENABLED` | Enable or disable image caching. | `true` |

### Manual Run

```bash
docker build -t text2image .
docker run -p 8000:8000 text2image
```

## API Usage

### Endpoint: `/render` [POST]

**Body:**

```json
{
  "html": "<div style='background: red; width: 100%; height: 100%; color: white;'>Hello World</div>",
  "width": 240,
  "height": 240
}
```

**Response:** Returns a `image/jpeg` file.

## License

This project is licensed under the MIT License - see the [LICENSE](/LICENSE) file for details.

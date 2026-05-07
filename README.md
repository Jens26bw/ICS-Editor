# ICS Editor

ICS Editor is a small dark-mode web app for editing iCalendar (`.ics`) files before importing them into a calendar.

The app runs directly in the browser and no longer needs VNC, Xvfb, or a desktop session.

## Docker Image

GitHub Actions builds the image automatically and publishes it to GitHub Container Registry:

```text
ghcr.io/jens26bw/ics-editor:latest
ghcr.io/jens26bw/ics-editor:v3.0.0
```

After the first successful build, check the package settings on GitHub and make the container package public if Unraid should pull it without a GitHub login.

## Unraid Setup

Use the following container settings in Unraid:

| Setting | Value |
| --- | --- |
| Repository | `ghcr.io/jens26bw/ics-editor:latest` |
| Icon URL | `https://raw.githubusercontent.com/Jens26bw/ICS-Editor/main/ICS-Editor_Logo.png` |
| WebUI | `http://[IP]:[PORT:8080]/` |
| Container port | `8080` |
| Host path for ICS files | any folder with your `.ics` files |
| Container path for ICS files | `/data` |
| Host path for config | appdata folder, for example `/mnt/user/appdata/ics-editor` |
| Container path for config | `/config` |

Optional environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `PUID` | empty | User ID for Unraid file permissions |
| `PGID` | empty | Group ID for Unraid file permissions |
| `WEB_PORT` | `8080` | Web app port inside the container |
| `MAX_UPLOAD_MB` | `32` | Maximum upload size for ICS files |

For a typical Unraid setup, `PUID=99` and `PGID=100` are often used.

## Local Build

```bash
docker build -t ics-editor:local .
docker run --rm -p 8080:8080 -v /path/to/ics:/data -v /path/to/config:/config ics-editor:local
```

Then open:

```text
http://localhost:8080/
```

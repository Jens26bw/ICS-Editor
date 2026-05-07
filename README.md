# ICS Editor

ICS Editor is a small browser-accessible desktop container for editing iCalendar (`.ics`) files before importing them into a calendar.

The app runs a Tkinter GUI inside Xvfb and exposes it through noVNC, which makes it suitable for Unraid and other Docker hosts.

## Docker Image

GitHub Actions builds the image automatically and publishes it to GitHub Container Registry:

```text
ghcr.io/jens26bw/ics-editor:latest
ghcr.io/jens26bw/ics-editor:v1.0
```

After the first successful build, check the package settings on GitHub and make the container package public if Unraid should pull it without a GitHub login.

## Unraid Setup

Use the following container settings in Unraid:

| Setting | Value |
| --- | --- |
| Repository | `ghcr.io/jens26bw/ics-editor:latest` |
| WebUI | `http://[IP]:[PORT:8080]/vnc.html?autoconnect=true` |
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
| `ICS_DIR` | `/data` | Start folder for the file picker |
| `NOVNC_PORT` | `8080` | noVNC web port inside the container |
| `VNC_PORT` | `5900` | internal VNC port |
| `RESOLUTION` | `1280x720` | virtual desktop resolution |
| `VNC_PASSWORD` | empty | Optional VNC password |

For a typical Unraid setup, `PUID=99` and `PGID=100` are often used.

## Local Build

```bash
docker build -t ics-editor:local .
docker run --rm -p 8080:8080 -v /path/to/ics:/data -v /path/to/config:/config ics-editor:local
```

Then open:

```text
http://localhost:8080/vnc.html?autoconnect=true
```

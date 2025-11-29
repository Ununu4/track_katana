# Track Katana

Simple PyQt6 desktop tool for slicing WAV files with FFmpeg. Load a track, preview playback, hover/seek with the timeline, then export chops with centisecond precision.

## Features
- WAV loader with duration detection via `ffprobe` (falls back to Python `wave`).
- Playback through `ffplay` with click/drag seeking and hover time readout.
- Prominent timer showing `HH:MM:SS:CC` (centiseconds) for precise chop points.
- Manual begin/end fields (or auto-fill from current playback) and one-click export for each chop.
- Exports use FFmpeg with GPU hints (`-hwaccel auto -hwaccel_output_format cuda`) and PCM output for broad compatibility.

## Requirements
- Python 3.9+ recommended.
- FFmpeg installed and on `PATH` (`ffmpeg`, `ffprobe`, `ffplay` available).
- Windows instructions below; similar steps apply on macOS/Linux with adjusted paths.

## Quickstart (Windows)
```powershell
git clone https://github.com/Ununu4/track_katana
cd track_katana
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

## Usage
1) Click **Select output folder** to choose where chops will be saved.  
2) Click **Load WAV** and pick a source file.  
3) Press **Play**. Hover or click/drag the timeline to inspect or seek. **Stop** halts playback.  
4) When you hear a cut point, click **Set begin to current**; do the same for the end (or type times manually in `HH:MM:SS:CC`).  
5) Click **Export chop**. Each export is listed with its time range and saved to the chosen folder. Repeat as needed.

Notes:
- Times accept `hh:mm:ss:cc` (centiseconds). `hh:mm:ss` or `mm:ss` also work.
- GPU flags are included; if your FFmpeg lacks CUDA support, exports will fall back to CPU automatically.

## Project Structure
- `app.py` — PyQt6 application.
- `requirements.txt` — Python dependencies.
- `.gitignore` — virtualenv, cache, build exclusions.

## Troubleshooting
- **Playback stops early**: ensure `ffplay <file>.wav` works end-to-end in a terminal. If not, update FFmpeg.  
- **Cannot play/seek**: verify `ffplay` is on `PATH`.  
- **Export fails**: confirm `ffmpeg` is on `PATH` and the output folder is writable.  
- **GUI doesn’t launch**: ensure the virtual environment is activated and PyQt6 is installed.

## License
See `LICENSE`.

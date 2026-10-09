"""Assemble the intro and architecture videos from still frames (frames/*.png) and the real clips.

    node stills.js && python3 build.py

Everything is composited by ffmpeg at a constant 30 fps, so nothing is screen-recorded
and nothing drops frames. Paper fades between intro scenes, dissolves between diagram steps.
"""
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = HERE.parent / "clips"
F = HERE / "frames"
PAPER = "0xefe6d2"
FPS = 30
ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), "-an"]
TMP = Path(tempfile.mkdtemp())


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def still(name, dur, fade=0.45):
    out = TMP / f"{name}.mp4"
    vf = f"fps={FPS},format=yuv420p"
    if fade:
        vf += f",fade=t=in:st=0:d={fade}:color={PAPER},fade=t=out:st={dur - fade}:d={fade}:color={PAPER}"
    run(["-loop", "1", "-t", str(dur), "-i", str(F / f"{name}.png"), "-vf", vf, *ENC, str(out)])
    return out


def split(dur=8.5, hot_at=3.5):
    """2x2 of real coop clips under the Fredon, NJ banner. Clips loop to fill the scene."""
    clips = ["coopcam_2026-10-08T15_35_00", "coopcam_2026-10-08T21_51_55",
             "coopcam_fight_2026-10-09T06_22_30", "coopcam_egglaying_2026-10-09T08_47_56"]
    pos = [(125, 140), (975, 140), (125, 611), (975, 611)]
    out = TMP / "split.mp4"
    args = ["-f", "lavfi", "-i", f"color=c={PAPER}:s=1920x1080:r={FPS}:d={dur}"]
    for c in clips:
        args += ["-stream_loop", "-1", "-t", str(dur), "-i", str(CLIPS / f"{c}.mp4")]
    args += ["-loop", "1", "-t", str(dur), "-i", str(F / "split.png")]
    args += ["-loop", "1", "-t", str(dur), "-i", str(F / "split_hot.png")]
    fc = []
    for i in range(4):
        fc.append(f"[{i + 1}:v]fps={FPS},scale=820:461,setsar=1[c{i}]")
    chain = "[0:v]"
    for i, (x, y) in enumerate(pos):
        fc.append(f"{chain}[c{i}]overlay={x}:{y}:shortest=1[o{i}]")
        chain = f"[o{i}]"
    fc.append(f"{chain}[5:v]overlay=0:0[base]")
    fc.append(f"[6:v]format=rgba,fade=t=in:st={hot_at}:d=0.5:alpha=1[hot]")
    fc.append(f"[base][hot]overlay=0:0,format=yuv420p,"
              f"fade=t=in:st=0:d=0.45:color={PAPER},fade=t=out:st={dur - 0.45}:d=0.45:color={PAPER}[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def fight_zoom(dur=5.5):
    """Full screen: the 6:22 AM clip cropped around the roosters, with the ring and caption bar."""
    out = TMP / "fightzoom.mp4"
    fc = (f"[0:v]fps={FPS},crop=iw*0.5:ih*0.5:iw*0.22:ih*0.18,scale=1920:1080,setsar=1[z];"
          f"[z][1:v]overlay=0:0,format=yuv420p,"
          f"fade=t=in:st=0:d=0.45:color={PAPER},fade=t=out:st={dur - 0.45}:d=0.45:color={PAPER}[v]")
    run(["-stream_loop", "-1", "-t", str(dur), "-i", str(CLIPS / "coopcam_fight_2026-10-09T06_22_30.mp4"),
         "-loop", "1", "-t", str(dur), "-i", str(F / "fightzoom.png"),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def zoom_step(dur):
    """Step 3: the diagram still with the real zoomed fight clip playing in its slot."""
    x, y, w, h = json.loads((F / "hole.json").read_text())
    out = TMP / "a3.mp4"
    fc = (f"[1:v]crop=iw/2:ih/2:iw/4:ih/4,scale={w}:{h},setsar=1,fps={FPS}[z];"
          f"[0:v]fps={FPS}[bg];[bg][z]overlay={x}:{y}:shortest=1,format=yuv420p[v]")
    run(["-loop", "1", "-t", str(dur), "-i", str(F / "a3.png"),
         "-stream_loop", "-1", "-t", str(dur), "-i", str(CLIPS / "coopcam_fight_2026-10-09T06_22_30.mp4"),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def concat(parts, out):
    lst = TMP / f"{out.stem}.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


def dissolve(parts, durs, out, d=0.4):
    """Chain xfade dissolves between same-size segments."""
    args = []
    for p in parts:
        args += ["-i", str(p)]
    fc, prev, offset = [], "[0:v]", 0.0
    for i in range(1, len(parts)):
        offset += durs[i - 1] - d
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={d}:offset={offset:.3f}[x{i}]")
        prev = f"[x{i}]"
        durs[i] = durs[i]  # cumulative handled via offset
    fc.append(f"{prev}format=yuv420p[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", *ENC, str(out)])


if __name__ == "__main__":
    intro = [still("i1", 3.2), still("i2", 2.8), still("i3", 5.2), split(8.5), fight_zoom(5.5),
             still("i4", 3.4), still("i5", 4.0), still("i6", 6.2)]
    concat(intro, HERE / "intro.mp4")

    steps = [("a1", 5.5), ("a2", 6.0), ("a3", 9.0), ("a4", 6.5), ("a5", 7.5), ("a6", 6.0), ("a7", 5.5), ("a8", 6.5)]
    parts, durs = [], []
    for name, dur in steps:
        parts.append(zoom_step(dur) if name == "a3" else still(name, dur, fade=0))
        durs.append(dur)
    parts.append(still("end", 4.5, fade=0))
    durs.append(4.5)
    dissolve(parts, durs, HERE / "architecture.mp4")
    for f in ("intro.mp4", "architecture.mp4"):
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(HERE / f)],
                           capture_output=True, text=True).stdout.strip()
        print(f, d)

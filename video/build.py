"""Assemble the intro and architecture videos from rendered stills (frames/*.png) and the real clips.

    node stills.js && python3 build.py

Everything is composited by ffmpeg at a constant 30 fps. Motion is continuous: backgrounds drift,
cards push in slowly (scaled per frame, so no jitter), and scenes slide into each other with xfade.
"""
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = HERE.parent / "clips"
F = HERE / "frames"
FPS = 30
ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-r", str(FPS), "-an"]
TMP = Path(tempfile.mkdtemp())
FIGHT = CLIPS / "coopcam_fight_2026-10-09T06_22_30.mp4"


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def bg_pan(i, dur, direction=1):
    """Filter for a 2400-wide background that drifts 480px across the scene."""
    x = f"480*t/{dur}" if direction > 0 else f"480-480*t/{dur}"
    return f"[{i}:v]fps={FPS},crop=1920:1080:'{x}':0,setsar=1"


def push(i, dur, amount=0.035):
    """Filter for a transparent foreground that pushes in slowly. Scaled per frame for smooth motion."""
    return (f"[{i}:v]fps={FPS},format=rgba,scale=w='trunc(1920*(1+{amount}*t/{dur})/2)*2':h=-2:eval=frame,"
            f"crop=1920:1080:'(iw-1920)/2':'(ih-1080)/2'")


def card(name, bg, dur, direction=1):
    """The card holds still; only the background drifts behind it."""
    out = TMP / f"{name}.mp4"
    fc = f"{bg_pan(0, dur, direction)}[b];[b][1:v]overlay=0:0,format=yuv420p,settb=AVTB[v]"
    run(["-loop", "1", "-t", str(dur), "-i", str(F / f"bg-{bg}.png"),
         "-loop", "1", "-t", str(dur), "-i", str(F / f"{name}.png"),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def split(dur=8.5, hot_at=3.5):
    """2x2 of real coop clips over drifting cow spots; then the fight tile is called out."""
    clips = ["coopcam_2026-10-08T15_35_00", "coopcam_2026-10-08T21_51_55",
             "coopcam_fight_2026-10-09T06_22_30", "coopcam_egglaying_2026-10-09T08_47_56"]
    pos = [(125, 140), (975, 140), (125, 611), (975, 611)]
    out = TMP / "split.mp4"
    args = ["-loop", "1", "-t", str(dur), "-i", str(F / "bg-cow.png")]
    for c in clips:
        args += ["-stream_loop", "-1", "-t", str(dur), "-i", str(CLIPS / f"{c}.mp4")]
    args += ["-loop", "1", "-t", str(dur), "-i", str(F / "split.png"),
             "-loop", "1", "-t", str(dur), "-i", str(F / "split_hot.png")]
    fc = [f"{bg_pan(0, dur, -1)}[b0]"]
    for i in range(4):
        fc.append(f"[{i + 1}:v]fps={FPS},scale=820:461,setsar=1[c{i}]")
    chain = "[b0]"
    for i, (x, y) in enumerate(pos):
        fc.append(f"{chain}[c{i}]overlay={x}:{y}:shortest=1[o{i}]")
        chain = f"[o{i}]"
    fc.append(f"{chain}[5:v]overlay=0:0[base]")
    fc.append(f"[6:v]format=rgba,fade=t=in:st={hot_at}:d=0.6:alpha=1[hot]")
    fc.append("[base][hot]overlay=0:0,format=yuv420p,settb=AVTB[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def fight_zoom(dur=5.0):
    """Full screen: the real 6:22 AM clip, cropped around the roosters and pushing in slowly."""
    out = TMP / "fightzoom.mp4"
    fc = (f"[0:v]fps={FPS},crop=iw*0.5:ih*0.5:iw*0.22:ih*0.18,"
          f"scale=w='trunc(1920*(1+0.06*t/{dur})/2)*2':h=-2:eval=frame,crop=1920:1080:'(iw-1920)/2':'(ih-1080)/2',setsar=1[z];"
          f"[z][1:v]overlay=0:0,format=yuv420p,settb=AVTB[v]")
    run(["-stream_loop", "-1", "-t", str(dur), "-i", str(FIGHT),
         "-loop", "1", "-t", str(dur), "-i", str(F / "fightzoom.png"),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def gallery(dur=7.0, bg="fence"):
    """'16 real clips recorded': a moving strip of the other 15 real clips plays above the line."""
    out = TMP / "i5.mp4"
    x, y, w, h = json.loads((F / "hole_gallery.json").read_text())
    rest = sorted(p for p in CLIPS.glob("*.mp4") if p != FIGHT)
    groups = [[p for p in rest if k(p.name)] for k in (lambda n: "T15" in n, lambda n: "T21" in n,
                                                         lambda n: "egg" in n, lambda n: "fight" in n)]
    clips = [g[i] for i in range(max(map(len, groups))) for g in groups if i < len(g)]  # mix day, night, nest, fight
    tw, gap = round(h * 16 / 9), 14
    args = ["-loop", "1", "-t", str(dur), "-i", str(F / f"bg-{bg}.png"),
            "-loop", "1", "-t", str(dur), "-i", str(F / "i5.png")]
    for c in clips:
        args += ["-i", str(c)]
    fc = [f"{bg_pan(0, dur)}[b]", "[b][1:v]overlay=0:0[base]"]
    for i in range(len(clips)):
        fc.append(f"[{i + 2}:v]scale={tw}:{h},setsar=1,setpts=1.45*PTS,framerate=fps={FPS},"
                  f"tpad=stop_mode=clone:stop_duration={dur},trim=duration={dur},pad={tw + gap}:{h}:0:0:color=0xfbf6ea[t{i}]")
    step = 8  # px per frame, exact: 240 px/s
    fc.append("".join(f"[t{i}]" for i in range(len(clips))) + f"hstack=inputs={len(clips)},"
              f"crop={w}:{h}:'n*{step}':0[g]")
    fc.append(f"[base][g]overlay={x}:{y}:shortest=1,format=yuv420p,settb=AVTB[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def ask_scene(dur=7.5, answer_at=1.6):
    """Plain-English search: the question sits in the box, then the answer and the real 9:04 AM clip appear."""
    out = TMP / "ask.mp4"
    x, y, w, h = json.loads((F / "hole_ask.json").read_text())
    clip = CLIPS / "coopcam_egglaying_2026-10-09T09_04_15.mp4"
    fc = (f"{bg_pan(0, dur)}[b];[b][1:v]overlay=0:0[q];"
          f"[2:v]format=rgba,fade=t=in:st={answer_at}:d=0.5:alpha=1[a];[q][a]overlay=0:0[qa];"
          f"[3:v]fps={FPS},scale={w}:{h},setsar=1,format=rgba,fade=t=in:st={answer_at}:d=0.5:alpha=1[c];"
          f"[qa][c]overlay={x}:{y}:shortest=1,format=yuv420p,settb=AVTB[v]")
    run(["-loop", "1", "-t", str(dur), "-i", str(F / "bg-cow.png"),
         "-loop", "1", "-t", str(dur), "-i", str(F / "ask.png"),
         "-loop", "1", "-t", str(dur), "-i", str(F / "ask_ans.png"),
         "-stream_loop", "-1", "-t", str(dur), "-i", str(clip),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def arch_step(name, bg, dur):
    """A diagram step over a slowly drifting background; step 3 plays the real zoomed fight in its slot."""
    out = TMP / f"{name}.mp4"
    args = ["-loop", "1", "-t", str(dur), "-i", str(F / f"bg-{bg}.png"),
            "-loop", "1", "-t", str(dur), "-i", str(F / f"{name}.png")]
    fc = f"{bg_pan(0, dur)}[b];[b][1:v]overlay=0:0"
    if name == "a3":
        x, y, w, h = json.loads((F / "hole.json").read_text())
        args += ["-stream_loop", "-1", "-t", str(dur), "-i", str(FIGHT)]
        fc += f"[s];[2:v]fps={FPS},crop=iw/2:ih/2:iw/4:ih/4,scale={w}:{h},setsar=1[z];[s][z]overlay={x}:{y}:shortest=1"
    fc += ",format=yuv420p,settb=AVTB[v]"
    run([*args, "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *ENC, str(out)])
    return out


def chain(segments, out):
    """segments: [(path, duration, transition_into_next)]. Crossfades every boundary with xfade."""
    args, fc, prev, offset = [], [], "[0:v]", 0.0
    for p, _, _ in segments:
        args += ["-i", str(p)]
    for i in range(1, len(segments)):
        _, dur_prev, (kind, d) = segments[i - 1]
        offset += dur_prev - d
        fc.append(f"{prev}[{i}:v]xfade=transition={kind}:duration={d}:offset={offset:.3f}[x{i}]")
        prev = f"[x{i}]"
        # the next offset is measured from the start of the merged stream
        segments[i] = (segments[i][0], segments[i][1], segments[i][2])
    fc.append(f"{prev}format=yuv420p[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", *ENC, str(out)])


if __name__ == "__main__":
    SL, FD = ("slideleft", 0.7), ("fade", 0.6)
    intro = [
        (card("i1", "hay", 3.6), 3.6, SL),
        (card("i3", "fence", 5.4, -1), 5.4, SL),
        (card("iw", "cow", 7.0), 7.0, SL),
        (split(8.5), 8.5, ("zoomin", 0.8)),
        (fight_zoom(6.0), 6.0, SL),
        (card("i4", "hay-chickens", 4.4, -1), 4.4, SL),
        (gallery(7.0), 7.0, SL),
        (card("phone", "fence", 7.2, -1), 7.2, SL),
        (ask_scene(9.0), 9.0, SL),
        (card("i6", "hay", 7.6), 7.6, FD),
    ]
    chain(intro, HERE / "intro.mp4")

    steps = [("a1", 6.2), ("a2", 6.8), ("a3", 10.5), ("a4", 10.8), ("a5", 8.6), ("a6", 6.8), ("a7", 6.2), ("a8", 7.6)]
    arch = [(arch_step(n, "fence", d), d, FD) for n, d in steps]
    arch.append((card("end", "cow", 5.0), 5.0, FD))
    chain(arch, HERE / "architecture.mp4")
    for f in ("intro.mp4", "architecture.mp4"):
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(HERE / f)],
                           capture_output=True, text=True).stdout.strip()
        print(f, d)

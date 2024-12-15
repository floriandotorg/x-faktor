import json
import os

from collections import namedtuple

from ffmpeg import FFmpeg


Resolution = namedtuple("Resolution", ("width", "height"))
Resolution.__str__ = lambda self: f"{self.width}x{self.height}"


video_resolution = Resolution(1920, 1080)
video_resolution = Resolution(1280, 720)
framerate = 25
background_volume = 0.5


def _length_of_media(media_file: str) -> float:
    ffprobe = FFmpeg(executable="ffprobe").input(
        media_file,
        v="error",
        show_entries="format=duration",
        of="csv=p=0",
    )

    #print(" ".join(ffprobe.arguments))
    duration = ffprobe.execute().decode("ASCII")
    return float(duration.rstrip())


def render_video(
    episode_file: str, output_file: str = None, temp_directory: str = None
) -> None:
    with open(episode_file, "r") as f:
        episode_data = json.load(f)

    if output_file is None:
        base_filename, _ = os.path.splitext(episode_file)
        output_file = base_filename + ".mp4"

    if temp_directory is None:
        base_filename, _ = os.path.splitext(os.path.basename(episode_file))
        temp_directory = f"generated-{base_filename}"

    scene_files = []

    os.makedirs(temp_directory, exist_ok=True)

    upscale_resolution = Resolution(*(x * 4 for x in video_resolution))

    fade_out = False
    for scene in episode_data["scenes"]:
        scene["fade_in"] = fade_out
        fade_out = scene.setdefault("fade_out", False)

    for scene_number, scene in enumerate(episode_data["scenes"]):
        print(f"Generate Scene #{scene_number}")

        scene_source_file = scene["content"]["filename"]
        scene_audio_file = scene["content"]["audio"]["filename"]
        scene_file = f"scene{scene_number}.mp4"
        scene_file_path = os.path.join(temp_directory, scene_file)
        audio_duration = _length_of_media(scene_audio_file)

        fade_length = min(0.5, audio_duration / 3)

        video_filter = []

        cmd = FFmpeg().option("y")

        kwargs = {}

        if scene["type"] == "image":
            # scene_duration = int(scene["content"]["duration"])

            frame_count = int(audio_duration * framerate) + 1
            zoom_level = 1.2
            zoom_per_frame = min(zoom_level / frame_count, 0.0001)

            video_filter += [
                f"scale={upscale_resolution}",
                f"zoompan=z='zoom+{zoom_per_frame}':d={frame_count}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={video_resolution}"
            ]

            # ./ffmpeg -loop 1 -i .\episode1\image1.png -c:v libx264 -t 10 -pix_fmt yuv420p output.mp4
            cmd = cmd.option("loop", 1)

            kwargs["t"] = audio_duration
        elif scene["type"] == "video":
            video_duration = _length_of_media(scene_source_file)
            video_filter += [
                f"setpts=({audio_duration}/{video_duration})*PTS",
                f"scale={video_resolution}"
            ]
        else:
            raise Exception(f"Unknown type {scene['type']}")

        # Previous scene faded out
        if scene["fade_in"]:
            video_filter += [f"fade=t=in:st=0:d={fade_length}"]

        # Current scene fades out
        if scene["fade_out"]:
            video_filter += [f"fade=t=out:st={audio_duration - fade_length}:d={fade_length}"]

        cmd = (
            cmd
            .input(scene_source_file)
            .input(scene_audio_file)
            .output(
                scene_file_path,
                {
                    "c:v": "libx264",
                    "c:a": "aac",
                    "b:a": "192k",
                    **kwargs
                },
                ac=2,
                ar=44100,
                # t=scene_duration,
                pix_fmt="yuv420p",
                vf=",".join(video_filter),
                r=framerate,
                map=["0:v", "1:a"],
                shortest=None,
            )
        )

        print(" ".join(cmd.arguments))
        cmd.execute()

        scene_files += [scene_file]

    episode_silent_file = os.path.join(temp_directory, "episode_silent.mp4")
    # Combine scenes
    # ffmpeg.exe -i scene0.mp4 -i scene2.mp4 -filter_complex "[0:v]scale=1024:576,setdar=16/9[v0];[1:v]scale=1024:576,setdar=16/9[v1];[v0][0:a][v1][1:a] concat=n=2:v=1:a=1 [v] [a]" -map "[v]" -map "[a]" output.mp4

    concat_cmd = FFmpeg().option("y")
    filter_complex = ""
    merge_filter = ""
    for i, scene_file in enumerate(scene_files):
        scene_file = os.path.join(temp_directory, scene_file)
        concat_cmd = concat_cmd.input(scene_file)

        filter_complex += f"[{i}:v]scale={video_resolution},setdar=16/9[v{i}];"
        merge_filter += f"[v{i}][{i}:a]"

    filter_complex += merge_filter
    filter_complex += f" concat=n={len(scene_files)}:v=1:a=1 [v][a]"

    cmd = concat_cmd.output(
        episode_silent_file, filter_complex=filter_complex, map=["[v]", "[a]"]
    )

    print(" ".join(cmd.arguments))
    cmd.execute()

    text_filters = []
    for overlay_index, overlay in enumerate(episode_data["textOverlays"]):
        text = overlay["text"]
        start = overlay["appearance"]["start"]
        end = overlay["appearance"]["end"]

        overlay_file = os.path.join(temp_directory, f"overlay{overlay_index}.txt")
        with open(overlay_file, "w") as f:
            f.write(text)

        overlay_file = overlay_file.replace("\\", "\\\\")

        text_filters += [
            f"drawtext=textfile='{overlay_file}':x=(w-text_w)/2:y=h-80-text_h:fontcolor=white:fontsize=48:font=Times New Roman:alpha='if(lte(t,{start+1}), (t-{start})/{1}, if(gte(t,{end-1}), ({end}-t)/{1}, 1))'"
        ]

    total_duration = _length_of_media(episode_silent_file)
    fade_length = 1

    kwargs = {}
    if text_filters:
        kwargs["vf"] = f"[in]{','.join(text_filters)}[out]"

    # ffmpeg -i output.mp4 -i music.mp3 -stream_loop -1 -map 0:v -map 1:a -c:v copy -shortest final_output.mp4
    cmd = (
        FFmpeg()
        .option("y")
        .input(episode_silent_file)
        .input(episode_data["backgroundMusic"]["filename"], stream_loop=-1)
        .output(
            output_file,
            {"c:v": "libx264", "c:a": "aac", **kwargs},
            filter_complex=f"[1:a]volume={background_volume},afade=t=out:st={total_duration - fade_length}:d={fade_length}[bga];[0:a][bga]amix=inputs=2:duration=longest",
            shortest=None,
        )
    )
    print(" ".join(cmd.arguments))
    cmd.execute()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render a video from an episode file.")

    parser.add_argument("episode_file", type=str, help="Path to the episode file.")
    parser.add_argument(
        "output_file",
        type=str,
        nargs="?",
        default=None,
        help="Path to the output file (optional).",
    )
    parser.add_argument(
        "temp_directory",
        type=str,
        nargs="?",
        default=None,
        help="Path to the temporary directory (optional).",
    )

    args = parser.parse_args()
    render_video(args.episode_file, args.output_file, args.temp_directory)

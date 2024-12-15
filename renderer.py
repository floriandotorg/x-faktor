from ffmpeg import FFmpeg
import json
import os



video_resolution = "1920:1080"
video_resolution = "1280:720"
framerate = 25
background_volume = 0.5


def render_video(episode_file: str, output_file: str = None, temp_directory: str = None) -> None:
    with open(episode_file, "r") as f:
        episode_data = json.load(f)

    if output_file is None:
        base_filename, _ = os.path.splitext(episode_file)
        output_file = base_filename + '.mp4'

    if temp_directory is None:
        base_filename, _ = os.path.splitext(os.path.basename(episode_file))
        temp_directory = f"generated-{base_filename}"

    scene_files = []

    os.makedirs(temp_directory, exist_ok=True)

    for scene_number, scene in enumerate(episode_data["scenes"]):
        print(f"Generate Scene #{scene_number}")

        scene_source_file = scene["content"]["filename"]
        scene_file = f"scene{scene_number}.mp4"
        scene_file_path = os.path.join(temp_directory, scene_file)
        if scene["type"] == "image":
            #scene_duration = int(scene["content"]["duration"])

            #./ffmpeg -loop 1 -i .\episode1\image1.png -c:v libx264 -t 10 -pix_fmt yuv420p output.mp4
            cmd = (
                FFmpeg()
                .option("y")
                .option("loop", "1")
                .input(scene_source_file)
                .input(scene["content"]["audio"]["filename"])
                .output(
                    scene_file_path,
                    {
                        "c:v": "libx264",
                        "c:a": "aac",
                        "b:a": "192k",
                    },
                    ac=2,
                    ar=44100,
                    #t=scene_duration,
                    tune="stillimage",
                    pix_fmt="yuv420p",
                    vf="scale=" + video_resolution,
                    r=framerate,
                    map=["0:v", "1:a"],
                    shortest=None,
                )
            )
        elif scene["type"] == "video":
            cmd = (
                FFmpeg()
                .option("y")
                .input(scene_source_file, stream_loop=-1)
                .input(scene["content"]["audio"]["filename"])
                .output(
                    scene_file_path,
                    {
                        "c:v": "libx264",
                        "c:a": "aac",
                        "b:a": "192k",
                    },
                    ac=2,
                    ar=44100,
                    #t=scene_duration,
                    pix_fmt="yuv420p",
                    vf="scale=" + video_resolution,
                    r=framerate,
                    map=["0:v", "1:a"],
                    shortest=None,
                )
            )
        else:
            raise Exception(f"Unknown type {scene['type']}")

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
        episode_silent_file,
        filter_complex=filter_complex,
        map=["[v]", "[a]"]
    )

    print(" ".join(cmd.arguments))
    cmd.execute()

    text_filters = []
    for overlay in episode_data["textOverlays"]:
        text = overlay["text"]
        start = overlay["appearance"]["start"]
        end = overlay["appearance"]["end"]

        text_filters += [
            f"drawtext=text='{text}':x=(w-text_w)/2:y=40:fontcolor=white:fontsize=48:enable='between(t,{start},{end})':font=Times New Roman"
        ]

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
            {
                "c:v": "libx264",
                "c:a": "aac",
                **kwargs
            },
            filter_complex=f"[1:a]volume={background_volume}[bga];[0:a][bga]amix=inputs=2:duration=longest",
            shortest=None
        )
    )
    print(" ".join(cmd.arguments))
    cmd.execute()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Render a video from an episode file.")

    parser.add_argument('episode_file', type=str, help="Path to the episode file.")
    parser.add_argument('output_file', type=str, nargs='?', default=None, help="Path to the output file (optional).")
    parser.add_argument('temp_directory', type=str, nargs='?', default=None, help="Path to the temporary directory (optional).")

    args = parser.parse_args()
    render_video(args.episode_file, args.output_file, args.temp_directory)

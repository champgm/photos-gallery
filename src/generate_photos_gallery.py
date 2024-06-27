import json
from pathlib import Path
import PIL
import os
import numpy as np
import datetime as dt
import logging
import coloredlogs
import click
from typing import Tuple, Dict, Optional
from PIL import Image, ImageFile, ExifTags
from pydantic import ValidationError

from models.photo_metadata_gapis import GapisMetadata


default_date = dt.datetime.fromisoformat("2020-01-30T22:35:20+00:00")


def get_script_directory() -> str:
    script_path = __file__
    full_path = os.path.realpath(script_path)
    script_dir = os.path.dirname(full_path)
    return script_dir


def open_metadata_file(csv_file: str) -> Dict[str, Tuple[str, dt.datetime, str]]:
    def chomp(string: str, start_char: str, end_char: str) -> Tuple[str, str]:
        chomp: str = ""
        l_index = string.find(start_char)
        if l_index >= 0:
            r_index = string.find(end_char, l_index + 1)
            if r_index < 0:
                return ("", string)
            chomp = string[l_index : r_index + 1]
            return (chomp, string[r_index + 1 :])
        else:
            return ("", string)

    processed: Dict[str, Tuple[str, dt.datetime, str]] = {}
    if not os.path.exists(csv_file):
        return processed
    with open(csv_file, "r") as f:
        line = f.readline()
        while line:
            filename, line = chomp(line, '"', '"')
            split = line[1:].split(",")
            if len(split) == 3:
                ar = split[0]
                c_date = dt.datetime.fromisoformat(split[1].strip())
                tokens = split[2].strip()
            else:
                ar = split[0]
                c_date = dt.datetime.fromisoformat(split[1].strip())
                tokens = ""
            if '"' in filename:
                filename = filename.replace('"', "")
            processed[filename] = (ar, c_date, tokens)
            line = f.readline()
    return processed


# def get_aspect_ratio(im: Image) -> float:
#     aspect_ratio = im.size[0] / im.size[1]
#     return aspect_ratio


def get_date_from_meta(photo_metadata: GapisMetadata) -> Optional[dt.datetime]:
    # image_path = Path(im.filename)
    # json_path = image_path.with_suffix(image_path.suffix + ".meta.json")

    # if not json_path.exists():
    #     return default_date

    # with open(json_path, encoding="utf-8") as f:
    #     metadata = json.load(f)
    #     try:
    #         photo_metadata = GapisMetadata(**metadata)
    #     except ValidationError as e:
    #         logging.error(f"Validation error while parsing photo metadata: {e}")
    #         return default_date

    photo_date_str = photo_metadata.mediaMetadata.creationTime
    # This Google metadata is weird. Replace non-breaking space and other potential
    # non-standard spaces with a standard space
    photo_date_str = (
        photo_date_str.replace("\u202F", " ").replace("\xa0", " ").replace(" ", " ")
    )
    try:
        # The 'Z' denotes UTC, which `fromisoformat` does not parse directly.
        # You need to replace 'Z' with '+00:00' for UTC designation.
        photo_date_str = photo_date_str.replace("Z", "+00:00")
        # Parse the ISO 8601 formatted string
        date = dt.datetime.fromisoformat(photo_date_str)
        return date
    except ValueError as ex:
        logging.error(f"Failed to parse date: {ex}")
        logging.error(f"Original photo_date_str: {photo_date_str}")
        raise ex


def rotate_image(im: Image) -> Image:
    try:
        orientation = -1
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == "Orientation":
                break
        exif = dict(im._getexif().items())
        if orientation in exif and exif[orientation] == 3:
            im = im.rotate(180, expand=True)
        elif orientation in exif and exif[orientation] == 6:
            im = im.rotate(270, expand=True)
        elif orientation in exif and exif[orientation] == 8:
            im = im.rotate(90, expand=True)
    except Exception as ex:
        logging.debug(ex)
    return im


def regenerate_csv(source_directory: str, csv_file: str) -> None:
    images = os.listdir(source_directory)
    metadata = {}

    with open(csv_file, "w") as csv_out:
        for filename in images:
            if not filename.endswith(".json"):
                # logging.info("Skipping JSON file: {}".format(f))
                continue
            logging.info("regenerating {}".format(filename))
            json_path = f"{source_directory}/{filename}"
            try:
                gapi_metadata: GapisMetadata = None
                with open(json_path) as raw_metadata:
                    raw_metadata = json.load(raw_metadata)
                    gapi_metadata = GapisMetadata(**raw_metadata)
                # im = Image.open(source_directory + "/" + filename)

                created_date = get_date_from_meta(gapi_metadata)
                # im = rotate_image(im)
                aspect_ratio = float(gapi_metadata.mediaMetadata.width) / float(
                    gapi_metadata.mediaMetadata.height
                )

                metadata[filename] = (aspect_ratio, created_date)
                # im.close()
            except ValidationError as ve:
                logging.error(f"Validation error while processing {filename}:")
                for error in ve.errors():
                    logging.error(
                        f"  {error['loc'][0]}: {error['msg']} (type={error['type']})"
                    )
                raise ve
            except Exception as ex:
                logging.exception("{}: {}".format(filename, ex), exc_info=False)
                raise ex

        metadata = {
            k: v
            for k, v in sorted(
                metadata.items(), key=lambda item: item[1][1], reverse=True
            )
        }

        for k, v in metadata.items():
            csv_out.write('"{}",{:.3f},{}\n'.format(k, v[0], v[1]))
        csv_out.close()


@click.command()
def main():
    script_directory = get_script_directory()
    parent_directory = os.path.dirname(script_directory)
    thumbnails_directory = os.path.join(parent_directory, "thumbnail")
    video_thumbnail_directory = os.path.join(parent_directory, "video_thumbnail")
    # web_directory = os.path.join(parent_directory, "web")
    image_metadata_file = os.path.join(parent_directory, "photos.csv")
    video_metadata_file = os.path.join(parent_directory, "videos.csv")
    image_source_directory = os.path.join(parent_directory, "images")
    video_source_directory = os.path.join(parent_directory, "videos")

    print("Regenerating image metadata...")
    regenerate_csv(image_source_directory, image_metadata_file)
    # print("Processing images...")
    # process_images(image_source_directory, thumbnails_directory, image_metadata_file)
    print("Regenerating video metadata...")
    regenerate_csv(video_source_directory, video_metadata_file)


if __name__ == "__main__":
    coloredlogs.install(level="INFO")
    main()

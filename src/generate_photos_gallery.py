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

from photo_metadata_takeout import TakeoutMetadata
from photo_metadata_gapis import GapisMetadata


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


def get_aspect_ratio(im: Image) -> float:
    aspect_ratio = im.size[0] / im.size[1]
    return aspect_ratio


def get_date_from_meta(im: Image) -> Optional[dt.datetime]:
    image_path = Path(im.filename)
    json_path = image_path.with_suffix(image_path.suffix + ".meta.json")

    if not json_path.exists():
        return default_date

    with open(json_path, encoding="utf-8") as f:
        metadata = json.load(f)
        try:
            photo_metadata = GapisMetadata(**metadata)
        except ValidationError as e:
            logging.error(f"Validation error while parsing photo metadata: {e}")
            return default_date

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


def regenerate_metadata_csv(source_directory: str, csv_file: str) -> None:
    images = os.listdir(source_directory)
    metadata = {}

    with open(csv_file, "w") as csv_out:
        for filename in images:
            if filename.endswith(".json"):
                # logging.info("Skipping JSON file: {}".format(f))
                continue
            logging.info("regenerating {}".format(filename))
            try:
                im = Image.open(source_directory + "/" + filename)

                created_date = get_date_from_meta(im)
                im = rotate_image(im)
                aspect_ratio = get_aspect_ratio(im)

                metadata[filename] = (aspect_ratio, created_date)
                im.close()
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


def process(source_directory: str, thumbnail_directory: str, csv_file: str) -> None:
    MAX_SIZE = (640, 640)
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    thumbnail_directory = os.path.abspath(thumbnail_directory)

    # don't need thumbnails for JSON files
    source_files = [f for f in os.listdir(source_directory) if not f.endswith('.json')]
    unprocessed_files = source_files

    if os.path.exists("generate.log"):
        os.remove("generate.log")
    log_file = open("generate.log", "w")

    thumbnail_files = os.listdir(thumbnail_directory)
    unprocessed_files = np.setdiff1d(source_files, thumbnail_files)
    metadata = open_metadata_file(csv_file)

    csv_out = open(csv_file, "w")

    logging.info("Number of files that need thumbnails: {}".format(len(unprocessed_files)))

    for f in unprocessed_files:
        if f.endswith(".json"):
            # logging.info("Skipping JSON file: {}".format(f))
            continue
        try:
            im = Image.open(source_directory + "/" + f)

            created_date = get_date_from_meta(im)
            im = rotate_image(im)
            aspect_ratio = get_aspect_ratio(im)

            im.thumbnail(MAX_SIZE, PIL.Image.LANCZOS)
            im.save(thumbnail_directory + "/" + f, format=im.format)

            metadata[f] = ("{:.3f}".format(aspect_ratio), created_date)

            logging.info("processed: {}".format(f))
            im.close()
        except Exception as ex:
            logging.exception("{}: {}".format(ex, f), exc_info=False)
            log_file.write(f + "\n")
            log_file.flush()
            raise ex

    # order the files by date
    metadata = {
        k: v
        for k, v in sorted(metadata.items(), key=lambda item: item[1][1], reverse=True)
    }

    for k, v in metadata.items():
        csv_out.write('"{}",{},{}\n'.format(k, v[0], v[1]))
    csv_out.close()


@click.command()
def main():
    script_directory = get_script_directory()
    parent_directory = os.path.dirname(script_directory)
    thumbnails_directory = os.path.join(parent_directory, "thumbnail")
    # web_directory = os.path.join(parent_directory, "web")
    metadata_file = os.path.join(parent_directory, "photos.csv")
    image_source_directory = os.path.join(parent_directory, "images")

    print("Regenerating metadata...")
    regenerate_metadata_csv(image_source_directory, metadata_file)
    print("Processing images...")
    process(image_source_directory, thumbnails_directory, metadata_file)


if __name__ == "__main__":
    coloredlogs.install(level="INFO")
    main()

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

from models.csv_entry import CsvEntry
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


def get_date_from_meta(photo_metadata: GapisMetadata) -> Optional[dt.datetime]:
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


def regenerate_csv(
    source_directory: str, thumbnail_directory: str, csv_file: str, is_for_videos: bool
) -> None:
    images = os.listdir(source_directory)
    metadata: list[CsvEntry] = []

    with open(csv_file, "w") as csv_out:
        for filename in images:
            if not filename.endswith(".meta.json"):
                # logging.info("Skipping JSON file: {}".format(f))
                continue
            meta_file_name = filename
            file_name = filename.replace(".meta.json", "")
            logging.info("regenerating {}".format(file_name))
            json_path = f"{source_directory}/{meta_file_name}"
            try:
                gapi_metadata: GapisMetadata = None
                with open(json_path) as raw_metadata:
                    raw_metadata = json.load(raw_metadata)
                    gapi_metadata = GapisMetadata(**raw_metadata)

                created_date = get_date_from_meta(gapi_metadata)
                aspect_ratio = float(gapi_metadata.mediaMetadata.width) / float(
                    gapi_metadata.mediaMetadata.height
                )

                # metadata[file_name] = (aspect_ratio, created_date)
                thumbnail_file_name = f"{file_name}.jpg" if is_for_videos else None
                # logging.info(f"Instantiating meta: {file_name}, {thumbnail_file_name}, {aspect_ratio}, {created_date}")
                metadata.append(
                    CsvEntry(
                        file_name=file_name,
                        thumbnail_file_name=thumbnail_file_name,
                        aspect_ratio=aspect_ratio,
                        created_date=created_date,
                    )
                )

            except ValidationError as ve:
                logging.error(f"Validation error while processing {meta_file_name}:")
                for error in ve.errors():
                    logging.error(
                        f"  {error['loc'][0]}: {error['msg']} (type={error['type']})"
                    )
                raise ve
            except Exception as ex:
                logging.exception("{}: {}".format(meta_file_name, ex), exc_info=False)
                raise ex

        # metadata = {
        #     k: v
        #     for k, v in sorted(
        #         metadata.items(), key=lambda item: item[1][1], reverse=True
        #     )
        # }
        metadata = sorted(metadata, key=lambda entry: entry.created_date, reverse=True)

        for row in metadata:
            if is_for_videos:
                thumbnail_folder_name = os.path.basename(thumbnail_directory)
                video_folder_name =  os.path.basename(source_directory)
                csv_out.write(
                    '"{}","{}",{:.3f},{}\n'.format(
                        os.path.join(video_folder_name, row.file_name),
                        os.path.join(thumbnail_folder_name, row.thumbnail_file_name),
                        row.aspect_ratio,
                        row.created_date,
                    )
                )
            else:
                csv_out.write(
                    '"{}",{:.3f},{}\n'.format(
                        row.file_name, row.aspect_ratio, row.created_date
                    )
                )
        csv_out.close()


@click.command()
def main():
    script_directory = get_script_directory()
    parent_directory = os.path.dirname(script_directory)
    image_thumbnail_directory = os.path.join(parent_directory, "thumbnail")
    video_thumbnail_directory = os.path.join(parent_directory, "video_thumbnail")
    # web_directory = os.path.join(parent_directory, "web")
    image_metadata_file = os.path.join(parent_directory, "photos.csv")
    video_metadata_file = os.path.join(parent_directory, "videos.csv")
    image_source_directory = os.path.join(parent_directory, "images")
    video_source_directory = os.path.join(parent_directory, "videos")
    
    print("Regenerating image metadata...")
    regenerate_csv(
        image_source_directory, image_thumbnail_directory, image_metadata_file, False
    )
    # print("Processing images...")
    # process_images(image_source_directory, thumbnails_directory, image_metadata_file)
    print("Regenerating video metadata...")
    regenerate_csv(
        video_source_directory, video_thumbnail_directory, video_metadata_file, True
    )


if __name__ == "__main__":
    coloredlogs.install(level="INFO")
    main()

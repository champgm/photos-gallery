import sys
import typing
import PIL
import os
import numpy as np
import datetime as dt
import logging
import coloredlogs
import random
import functools
import click
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageFile, ExifTags
from PIL import Image, ImageFile

def open_metadata_file(csv_file: str) -> Dict[str, Tuple[str, dt.datetime, str]]:
    def chomp(string: str, start_char: str, end_char: str) -> Tuple[str, str]:
        chomp: str = ''
        l_index = string.find(start_char)
        if l_index >= 0:
            r_index = string.find(end_char, l_index + 1)
            if r_index < 0:
                return ('', string)
            chomp = string[l_index:r_index + 1]
            return (chomp, string[r_index + 1:])
        else:
            return ('', string)
    processed: Dict[str, Tuple[str, dt.datetime, str]] = {}
    if not os.path.exists(csv_file):
        return processed
    with open(csv_file, 'r') as f:
        line = f.readline()
        while line:
            filename, line = chomp(line, '"', '"')
            split = line[1:].split(',')
            if len(split) == 3:
                ar = split[0]
                c_date = dt.datetime.strptime(split[1].strip(), '%Y-%m-%d %H:%M:%S')
                tokens = split[2].strip()
            else:
                ar = split[0]
                c_date = dt.datetime.strptime(split[1].strip(), '%Y-%m-%d %H:%M:%S')
                tokens = ''
            if '"' in filename:
                filename = filename.replace('"', '')
            processed[filename] = (ar, c_date, tokens)
            line = f.readline()
    return processed

def get_aspect_ratio(im: Image) -> float:
    aspect_ratio = im.size[0] / im.size[1]
    return aspect_ratio

def get_created_date(im: Image) -> dt.datetime:
    if im._getexif() and 36867 in im._getexif():
        created_date = im._getexif()[36867]
    else:
        created_date = '1990:1:1 0:0:0'
    created_date = created_date.strip()
    photo_date = dt.datetime(1990, 1, 1)
    try:
        photo_date = dt.datetime.strptime(created_date, '%Y:%m:%d %H:%M:%S')
    except Exception as ex:
        logging.debug(ex)
    return photo_date

def rotate_image(im: Image) -> Image:
    try:
        orientation = -1
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation': break
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


def regenerate_metadata_csv(source_directory: str, models_directory: str, csv_file: str) -> None:
    if not os.path.exists(models_directory + '/cities.csv'):
        raise ValueError('models directory {} does not contain cities.csv model'.format(models_directory))

    images = os.listdir(source_directory)
    metadata = {}

    with open(csv_file, 'w') as csv_out:
        for f in images:
            logging.info('regenerating {}'.format(f))
            try:
                im = Image.open(source_directory + '/' + f)

                created_date = get_created_date(im)
                im = rotate_image(im)
                aspect_ratio = get_aspect_ratio(im)

                metadata[f] = (aspect_ratio, created_date)
                im.close()
            except Exception as ex:
                logging.exception('{}: {}'.format(f, ex), exc_info=False)

        metadata = {k: v for k, v in sorted(metadata.items(), key=lambda item: item[1][1], reverse=True)}

        for k, v in metadata.items():
            csv_out.write('"{}",{:.3f},{}\n'.format(k, v[0], v[1]))
        csv_out.close()


def process(source_directory: str,
            thumbnail_directory: str,
            csv_file: str) -> None:
    MAX_SIZE = (640, 640)
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    thumbnail_directory = os.path.abspath(thumbnail_directory)

    source_files = os.listdir(source_directory)
    unprocessed_files = source_files

    if os.path.exists('generate.log'):
        os.remove('generate.log')
    log_file = open('generate.log', 'w')

    thumbnail_files = os.listdir(thumbnail_directory)
    unprocessed_files = np.setdiff1d(source_files, thumbnail_files)
    metadata = open_metadata_file(csv_file)

    csv_out = open(csv_file, 'w')

    logging.info('unprocessed files: {}'.format(len(unprocessed_files)))

    for f in unprocessed_files:
        try:
            im = Image.open(source_directory + '/' + f)

            created_date = get_created_date(im)
            im = rotate_image(im)
            aspect_ratio = get_aspect_ratio(im)

            im.thumbnail(MAX_SIZE, PIL.Image.LANCZOS)
            im.save(thumbnail_directory + '/' + f, format=im.format)

            if f not in metadata:
                metadata[f] = ('{:.3f}'.format(aspect_ratio),
                               created_date)
            logging.info('processed: {}'.format(f))
            im.close()
        except Exception as ex:
            logging.exception('{}: {}'.format(ex, f), exc_info=False)
            log_file.write(f + '\n')
            log_file.flush()

    # order the files by date
    metadata = {k: v for k, v in sorted(metadata.items(), key=lambda item: item[1][1], reverse=True)}

    for k, v in metadata.items():
        csv_out.write('"{}",{},{}\n'.format(k, v[0], v[1]))
    csv_out.close()


@click.command()
@click.option('--source_dir', required=True, default='img', type=click.Path(exists=True),
              help='Source directory of images')
@click.option('--thumbnail_dir', required=True, default='thumbnail', type=click.Path(),
              help='Destination directory of thumbnails')
@click.option('--metadata_file', default='photos.csv', required=True,
              help='Filename for csv that has/will have images metadata')
@click.option('--regenerate_metadata', is_flag=True, help='Refresh images metadata (aspect ratios, search etc)')
def main(source_dir,
         thumbnail_dir,
         metadata_file,
         regenerate_metadata):

    if regenerate_metadata:
        regenerate_metadata_csv(source_dir, metadata_file)
    else:
        process(source_dir, thumbnail_dir, metadata_file)

if __name__ == '__main__':
    coloredlogs.install(level='INFO')
    main()

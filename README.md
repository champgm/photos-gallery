# Google Photos Clone for Amazon S3/Static Hosting

This has a collection of Python scripts, machine learning models, and hacky tricks to create a Google Photos style clone that does not require any server side backend -- it can be hosted as a static site, straight from Amazon S3 or equivalent.

## Setup
* Use chocolatey to install python
* Make a virtual environment: `python -m venv env`
* Activate in windows: `.\env\Scripts\activate`
* Install dependency requirements: `pip install -r requirements.txt`
* (If changed) Update dependency requirements: `pip freeze > requirements.txt`

## Features

* Entirely statically generated and hosted (Just some Javascript, HTML and your images)
* Search/group by year photos were taken
* Infinite scroll like Google Photos

## Steps For Use

### Deploy CloudFormation resources

Right now, this is just an S3 bucket. Deploy it like this:

```
python scripts\deploy.py --bucket-name <your desired bucket name>
```

### Download Your Photos

Sync your photos into a `img` directory using the `sync_from_photos.py` script. This script will download images (and their metadata) from the specified Google Photos album. Here's an example command: 

```
python src/sync_from_photos.py --album-id "laksjhdlfkjhasdflkhjasdoiquwer_al"
```

This command may open up your web browser and ask for permissions to connect your Google Cloud Application to your google account. Make sure you pick the one that contains the pictures you want to sync.

### Generate Static Website Metadata

Call the `generate_photos_gallery.py` script, which will do the following:

* Extract photo creation date from Google Photos metadata
* Generate thumbnails for your images

```
python src/generate_photos_gallery.py
```

Test to see if everything works:

```
python -m http.server 8000
```

browse to http://localhost:8000/


### Synchronize Site To S3

S3 is where the files will be stored for later serving. Synchronize all of the artifacts into your bucket with another script:

```
python src/sync_to_aws.py <your deployed bucket name>
```


![Screenshot](screenshot.png)

## How does it work?

* Uses [Progressive Image Grid](https://github.com/schlosser/pig.js/) from schlosser for Google Photos like infinite scroll.
* Uses some badly written JQuery
* Generates a big metadata csv file (image, aspect ratio, search tokens) that the Javascript frontend downloads and parses for search and image display.

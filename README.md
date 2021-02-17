# ExternalClientReviewSamples

This collection of scripts shows you how to use FLAPI to sync media and metadata (such as marker notes and comments) with some popular media sharing services in order to conduct virtual client reviews.

## Installation
These examples will only work against the FLAPI distributed with `branch-dev-flapi-20` (internal name). A Filmlight staff member will advise you on how to install this build.

These examples were written in Python version 3.7.9 (the highest Python versin supported by Frame.io).

We recommend that you create a Python virtual environment and install FLAPI and required packages inside it.

### Creating a Python Virtual Environment

You can create a virtual environment with `python3 -m venv env`, where `env` is the name of the new environment.

You can activate that environment with `source env/bin/activate`. Your shell prompt will then show the name of the environment in parentheses, indicating that it is active.

To deactivate the environment, run `deactivate`.

### Installing FLAPI

With the virtual environment active, install FLAPI with `pip install /Applications/Baselight/5.3.<version>/Baselight-5.3.<version>.app/Contents/share/flapi/python`. (Subtitute a Daylight application path as necessary.)

### Installing Required Libraries

These examples use a few external libraries. To install them, `pip3 install -r requirements.txt` within your virtueal environement (see above). 

See the sections below for each sharing service for notes on installing any additional Python libraries that these services may require.

### Starting the FLAPI Service

Restart all Daylight/Baselight application services by changing to the `bin` directory inside the installation directory and running `sudo ./fl-service restart`. Make sure in particular that the `flapi` service starts without error.

## A Note on Rendering

Currently, FLAPI cannot render independently of the Baselight/Daylight render service. (This limitation is temporary.) For now, before launching scripts which render output prior to upload to a sharing service, you must first ttart the Baselight/Daylight application, being sure to start the version matching the special build given to you for use with this repo.

## Frame.io Scripts

See this repo's `frame.io` directory.

### Setup

1. You'll need a developer key to run these scripts. See [their docs here](https://developer.frame.io/docs/getting-started/authentication#developer-tokens).

2. You'll need to install [their Python client](https://github.com/Frameio/python-frameio-client) into your virtual environment. Run `pip3 install frameioclient`.

### `share_to_frameio.py` Usage

This script adds a movie and marker notes from the parent BL/DL scene to Frame.io for client review. You can choose an already rendered movie or allow the script to render out whatever deliverable you choose from the parent scene (so long as it produces a movie file).

The script authenticates your account with Frame.io and places the BL/DL-generated movie inside a Frame.io project of your choosing. It creates Frame.io comments from marker notes on frame numbers corresponding to those in the parent BL/DL scene, thus allowing the colourist to start a dialog with the project reviewers. It also creates a Frame.io project review link upon request."

### `sync_comments_from_frameio.py`

This script receives comments from a Frame.io project to which you've previously uploaded as an asset for review via this script's companion, `sharing_to_frameio.py`. It authenticates your account with Frame.io, scrapes comments from the asset of your choosing, then inserts them as marker notes in the BL/DL scene that generated the Frame.io asset. In cases where the BL/DL scene already has a marker note at a given frame, the script appends to this note, referencing author and creation time.


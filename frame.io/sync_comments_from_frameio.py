import flapi
import sys
import time
import bullet
import os
from bullet import Bullet, ScrollBar, YesNo, Input, colors
import glob
from frameioclient import FrameioClient
from getpass import getpass
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import random
import string
from share_to_frameio import FLAPIManager, FrameIOManager, color


def display_help():
    print("\n%sWelcome to the BL/DL Frame.io Comment Syncer%s" %
          (color.BOLD, color.END))
    print("This script receives comments from a Frame.io project to which you've previously uploaded as an asset for review via this script's companion, %ssharing_to_frameio.py%s. It authenticates your account with Frame.io, scrapes comments from the asset of your choosing, then inserts them as marker notes in the BL/DL scene that generated the Frame.io asset. In cases where the BL/DL scene already has a marker note at a given frame, the script appends to this note, referencing author and creation time." % (color.CYAN, color.END))


if __name__ == "__main__":
    display_help()
    flapi_manager = FLAPIManager("localhost")

    # Authenticate with FrameIO and get asset for comments download
    print("\n%sFirst, let's log you into Frame.io and choose the asset whose comments you wish to download.%s" %
          (color.BOLD, color.END))
    frameio_manager = FrameIOManager()
    frameio_manager.authenticate()
    if frameio_manager.frameio_account_id is not None:
        frameio_manager.get_teams(
            "Choose the team hosting the project you want to download comments from:")
    if frameio_manager.frameio_team_id is not None:
        frameio_manager.get_projects(
            "Choose the project hosting the asset you want to download comments from:")
    if frameio_manager.frameio_project_root_id is not None:
        frameio_manager.get_asset(
            "Choose the asset whose comments you wish to download:")
    if frameio_manager.frameio_chosen_asset_id is not None:
        frameio_manager.get_comments()
    if frameio_manager.downloaded_comments is not None:
        print("%sComments recieved from Frame.io.%s" % (color.BOLD, color.END))
        print("%s\nOK, now you're ready to choose the receiving BL/DL scene.%s" %
              (color.BOLD, color.END))
        flapi_manager.get_scene("Choose the job containing the scene you want to sync comments to: ",
                                "Choose the scene you want to sync comments to: ")
        if flapi_manager.scene is not None:
            flapi_manager.sync_frameio_marks(
                frameio_manager.downloaded_comments)

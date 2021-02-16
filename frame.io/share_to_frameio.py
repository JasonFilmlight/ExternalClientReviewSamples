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


class color:
    PURPLE = '\033[1;35;48m'
    CYAN = '\033[1;36;48m'
    BOLD = '\033[1;37;48m'
    BLUE = '\033[1;34;48m'
    GREEN = '\033[1;32;48m'
    YELLOW = '\033[1;33;48m'
    RED = '\033[1;31;48m'
    WHITE = '\033[1;37;48m'
    BLACK = '\033[1;30;48m'
    UNDERLINE = '\033[4;37;48m'
    END = '\033[1;37;0m'


def display_help():
    print("\n%sWelcome to the BL/DL Frame.io Sharer%s" %
          (color.BOLD, color.END))
    print("This script uploads a movie and marker notes from the parent BL/DL scene to Frame.io for client review. You can choose an already rendered movie or allow the script to render out whatever deliverable you choose from the parent scene (so long as it produces a movie file). (Note that the BL/DL GUI must be running in order for the render to progress.) The script authenticates your account with Frame.io and places the BL/DL-generated movie inside a Frame.io project of your choosing. It creates Frame.io comments from marker notes on frame numbers corresponding to those in the parent BL/DL scene, thus allowing the colourist to start a dialog with the project reviewers. It also creates a Frame.io project review link upon request.")


class FLAPIManager():
    jobs_host = None
    flapi_conn = None
    job_name = None
    scene_name = None
    scene = None
    render_setup = None
    deliverable_for_render = None
    deliverable_idx = None
    mark_comments = None
    output_filepath = None
    frameio_comments = None

    def __init__(self, jobs_host=None):
        self.jobs_host = jobs_host

        # Connect to flapi
        self.flapi_conn = flapi.Connection(self.jobs_host)
        self.flapi_conn.connect()

    def __del__(self):
        self.flapi_conn.close()

    def get_scene(self, job_chooser_prompt, scene_chooser_prompt):
        while True:
            jobs = self.flapi_conn.JobManager.get_jobs(self.jobs_host)
            chooser = ScrollBar(prompt="\n%s%s%s " %
                                (color.BOLD, job_chooser_prompt, color.END), choices=jobs, height=15, word_color=colors.foreground["cyan"])
            self.job_name = chooser.launch()
            scenes = self.flapi_conn.JobManager.get_scenes(
                self.jobs_host, self.job_name)

            confirmer = YesNo(prompt="%sUse job %s%s%s?%s " % (
                color.BOLD, color.CYAN, self.job_name, color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

        while True:
            chooser = ScrollBar(prompt="\n%s%s%s " % (color.BOLD, scene_chooser_prompt, color.END),  choices=scenes,
                                height=15, word_color=colors.foreground["cyan"])
            self.scene_name = chooser.launch()

            confirmer = YesNo(prompt="%sUse scene %s%s%s?%s " % (
                color.BOLD, color.CYAN, self.scene_name, color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

        # Open the given scene
        scene_path = self.flapi_conn.Scene.parse_path(
            "%s:%s:%s" % (self.jobs_host, self.job_name, self.scene_name))

        try:
            self.scene = self.flapi_conn.Scene.open_scene(scene_path)
        except flapi.FLAPIException as ex:
            print("%sError loading scene:%s%s " %
                  (color.RED, str(ex), color.END))
            sys.exit(1)

    def get_deliverables(self):
        # Create RenderSetup
        self.render_setup = self.flapi_conn.RenderSetup.create_from_scene(
            self.scene)

        # Prompt for deliverable
        while True:
            deliverable_names = [self.render_setup.get_deliverable(
                i).Name for i in range(self.render_setup.get_num_deliverables())]
            chooser = ScrollBar(prompt="\n%sChoose the deliverable you want to render:%s " % (color.BOLD, color.END),
                                choices=deliverable_names, height=15, word_color=colors.foreground["cyan"], return_index=True)
            self.deliverable_idx = chooser.launch()[1]

            confirmer = YesNo(prompt="%sRender %s%s%s deliverable?%s " % (
                color.BOLD, color.CYAN, deliverable_names[self.deliverable_idx], color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

        # Enable only selected deliverable
        for i in range(self.render_setup.get_num_deliverables()):
            if i == self.deliverable_idx:
                self.render_setup.set_deliverable_enabled(i, 1)
            else:
                self.render_setup.set_deliverable_enabled(i, 0)

        self.deliverable_for_render = self.render_setup.get_deliverable(
            self.deliverable_idx)
        if self.deliverable_for_render.IsMovie == 0:
            print("%sDeliverable must output a movie file, not sequence. Edit deliverable in the GUI Render Panel and save scene.%s" % (
                color.BOLD, color.END))
            sys.exit(1)

    def get_all_marks(self, verbose = False):
        print("\n%sGetting mark comments . . . %s" % (color.BOLD, color.END))
        self.mark_comments = []

        # Get timeline marks
        for mark_id in self.scene.get_mark_ids():
            mark = self.scene.get_mark(mark_id)
            if mark.get_note_text() is not None:
                self.mark_comments.append(
                    [mark.get_record_frame(), mark.get_note_text()]
                )

        # Get shot marks
        shot_ids = self.scene.get_shot_ids()
        if len(shot_ids) > 0:
            for shot_id in shot_ids:
                shot = self.scene.get_shot(shot_id.ShotId)
                for mark_id in shot.get_mark_ids():
                    mark = shot.get_mark(mark_id)
                    if mark.get_note_text() is not None:
                        self.mark_comments.append(
                            [mark.get_record_frame(), mark.get_note_text()]
                        )
        
        if verbose:
            print("Found these:")
            for m in self.mark_comments:
                print("%s%s%s (@ frame number %i)" %
                    (color.CYAN, m[1], color.END, m[0]))

    def sync_frameio_marks(self, frameio_comments):  

        self.get_all_marks()

        self.scene.start_delta("Insert comments")

        for fio_comment in frameio_comments:
            ts = fio_comment['timestamp']
            if ts is None:
                # Reply case
                ts = [c for c in frameio_comments if c['id'] == fio_comment['parent_id']][0]['timestamp']

            email = None
            if fio_comment['owner_id'] is not None:
                email = fio_comment['owner']['email']
            else:
                email= fio_comment['anonymous_user']['email']

            cat_name = "frame.io_" + email

            time_of_comment = fio_comment['inserted_at'].replace("T", " ").split(".")[0]

            note = fio_comment['text'] + "\n(Frame.io comment from " + email + ", made @ " + time_of_comment + ")"

            # Add a random purplish color close toe the Frame.io trademark purple
            marker_color = [88/255.0 + random.uniform(-0.1, 0.1), 91/255.088/255.0 + random.uniform(-0.1, 0.1), 246/255.088/255.0 + random.uniform(-0.1, 0.1) + 1.0]

            if cat_name not in self.scene.get_mark_categories():
                self.scene.set_category(cat_name, marker_color)

            if len([x for x in self.mark_comments if x[0] == int(ts) and x[1] == fio_comment['text']]) == 0: # New mark only if text not already on timeline
                print("Inserting Frame.io comment marker at frame %i." % int(ts))
                if cat_name not in self.scene.get_mark_categories():
                    self.scene.set_category(cat_name, marker_color)
                self.scene.add_mark(int(ts), cat_name, note)
            

        self.scene.end_delta()
        # Close the scene
        self.scene.save_scene()
        self.scene.close_scene()
        self.scene.release()

    def render(self):
        print("\n%sCommencing render . . . %s" % (color.BOLD, color.END))

        # Temporarily set the root of the output render path to working directory of script
        output_root = os.getcwd() + "/_renders/"
        self.render_setup.set_container(output_root)

        # self.scene.save_scene()

        # Create Queue Manager
        print("Opening QueueManager connection . . . ")
        qm = self.flapi_conn.QueueManager.create_local()

        # Submit render job to Queue
        print("Submitting to queue . . .  (Note that the BL/DL GUI must be running in order for the render to progress.")
        opinfo = self.render_setup.submit_to_queue(qm, "Frame.io render deliverable: %s:%s:%s" % (
            self.jobs_host, self.job_name, self.scene_name))

        print("Created operation id %d" % opinfo.ID)
        if opinfo.Warning != None:
            print("%sWarning: %s%s" % (color.RED, opinfo.Warning, color.END))

        # We're finished with RenderSetup now
        self.render_setup.release()

        # We're finished with Scene now
        self.scene.close_scene()
        self.scene.release()

        # Wait on job to finish
        print("Waiting on render job to complete.\nRender progress:")

        while True:
            opstat = qm.get_operation_status(opinfo.ID)
            print("  Status: {Status} {Progress:.0%} {ProgressText}\r".format(
                **vars(opstat)), end="")
            if opstat.Status == "Done":
                break
            time.sleep(0.5)

        print("Operation complete")

        # Remove completed operation from queue
        print("Archiving operaton")
        qm.archive_operation(opinfo.ID)

        qm.release()

        print(output_root + "**/*" + self.deliverable_for_render.FileNameExtension)
        files = glob.glob(
            output_root + "**/*" + self.deliverable_for_render.FileNameExtension, recursive=True)
        if len(files) > 0:
            self.output_filepath = max(files, key=os.path.getctime)
            print("Output pathname is %s%s%s." %
                  (color.CYAN, self.output_filepath, color.END))
        else:
            print("%sRender output pathname could not be determined.%s" %
                  (color.RED, color.END))


class FrameIOManager():
    movie_file_path = None
    comments_for_upload = None
    downloaded_comments = None
    frameio_token = None
    frameio_client = None
    frameio_account_id = None
    frameio_team_id = None
    frameio_project_root_id = None
    frameio_project_id = None
    frameio_chosen_asset_id = None
    frameio_new_asset_id = None
    frameio_review_link_id = None

    def authenticate(self):
        self.frameio_token = getpass(prompt="\n%sCopy/paste your Frame.io developer key (input hidden):%s " % (color.BOLD, color.END))
        try:
            self.frameio_client = FrameioClient(self.frameio_token)
            me = self.frameio_client.get_me()
            print("Authorization successful. Account ID is %s%s%s." %
                  (color.CYAN, me['account_id'], color.END))
            self.frameio_account_id = me['account_id']
        except Exception as e:
            print("%sThere was a problem with the developer key:%s%s " %
                  (color.RED, str(e), color.END))
            confirmer = YesNo("%sTry entering another?%s " % (
                color.BOLD, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                self.authenticate()
            else:
                sys.exit(1)

    def get_teams(self, chooser_prompt):
        teams = None
        try:
            teams = self.frameio_client.get_teams(self.frameio_account_id)
        except Exception as e:
            print("%sThere was a problem retrieving teams: %s%s " %
                  (color.RED, str(e), color.END))
            sys.exit(1)

        teams_out = [[x['id'], x['name']] for x in teams]

        while True:
            choices = [x[1] for x in teams_out]
            chooser = ScrollBar(prompt="\n%s%s %s" % (color.BOLD, chooser_prompt, color.END),
                                choices=choices, height=15, word_color=colors.foreground["cyan"], return_index=True)
            team_idx = chooser.launch()[1]
            self.frameio_team_id = teams_out[team_idx][0]

            confirmer = YesNo(prompt="%sUse %s%s%s team?%s " % (
                color.BOLD, color.CYAN, choices[team_idx], color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

    def create_project(self):
        while True:
            namer = Input(prompt="\n%sEnter a name for the new project:%s " % (
                color.BOLD, color.END), word_color=colors.foreground["cyan"])
            new_project_name = namer.launch()

            confirmer = YesNo(prompt="%sCreate %s%s%s project?%s " % (
                color.BOLD, color.CYAN, new_project_name, color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

        print("Creating %s project . . . " % new_project_name)
        self.frameio_client.create_project(
            team_id=self.frameio_team_id,
            name=new_project_name
        )

        print("Getting root ID of %s . . . " % new_project_name)
        projects = self.frameio_client.get_projects(self.frameio_team_id)
        new_project = [x for x in projects if x['name'] == new_project_name][0]
        self.frameio_project_root_id = new_project['root_asset_id']
        self.frameio_project_id = new_project['id']

    def get_projects(self, chooser_prompt):
        try:
            projects = self.frameio_client.get_projects(self.frameio_team_id)
            projects_out = [[x['root_asset_id'], x['name'], x['id']]
                            for x in projects]
            # if len(projects_out) == 1:
            #     print("Using %s%s%s as project (only one available)." %
            #           (color.CYAN, projects_out[0][1], color.END))
            #     self.frameio_project_root_id = projects_out[0][0]
            # else:

        except Exception as e:
            print("%sThere was a problem retrieving projects: %s%s " %
                  (color.RED, str(e), color.END))
            system.exit(1)

        while True:
            choices = [x[1] for x in projects_out]
            chooser = ScrollBar(prompt="\n%s%s%s " % (color.BOLD, chooser_prompt, color.END),
                                choices=choices, height=15, word_color=colors.foreground["cyan"], return_index=True)
            project_idx = chooser.launch()[1]
            self.frameio_project_root_id = projects_out[project_idx][0]
            self.frameio_project_id = projects_out[project_idx][2]

            confirmer = YesNo(prompt="%sUse %s%s%s?%s " % (
                color.BOLD, color.CYAN, choices[project_idx], color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

    def get_asset(self, chooser_prompt):
        try:
            assets = self.frameio_client.get_asset_children(self.frameio_project_root_id)
            assets_out = [[x['name'], x['id']] for x in assets]

        except Exception as e:
            print("%sThere was a problem retrieving assets: %s%s " %
                  (color.RED, str(e), color.END))
            system.exit(1)

        while True:
            choices = [x[0] for x in assets_out]
            chooser = ScrollBar(prompt="\n%s%s%s " % (color.BOLD, chooser_prompt, color.END),
                                choices=choices, height=15, word_color=colors.foreground["cyan"], return_index=True)
            asset_idx = chooser.launch()[1]
            self.frameio_chosen_asset_id = assets_out[asset_idx][1]

            confirmer = YesNo(prompt="%sUse %s%s%s?%s " % (
                color.BOLD, color.CYAN, choices[asset_idx], color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

    def get_comments(self):
        try:
            self.downloaded_comments = self.frameio_client.get_comments(self.frameio_chosen_asset_id)

        except Exception as e:
            print("%sThere was a problem retrieving comments: %s%s " %
                  (color.RED, str(e), color.END))
            system.exit(1)

    def get_movie_file(self):
        print(color.BOLD + "\nChoose a movie file from the dialog that appears.")
        root = tk.Tk()
        root.withdraw()
        filepath = filedialog.askopenfilename(
            title="Choose a movie file for upload.")

        confirmer = YesNo(prompt="%sUse file %s%s%s?%s " % (
            color.BOLD, color.CYAN, filepath, color.WHITE, color.END), word_color=colors.foreground["cyan"])
        ans = confirmer.launch()
        if ans:
            self.movie_file_path = filepath
        else:
            get_movie_file()

    def get_newly_posted_asset_id(self):
        assets = self.frameio_client.get_asset_children(
            self.frameio_project_root_id)
        name_filtered_assets = [
            [
                x['id'],
                datetime.strptime(x['uploaded_at'],
                                  '%Y-%m-%dT%H:%M:%S.%fZ').timestamp()
            ] for x in assets if x['name'] == self.movie_file_path.split("/")[-1]
        ]
        if len(name_filtered_assets) == 0:
            print("%sSorry, there was a problem finding the newly uploaded asset on Frame.io. Check the site to see if it was successfully uploaded.%s" % (
                color.RED, color.END))
        elif len(name_filtered_assets) == 1:
            self.frameio_new_asset_id = name_filtered_assets[0][0]
        elif len(name_filtered_assets) > 1:
            # Sort such that most recently uploaded is at bottom
            name_filtered_assets.sort(key=lambda x: x[1])
            self.frameio_new_asset_id = name_filtered_assets[-1][0]

    def upload_file(self):
        print("%s\nUploading to Frame.io (this may take a while) . . . %s" %
              (color.BOLD, color.END))
        filesize = os.path.getsize(self.movie_file_path)

        asset = self.frameio_client.create_asset(
            parent_asset_id=self.frameio_project_root_id,
            name=self.movie_file_path.split("/")[-1],
            type="file",
            filetype="video/quicktime",
            filesize=filesize
        )

        file = open(self.movie_file_path, 'rb')
        self.frameio_client.upload(asset, file)

    def post_comments(self):
        print("%s\nPosting comments to new asset . . . %s" %
              (color.BOLD, color.END))
        for i, comment in enumerate(self.comments_for_upload):
            self.frameio_client.create_comment(
                asset_id=self.frameio_new_asset_id,
                timestamp=comment[0],
                text=comment[1]
            )
            print("Posted comment %s#%i%s." % (color.CYAN, i, color.END))

    def create_review_link(self):
        print("%s\nCreating a review link . . . %s" % (color.BOLD, color.END))

        while True:
            namer = Input(prompt="%sEnter a namee for the link (include job name, etc.):%s " % (
                color.BOLD, color.END), word_color=colors.foreground["cyan"])
            name = namer.launch()

            confirmer = YesNo(prompt="%sUse %s%s%s as the review link name?%s " % (
                color.BOLD, color.CYAN, name, color.WHITE, color.END), word_color=colors.foreground["cyan"])
            ans = confirmer.launch()
            if ans:
                break
            else:
                continue

        # Enable password protection if you have Pro Frame.io account.
        # password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        # print("%sAssigning %s%s%s as the review link password. (Write it down as it won't be shown again.)%s" % (color.BOLD, color.CYAN, password, color.WHITE, color.END))

        # Create the link
        self.frameio_client.create_review_link(
            project_id=self.frameio_project_id,
            name=name  # ,
            # password=password
        )

        # Retrieve it
        links = self.frameio_client.get_review_links(self.frameio_project_id)
        name_filtered_links = [
            [
                x['short_url'],
                datetime.strptime(x['inserted_at'],
                                  '%Y-%m-%dT%H:%M:%S.%fZ').timestamp(),
                x['id']
            ] for x in links if x['name'] == name
        ]

        url = None
        if len(name_filtered_links) == 0:
            print("%sSorry, there was a problem finding the newly created review link on Frame.io. Check the site to see if it was successfully created, and, if not, manually create it using the web UI.%s" % (color.RED, color.END))
            sys.exit(1)
        elif len(name_filtered_links) == 1:
            url = name_filtered_links[0][0]
            self.frameio_review_link_id = name_filtered_links[0][2]
        elif len(name_filtered_links) > 1:
            # Sort such that most recently inserted is at bottom
            name_filtered_links.sort(key=lambda x: x[1])
            url = name_filtered_links[-1][0]
            self.frameio_review_link_id = name_filtered_links[-1][2]

        if url is not None:
            print("%sThe URL for the new review link is %s%s%s. Feel free to send it on to your clients. (Go to the Frame.io site if you forget this URL.)%s" % (
                color.BOLD, color.CYAN, url, color.WHITE, color.END))

    def add_new_asset_to_review_link(self):
        print("%sAdding newly uploaded asset to review link . . . %s" %
              (color.BOLD, color.END))

        try:
            self.frameio_client.update_review_link_assets(
                link_id=self.frameio_review_link_id,
                asset_ids=[self.frameio_new_asset_id]
            )
        except Exception as e:
            print("%sError adding asset to review link: %s%s " %
                  (color.RED, str(ex), color.END))
            sys.exit(1)


if __name__ == "__main__":
    display_help()

    flapi_manager = FLAPIManager("localhost")

    # Authenticate with FrameIO and get upload destination
    print("\n%sFirst, let's log you into Frame.io and choose a destination project for the BL/DL generated media.%s" %
              (color.BOLD, color.END))
    frameio_manager = FrameIOManager()
    frameio_manager.authenticate()
    if frameio_manager.frameio_account_id is not None:
        frameio_manager.get_teams("Choose the team hosting the project you want to upload to:")

        chooser = ScrollBar(prompt="\n%sShare to a new Frame.io project or an existing one?%s " % (color.BOLD, color.END),
                            choices=["Create new project", "Choose existing project"], height=15, word_color=colors.foreground["cyan"], return_index=True)
        choice = chooser.launch()[1]
        if choice == 0:
            frameio_manager.create_project()
        else:
            frameio_manager.get_projects("Choose the project you want to upload to:")
    # Get assets
    if frameio_manager.frameio_project_id is not None:
        print(color.BOLD + "\nNow let's get an asset for upload.")
        confirmer = YesNo(prompt="%sHave you already rendered the scene out for upload?%s " % (
            color.BOLD, color.END), word_color=colors.foreground["cyan"])
        ans = confirmer.launch()
        # Already rendered case
        if ans:
            frameio_manager.get_movie_file()
            if frameio_manager.movie_file_path is not None and os.path.isfile(frameio_manager.movie_file_path):
                confirmer = YesNo(prompt="%sDo you want to parse marker comments from this file's parent BL/DL scene?%s " %
                                (color.BOLD, color.END), word_color=colors.foreground["cyan"])
                ans = confirmer.launch()
                # But do parse comments from parent scene
                if ans:
                    flapi_manager.get_scene("Choose the job containing the scene you want to parse for comments: ", "Choose the scene you want to parse for comments: ")
                    if flapi_manager.scene is not None:
                        flapi_manager.get_all_marks()
                        if len(flapi_manager.mark_comments) > 0:
                            frameio_manager.comments_for_upload = flapi_manager.mark_comments
        # Need to render case
        else:
            flapi_manager.get_scene("Choose the job containing the scene you want to render: ", "Choose the scene you want to render: ")
            if flapi_manager.scene is not None:
                flapi_manager.get_all_marks(True)
                flapi_manager.get_deliverables()
                flapi_manager.render()
                if flapi_manager.output_filepath is not None and os.path.isfile(flapi_manager.output_filepath):
                    frameio_manager.movie_file_path = flapi_manager.output_filepath
                if len(flapi_manager.mark_comments) > 0:
                    frameio_manager.comments_for_upload = flapi_manager.mark_comments
        # Upload
        if frameio_manager.movie_file_path is not None:
            frameio_manager.upload_file()
            frameio_manager.get_newly_posted_asset_id()
        # Post comments
        if frameio_manager.frameio_new_asset_id is not None:
            if frameio_manager.comments_for_upload is not None:
                if len(frameio_manager.comments_for_upload) > 0:
                    frameio_manager.post_comments()
        # Create review link
        confirmer = YesNo(prompt="\n%sCreate a review link to the parent project of the newly uploaded asset?%s " % (
            color.BOLD, color.END), word_color=colors.foreground["cyan"])
        ans = confirmer.launch()
        if ans:
            if frameio_manager.frameio_project_id is not None:
                frameio_manager.create_review_link()
                if frameio_manager.frameio_review_link_id is not None and frameio_manager.frameio_new_asset_id is not None:
                    frameio_manager.add_new_asset_to_review_link()

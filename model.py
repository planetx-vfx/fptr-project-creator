"""Model for the NFA ShotGrid Project Creator, written by Mervin van Brakel (2024)"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass
from typing import Callable

from PySide2 import QtCore
from shotgun_api3 import shotgun


@dataclass
class ProjectInformation:
    """Dataclass used for storing all the information we need to create the project."""

    username: str
    project_name: str
    has_production_code: bool
    project_code: str
    has_other_supervisors: bool
    supervisor_list: list[dict]
    project_type: str
    project_fps: str


@dataclass
class UserInformation:
    """Dataclass used for storing information about the user who creates the project."""

    sg_username: str
    sg_user_id: str


class ValidationError(Exception):
    """Custom exception that gets raised when validation fails."""


class ProjectCreatorModel:
    """Model for the ShotGrid Project Creator.

    This model handles all validation and ShotGrid interfacing."""

    def __init__(self, controller) -> None:
        """Initializes this class and stores the project dataclass."""
        self.controller = controller

        self.project_information = ProjectInformation(
            username="",
            project_name="",
            has_production_code=True,
            project_code="",
            has_other_supervisors=False,
            supervisor_list=[],
            project_type="Fiction",
            project_fps="24.00",
        )

    def connect_to_shotgrid(
        self,
        connection_successful_function: Callable,
        connection_failed_function: Callable,
    ) -> None:
        """Connects to ShotGrid database on a separate thread.

        Args:
            connection_successful_function: Function that gets called when connection is successful.
            connection_failed_function: Function that gets called when connection failed.
        """
        self.shotgrid_connection_thread = ShotGridConnectionThread(self)

        self.shotgrid_connection_thread.shotgrid_connection_successful.connect(
            connection_successful_function
        )
        self.shotgrid_connection_thread.shotgrid_connection_failed.connect(
            connection_failed_function
        )

        self.shotgrid_connection_thread.start()

    def create_shotgrid_connection(self) -> None:
        """Starts our ShotGrid connection and retrieves useful information to
        speed up the program.
        """
        self.shotgrid_connection = shotgun.Shotgun(
            self.controller._sg_url,
            script_name=self.controller._script_name,
            api_key=self.controller._api_key,
        )

        users = self.shotgrid_connection.find("HumanUser", [], ["name"])
        self.usernames = [user["name"] for user in users]

        projects = self.shotgrid_connection.find("Project", [], ["name"])
        self.projects = [project["name"] for project in projects]

        project_codes = self.shotgrid_connection.find("Project", [], ["sg_short_name"])
        self.project_codes = [
            project_code["sg_short_name"] for project_code in project_codes
        ]

        self.project_types = self.shotgrid_connection.schema_field_read(
            "Project", "sg_type"
        )["sg_type"]["properties"]["valid_values"]["value"]
        self.project_types = [
            ptype for ptype in self.project_types if "template" not in ptype.lower()
        ]

        self.fps_values = sorted(
            self.shotgrid_connection.schema_field_read("Project", "sg_frame_rate")[
                "sg_frame_rate"
            ]["properties"]["valid_values"]["value"],
            key=float,
        )

    def get_shotgrid_user_from_computer_username(self) -> bool:
        """Checks if the username of the computer matches an account name
        in the ShotGrid database. At school this is usually the case.

        Returns:
            Whether or not usernames match.
        """
        username = os.getlogin()
        return self.get_shotgrid_user(username)

    def get_shotgrid_user(self, username: str) -> dict | None:
        """Tries to find a ShotGrid user in the database. This can be based
        on either the 'name' field or 'login' field.

        Args:
            username: ShotGrid user name or login

        Returns:
            ShotGrid user object with needed info fields.
        """
        fields_to_retrieve = [
            "id",
            "name",
            "permission_rule_set",
        ]
        name_field_search = [["name", "contains", username]]
        login_field_search = [["login", "is", username]]

        name_search_user_object = self.shotgrid_connection.find_one(
            "HumanUser", name_field_search, fields_to_retrieve
        )

        if name_search_user_object:
            return name_search_user_object

        login_search_user_object = self.shotgrid_connection.find_one(
            "HumanUser", login_field_search, fields_to_retrieve
        )

        if login_search_user_object:
            return login_search_user_object

        return None

    def set_user_information(self, shotgrid_user: dict) -> None:
        """Stores the correct user information in this class.

        Args:
            shotgrid_user: The ShotGrid user we must store information about.
        """
        shotgrid_user_name = shotgrid_user.get("name")
        shotgrid_user_id = shotgrid_user.get("id")

        self.user_information = UserInformation(
            shotgrid_user_name,
            shotgrid_user_id,
        )

    def validate_project_name(self, project_name: str) -> None:
        """Validates the project name.

        Args:
            project_name: The string name for the project.
        """
        self.project_information.project_name = project_name

        if not project_name:
            validation_message = "You must fill in a project name"
            raise ValidationError(validation_message)

        legal_characters = "^[a-z_]*$"
        contains_only_legal_characters = re.match(legal_characters, project_name)

        if not contains_only_legal_characters:
            validation_message = (
                "Project name may only use lowercase a-z and underscores."
            )
            raise ValidationError(validation_message)

        if project_name in self.projects:
            validation_message = "Project name already taken."
            raise ValidationError(validation_message)

    def validate_project_code(self, project_code: str) -> None:
        """Validates the project code.

        Args:
            project_code: The string project code.
        """
        self.project_information.project_code = project_code.lower()

        if self.project_information.has_production_code:
            legal_characters = "^[Pp0-9]+$"
            code_length = 6
            legal_character_warning = (
                "Production code should start with a p and contain 5 numbers."
            )
        else:
            legal_characters = "^[A-Za-z]+$"
            code_length = 3
            legal_character_warning = "Three-letter code should only use letters a-z."

        contains_only_legal_characters = re.match(legal_characters, project_code)

        if not contains_only_legal_characters:
            raise ValidationError(legal_character_warning)

        if len(project_code) != code_length:
            validation_message = f"Project code uses {'more' if len(project_code) > code_length else 'less'} characters than allowed."
            raise ValidationError(validation_message)

        if project_code.lower() in self.project_codes:
            validation_message = "Project code already taken."
            raise ValidationError(validation_message)

    def set_has_production_code(self, has_code: bool) -> None:
        """Sets production code bool on the dataclass.

        Args:
            has_code: Wether or not project has production code.
        """
        self.project_information.has_production_code = has_code

    def add_supervisor(self, supervisor_name: str) -> str:
        """Validates the name of a supervisor and adds it to the dataclass.

        Args:
            supervisor_name: The username of the supervisor to add.

        Returns:
            Username after validation.
        """
        supervisor_user_object = self.get_shotgrid_user(supervisor_name)

        if not supervisor_user_object:
            validation_message = "Could not find supervisor name in ShotGrid database."
            raise ValidationError(validation_message)

        if supervisor_user_object in self.project_information.supervisor_list:
            validation_message = "This supervisor has already been added."
            raise ValidationError(validation_message)

        self.project_information.supervisor_list.append(supervisor_user_object)
        return supervisor_user_object.get("name")

    def remove_supervisor(self, supervisor_name: str) -> None:
        """Removes the given supervisor from the dataclass.

        Args:
            supervisor_name: Username of supervisor to remove
        """
        supervisor_user_object = self.get_shotgrid_user(supervisor_name)

        if supervisor_user_object not in self.project_information.supervisor_list:
            validation_message = "Can't remove because supervisor isn't on the list."
            raise ValidationError(validation_message)

        self.project_information.supervisor_list.remove(supervisor_user_object)

    def set_project_type(self, project_type: str) -> None:
        """Sets the project type on the dataclass.

        Args:
            project_type: Project type to use. Either fiction or documentary.
        """
        self.project_information.project_type = project_type

    def set_fps(self, fps: str) -> None:
        """Sets the project FPS

        Args:
            fps: FPS to set.
        """
        self.project_information.project_fps = fps

    def validate_project(self):
        """Runs through all validation again."""

        self.validate_project_name(self.project_information.project_name)

        self.validate_project_code(self.project_information.project_code)

        if not self.project_information.supervisor_list:
            validation_message = "You haven't yet added any supervisors."
            raise ValidationError(validation_message)

    def get_formatted_supervisors_list(self, supervisors_list: list) -> list[dict]:
        """Reworks the supervisor list into the list format that ShotGrid expects.
        Also adds the correct permissions to the supervisors on the list.

        Args:
            supervisors_list: List of supervisor usernames.

        Returns:
            List of dicts with supervisor ID and type.
        """
        formatted_supervisors_list = []
        for supervisor in supervisors_list:
            formatted_supervisors_list.append(
                {"id": supervisor.get("id"), "type": "HumanUser"}
            )

            self.add_supervisor_permissions_to_user(supervisor)

        return formatted_supervisors_list

    @staticmethod
    def get_pipeline_configuration_string(student_year: int) -> str:
        return f"sgtk:descriptor:git_branch?branch=release/s{student_year}&path=https://github.com/nfa-vfxim/nfa-shotgun-configuration.git"

    def add_supervisor_permissions_to_user(self, shotgrid_user: dict) -> None:
        """Adds the supervisor permission group to the user if they still have artist permissions.

        Args:
            shotgrid_user: ShotGrid user object to update
        """
        user_permission_group = shotgrid_user.get("permission_rule_set").get("name")

        if user_permission_group == "Artist":
            new_permission_configuration = {
                "permission_rule_set": {
                    "id": 190,
                    "name": "Supervisor",
                    "type": "PermissionRuleSet",
                }
            }
            self.shotgrid_connection.update(
                "HumanUser",
                shotgrid_user.get("id"),
                new_permission_configuration,
            )

    def start_project_creation(
        self,
        creation_successful_function: Callable,
        creation_failed_function: Callable,
    ) -> None:
        """Starts the project creation on a separate thread.

        Args:
            creation_successful_function: Function that gets called when creation is successful.
            creation_failed_function: Function that gets called when creation failed.
        """
        self.project_creation_thread = ProjectCreationThread(self)

        self.project_creation_thread.project_creation_successful.connect(
            creation_successful_function
        )
        self.project_creation_thread.project_creation_failed.connect(
            creation_failed_function
        )

        self.project_creation_thread.start()

    def create_project(self) -> str:
        """Creates the ShotGrid project and adds the pipeline configuration.

        Returns:
            Link to project page.
        """
        formatted_supervisors_list = self.get_formatted_supervisors_list(
            self.project_information.supervisor_list
        )

        tank_name = f"{self.project_information.project_code.strip()}_{self.project_information.project_name.strip()}".replace(
            " ", "_"
        )
        project_data = {
            "name": self.project_information.project_name,
            "tank_name": tank_name,
            "code": self.project_information.project_code,
            "sg_short_name": self.project_information.project_code,
            "users": formatted_supervisors_list,
            "sg_type": self.project_information.project_type,
            "sg_frame_rate": self.project_information.project_fps,
            "sg_status": "Active",
            # TODO select template
        }

        created_project = self.shotgrid_connection.create("Project", project_data)
        project_id = created_project.get("id")

        pipeline_configuration_data = {
            "code": "Primary",
            "descriptor": self.get_pipeline_configuration_string(1),
            "plugin_ids": "basic.*",
            "project": {"id": project_id, "type": "Project"},
        }
        self.shotgrid_connection.create(
            "PipelineConfiguration", pipeline_configuration_data
        )

        # TODO add production logs

        return f"{self.controller._sg_url}page/project_overview?project_id={project_id}"


class ShotGridConnectionThread(QtCore.QThread):
    """Class for connecting to ShotGrid on a separate thread
    so the UI doesn't freeze."""

    shotgrid_connection_successful = QtCore.Signal(object)
    shotgrid_connection_failed = QtCore.Signal(object)

    def __init__(self, model):
        super().__init__()
        self.model = model

    def run(self):
        try:
            connection_information = self.model.create_shotgrid_connection()
            self.shotgrid_connection_successful.emit(connection_information)
        except Exception as error:
            self.shotgrid_connection_failed.emit(str(error))


class ProjectCreationThread(QtCore.QThread):
    """Class for creating the ShotGrid project on a separate thread
    so the UI doesn't freeze."""

    project_creation_successful = QtCore.Signal(object)
    project_creation_failed = QtCore.Signal(object)

    def __init__(self, model):
        super().__init__()
        self.model = model

    def run(self):
        try:
            project_url = self.model.create_project()
            self.project_creation_successful.emit(project_url)
        except Exception as error:
            self.project_creation_failed.emit(str(error))

# -*- coding: utf8 -*-
# This file is part of PYBOSSA.
#
# Copyright (C) 2015 Scifabric LTD.
#
# PYBOSSA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PYBOSSA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PYBOSSA.  If not, see <http://www.gnu.org/licenses/>.
"""
PYBOSSA api module for exposing domain object Task via an API.

This package adds GET, POST, PUT and DELETE methods for:
    * tasks

"""
from flask import abort
from flask.ext.login import current_user
from werkzeug.exceptions import BadRequest, Conflict
from pybossa.model.task import Task
from pybossa.model.project import Project
from pybossa.core import result_repo
from pybossa.util import sign_task
from api_base import APIBase
from pybossa.api.pwd_manager import get_pwd_manager
from pybossa.util import get_user_id_or_ip, validate_required_fields
from pybossa.core import task_repo
from pybossa.cache.projects import get_project_data
import json
import copy


class TaskAPI(APIBase):

    """Class for domain object Task."""

    __class__ = Task
    reserved_keys = set(['id', 'created', 'state', 'fav_user_ids',
        'calibration'])

    immutable_keys = set(['project_id'])

    def _forbidden_attributes(self, data):
        for key in data.keys():
            if key in self.reserved_keys:
                raise BadRequest("Reserved keys in payload")

    def _update_attribute(self, new, old):
        gold_task = bool(new.gold_answers)
        if (new.state == 'completed'):
            n_taskruns = len(new.task_runs)
            if gold_task or (old.n_answers < new.n_answers and
                n_taskruns < new.n_answers):
                new.state = 'ongoing'
        new.calibration = int(gold_task)
        new.exported = gold_task

    def _preprocess_post_data(self, data):
        project_id = data["project_id"]
        info = data["info"]
        duplicate = task_repo.find_duplicate(project_id=project_id, info=info)
        if duplicate:
            message = {
                'reason': 'DUPLICATE_TASK',
                'task_id': duplicate
            }
            raise Conflict(json.dumps(message))
        if 'n_answers' not in data:
            project = Project(**get_project_data(project_id))
            data['n_answers'] = project.get_default_n_answers()
        invalid_fields = validate_required_fields(info)
        if invalid_fields:
            raise BadRequest('Missing or incorrect required fields: {}'
                            .format(','.join(invalid_fields)))
        if data.get('gold_answers'):
            try:
                gold_answers = data['gold_answers']
                if type(gold_answers) is dict:
                    data['calibration'] = 1
                    data['exported'] = True
            except Exception as e:
                raise BadRequest('Invalid gold_answers')

    def _verify_auth(self, item):
        if not current_user.is_authenticated():
            return False
        if current_user.admin or current_user.subadmin:
            return True
        project = Project(**get_project_data(item.project_id))
        pwd_manager = get_pwd_manager(project)
        return not pwd_manager.password_needed(project, get_user_id_or_ip())

    def _sign_item(self, item):
        project_id = item['project_id']
        if current_user.admin or \
           current_user.id in get_project_data(project_id)['owners_ids']:
            sign_task(item)

    def _select_attributes(self, data):
        project_id = data['project_id']
        if current_user.admin or \
            (current_user.subadmin and
                current_user.id in get_project_data(project_id)['owners_ids']):
            pass
        else:
            data.pop('gold_answers', None)
            data.pop('calibration', None)
        return data

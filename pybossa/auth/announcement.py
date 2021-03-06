# -*- coding: utf8 -*-
# This file is part of PYBOSSA.
#
# Copyright (C) 2017 Scifabric LTD.
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


class AnnouncementAuth(object):
    _specific_actions = []

    def __init__(self):
        pass

    @property
    def specific_actions(self):
        return self._specific_actions

    def can(self, user, action, announcement=None):
        action = ''.join(['_', action])
        return getattr(self, action)(user, announcement)

    def _create(self, user, announcement=None):
        if user.is_anonymous() or (announcement is None):
            return False
        if not user.is_anonymous() and user.admin:
            return True
        return False

    def _read(self, user, announcement=None):
        return True

    def _update(self, user, announcement):
        if user.is_anonymous() or (announcement is None):
            return False
        if not user.is_anonymous() and user.admin:
            return True
        return False

    def _delete(self, user, announcement):
        if user.is_anonymous() or (announcement is None):
            return False
        if not user.is_anonymous() and user.admin:
            return True
        return False

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

import requests
from StringIO import StringIO
from flask.ext.babel import gettext
from pybossa.util import unicode_csv_reader, validate_required_fields

from .base import BulkTaskImport, BulkImportException
from flask import request
from werkzeug.datastructures import FileStorage
import io, time, json
from flask import current_app as app
from pybossa.util import get_import_csv_file
import re

class BulkTaskCSVImport(BulkTaskImport):

    """Class to import CSV tasks in bulk."""

    importer_id = "csv"

    def __init__(self, csv_url, last_import_meta=None):
        self.url = csv_url
        self.last_import_meta = last_import_meta

    def tasks(self):
        """Get tasks from a given URL."""
        dataurl = self._get_data_url()
        r = requests.get(dataurl)
        return self._get_csv_data_from_request(r)

    def _get_data_url(self):
        """Get data from URL."""
        return self.url

    def _import_csv_tasks(self, csvreader):
        """Import CSV tasks."""
        headers = []
        fields = set(['state', 'quorum', 'calibration', 'priority_0',
                      'n_answers', 'user_pref', 'expiration'])
        field_header_index = []
        row_number = 0
        for row in csvreader:
            if not headers:
                headers = self._headers = row
                self._check_no_duplicated_headers(headers)
                self._check_no_empty_headers(headers)
                self._check_required_headers(headers)
                field_headers = set(headers) & fields
                for field in field_headers:
                    field_header_index.append(headers.index(field))
            else:
                row_number += 1
                self._check_valid_row_length(row, row_number, headers)

                # check required fields
                fvals = {headers[idx]: cell for idx, cell in enumerate(row)}
                invalid_fields = validate_required_fields(fvals)
                if invalid_fields:
                    msg = gettext('The file you uploaded has incorrect/missing '
                                  'values for required header(s): {0}'
                                  .format(','.join(invalid_fields)))
                    raise BulkImportException(msg)

                task_data = {"info": {}}
                for idx, cell in enumerate(row):
                    if idx in field_header_index:
                        if headers[idx] == 'user_pref':
                            if len(cell) > 0:
                                task_data[headers[idx]] = json.loads(cell.lower())
                            else:
                                task_data[headers[idx]] = {}
                        else:
                            task_data[headers[idx]] = cell
                    elif headers[idx].endswith('_gold'):
                        if cell:
                            if 'gold_answers' not in task_data:
                                task_data['gold_answers'] = {}
                            field_name = re.sub('_gold$', '', headers[idx])
                            task_data['gold_answers'][field_name] = cell
                    else:
                        task_data["info"][headers[idx]] = cell
                if 'gold_answers' in task_data:
                    task_data['calibration'] = 1
                yield task_data

    def _check_no_duplicated_headers(self, headers):
        if len(headers) != len(set(headers)):
            msg = gettext('The file you uploaded has '
                          'two headers with the same name.')
            raise BulkImportException(msg)

    def _check_no_empty_headers(self, headers):
        stripped_headers = [header.strip() for header in headers]
        if "" in stripped_headers:
            position = stripped_headers.index("")
            msg = gettext("The file you uploaded has an empty header on "
                          "column %(pos)s.", pos=(position+1))
            raise BulkImportException(msg)

    def _check_valid_row_length(self, row, row_number, headers):
        if len(headers) != len(row):
            msg = gettext("The file you uploaded has an extra value on "
                          "row %s." % (row_number+1))
            raise BulkImportException(msg)

    def _check_required_headers(self, headers):
        required_headers = app.config.get("TASK_REQUIRED_FIELDS", {})
        missing_headers = [r for r in required_headers if r not in headers]
        if missing_headers:
            msg = gettext('The file you uploaded has missing '
                          'required header(s): {0}'.format(','.join(missing_headers)))
            raise BulkImportException(msg)

    def _get_csv_data_from_request(self, r):
        """Get CSV data from a request."""
        if r.status_code == 403:
            msg = ("Oops! It looks like you don't have permission to access"
                   " that file")
            raise BulkImportException(gettext(msg), 'error')
        if (('text/plain' not in r.headers['content-type']) and
                ('text/csv' not in r.headers['content-type'])):
            msg = gettext("Oops! That file doesn't look like the right file.")
            raise BulkImportException(msg, 'error')

        r.encoding = 'utf-8'
        csvcontent = StringIO(r.text)
        csvreader = unicode_csv_reader(csvcontent)
        return self._import_csv_tasks(csvreader)

class BulkTaskGDImport(BulkTaskCSVImport):

    """Class to import tasks from Google Drive in bulk."""

    importer_id = "gdocs"

    def __init__(self, googledocs_url):
        self.url = googledocs_url

    def _get_data_url(self, **form_data):
        """Get data from URL."""
        # For old data links of Google Spreadsheets
        if 'ccc?key' in self.url:
            return ''.join([self.url, '&output=csv'])
        # New data format for Google Drive import is like this:
        # https://docs.google.com/spreadsheets/d/key/edit?usp=sharing
        else:
            return ''.join([self.url.split('edit')[0],
                            'export?format=csv'])


class BulkTaskLocalCSVImport(BulkTaskCSVImport):

    """Class to import CSV tasks in bulk from local file."""

    importer_id = "localCSV"

    def __init__(self, **form_data):
       self.form_data = form_data

    def _get_data(self):
        """Get data."""
        return self.form_data['csv_filename']

    def count_tasks(self):
        return len([task for task in self.tasks()])

    def _get_csv_data_from_request(self, csv_filename):
        if csv_filename is None:
            msg = ("Not a valid csv file for import")
            raise BulkImportException(gettext(msg), 'error')

        datafile = get_import_csv_file(csv_filename)
        csv_file = FileStorage(io.open(datafile.name, encoding='utf-8-sig'))    #utf-8-sig to ignore BOM

        if csv_file is None or csv_file.stream is None:
            msg = ("Unable to load csv file for import, file {0}".format(csv_filename))
            raise BulkImportException(gettext(msg), 'error')

        csv_file.stream.seek(0)
        csvcontent = io.StringIO(csv_file.stream.read())
        csvreader = unicode_csv_reader(csvcontent)
        return list(self._import_csv_tasks(csvreader))

    def tasks(self):
        """Get tasks from a given URL."""
        csv_filename = self._get_data()
        return self._get_csv_data_from_request(csv_filename)

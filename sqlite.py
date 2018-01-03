import hashlib
import json
import os
import traceback
import urllib
import webbrowser

import launchy
import sqlite3

import subprocess

import sys
import time


# prefix to prepend to the json in the full path for disambiguation
PRE_TAG = ""

DEBUG_OUTPUT = False
DO_TIMING = False


def read_json(filename):
    with open(filename, "r") as handle:
        return json.load(handle)


def sqlite_escape(s):
    assert "\x00" not in s
    return '"%s"' % s.replace('"', '""')


def url_hash(s):
    m = hashlib.sha256()
    m.update(s)
    return m.hexdigest()[:16]


def ext_of_url(url):
    final = url.rsplit("/", 1)[-1]
    if "." in final:
        ext_part = final.rsplit(".", 1)[-1]
        return "." + ext_part.split("?", 1)[0]
    return ""


class LaunchySQLite(launchy.Plugin):
    def __init__(self):
        super(LaunchySQLite, self).__init__()
        self.name = "SQLite"
        self.hash = launchy.hash(self.name)
        self.icon = os.path.join(launchy.getIconsPath(), "pysimple.png")

        script_path = launchy.getScriptsPath()
        config_filename = os.path.join(script_path, "sqlite_config.json")

        self.config = read_json(config_filename)
        self.database_filename = self.config["database"]

        self.conn = None

    def init(self):
        self.conn = sqlite3.connect(self.database_filename)

    # noinspection PyPep8Naming
    def getID(self):
        return self.hash

    # noinspection PyPep8Naming
    def getName(self):
        return self.name

    # noinspection PyPep8Naming
    def getIcon(self):
        return self.icon

    # noinspection PyPep8Naming
    def getLabels(self, inputDataList):
        pass

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    # noinspection PyPep8Naming
    # noinspection PyPep8Naming
    @staticmethod
    def download(url, filename):
        original_ext = ext_of_url(url)
        do_convert = original_ext != ".png"
        if do_convert:
            download_filename = filename.rsplit(".", 1)[0] + original_ext
        else:
            download_filename = filename

        input_handle = urllib.urlopen(url)
        try:
            with open(download_filename, "wb") as output_handle:
                while True:
                    block = input_handle.read(65536)
                    if len(block) == 0:
                        break
                    output_handle.write(block)
        finally:
            input_handle.close()

        def iv_quote(fn):
            return '%s' % fn.replace("/", "\\")

        if do_convert:
            wd = os.path.dirname(download_filename)
            download_filename_proper = os.path.basename(download_filename)
            assert os.path.dirname(filename) == wd
            filename_proper = os.path.basename(filename)
            assert os.path
            if sys.platform == "win32":
                pf = os.environ["ProgramFiles(x86)"]
                args = [os.path.join(pf, r"IrfanView\i_view32.exe"), iv_quote(download_filename_proper), "/convert=" + iv_quote(filename_proper)]
            else:
                assert False, "not implemented"
            print repr(args)
            subprocess.check_call(args, cwd=wd)

    @classmethod
    def has_valid_action(cls, field_def):
        if type(field_def) == list:
            return any(cls.has_valid_action(x) for x in field_def)
        if "action_url_pattern" in field_def:
            return True
        return False

    @staticmethod
    def do_action(field_def, field_value):
        if "action_url_pattern" in field_def:
            action_url_pattern = field_def["action_url_pattern"]
            if action_url_pattern == "%s":
                # For the special case where the action pattern is just the URL,
                # don't escape it; the database value will have to be a valid URL
                url = field_value
            else:
                url = action_url_pattern.replace("%s", urllib.quote(field_value))
            webbrowser.open(url)

    @staticmethod
    def get_action_name(field_def, output_column_name):
        if field_def is None:
            return None
        action_name = field_def.get("action_name")
        if action_name is None:
            action_name = "Open %s" % output_column_name
        return action_name

    @staticmethod
    def action_name_match(text_part, action_name):
        return action_name is not None and text_part.lower() in action_name.lower()

    @staticmethod
    def field_defs_entry_proper(field_defs_entry):
        if field_defs_entry is not None and type(field_defs_entry) != list:
            return [field_defs_entry]
        return field_defs_entry

    # noinspection PyPep8Naming
    def getResults(self, inputDataList, resultsList):
        # Take the text from the first input item and add a new
        # Catalog item with our plugin id

        # print len(inputDataList)
        inputData = inputDataList[0]

        first_result = True

        all_text = inputData.getText()

        all_text_parts = all_text.split(" ")

        if DO_TIMING:
            start_time = time.time()

        # print inputDataList

        for table_entry in self.config["tables"]:
            # go through the tables to use from this sqlite database according to the config
            table_name = table_entry["name"]
            display_name_field = table_entry.get("display_name_field")
            search_fields = table_entry["search_fields"]

            # 1. build the list of fields we want for this table
            output_fields = []

            # the fields definitions for this table from our config file
            field_defs = table_entry["fields"]

            for field_name, field_def in field_defs.iteritems():
                if self.has_valid_action(field_def):
                    output_fields.append(field_name)
                else:
                    print "field %s has no valid action; skipping" % field_name

            icon_url_field = table_entry.get("icon_url_field")
            if icon_url_field and icon_url_field not in output_fields:
                output_fields.append(icon_url_field)
            if display_name_field and display_name_field not in output_fields:
                output_fields.append(display_name_field)

            # What we want
            # - the rows where all the words are in any of the fields
            # - for any combination of the words that are in an action, the rows where all the other words are in any of the fields
            #   (we will show just certain actions for these)
            #
            # For a simple first cut of this, let's just narrow the actions to any word that is part of an action
            # rather than doing the full union.

            # 2. figure out what action names the search terms match and what other actions to exclude

            action_names = []
            action_entries = []

            for output_column_name in output_fields:
                field_defs_entry = self.field_defs_entry_proper(field_defs.get(output_column_name))
                if field_defs_entry is None:
                    continue
                for field_def_num, field_def in enumerate(field_defs_entry):
                    action_name = self.get_action_name(field_def, output_column_name)
                    action_names.append(action_name)
                    action_entries.append((output_column_name, field_def_num, action_name))

            exclude_output_fields = set()

            text_parts = []
            for text_part in all_text_parts:
                if any(self.action_name_match(text_part, action_name) for action_name in action_names):
                    # text is in any action name; treat as a search for those specific actions

                    # we only want actions that have all of these action words
                    for output_field, field_def_num, action_name in action_entries:
                        if action_name is None:
                            continue
                        if not self.action_name_match(text_part, action_name):
                            key = (output_field, field_def_num)
                            if key not in exclude_output_fields:
                                exclude_output_fields.add(key)
                else:
                    # text is not in any action name; treat as ordinary search text
                    text_parts.append(text_part)

            if DEBUG_OUTPUT:
                print ""
                print "QUERY %r" % all_text_parts
                print "exclude output fields %r" % exclude_output_fields
                print "text parts %r" % text_parts

            # 3. build database query to do for this table to match on those fields

            output_clause = ", ".join(sqlite_escape(x) for x in output_fields)
            if len(text_parts) == 0:
                search_clause = "1"
            else:
                search_clause = " OR ".join("%s LIKE ?" % sqlite_escape(x) for x in search_fields)
                search_clause = " AND ".join(["(" + search_clause + ")"] * len(text_parts))

            query = "SELECT %s FROM %s WHERE %s" % (output_clause, sqlite_escape(table_name), search_clause)

            args = []
            for text_part in text_parts:
                args += ["%" + text_part.replace("%", "%%") + "%"] * len(search_fields)

            if DEBUG_OUTPUT:
                print query

            # print "running query: " + query
            # print "with args: " + repr(args)

            # 4. Use the database query results to create the action items, respecting the action filters

            c = self.conn.cursor()
            assert isinstance(c, sqlite3.Cursor)
            try:
                try:
                    c.execute(query, args)
                except sqlite3.OperationalError:
                    print "failing query was %r args %r" % (query, args)
                    raise
                result_rows = c.fetchall()
                if DEBUG_OUTPUT:
                    print "got %d rows" % len(result_rows)
                for result_row in result_rows:

                    column_pairs = zip(output_fields, result_row)
                    column_dict = dict(column_pairs)

                    icon = self.getIcon()
                    # noinspection PyBroadException
                    try:
                        if icon_url_field:
                            icon_url = column_dict[icon_url_field]
                            if icon_url:
                                assert isinstance(icon_url, basestring)
                                icon_filename = os.path.join(launchy.getIconsPath(), url_hash(icon_url) + ".png")
                                if not os.path.exists(icon_filename):
                                    self.download(icon_url, icon_filename)
                                icon = icon_filename
                    except Exception:
                        print "error getting icon"
                        traceback.print_exc()
                    # print "icon is " + icon

                    for output_column_name, output_value in column_pairs:
                        if not output_value:
                            continue

                        field_defs_entry = self.field_defs_entry_proper(field_defs.get(output_column_name))
                        if field_defs_entry is None:
                            continue

                        for field_def_number, field_def in enumerate(field_defs_entry):
                            if (output_column_name, field_def_number) in exclude_output_fields:
                                continue

                            if not self.has_valid_action(field_def):
                                continue

                            action_name = self.get_action_name(field_def, output_column_name)

                            action = {"table": table_name, "field": output_column_name, "value": output_value, "field_def_number": field_def_number}
                            action_json = json.dumps(action)

                            if display_name_field and column_dict[display_name_field]:
                                entry_display_text = "%s: %s (%s)" % (column_dict[display_name_field], action_name, output_value)
                            else:
                                entry_display_text = "%s: %s" % (output_value,  action_name)

                            if DEBUG_OUTPUT:
                                print "ENTRY: " + entry_display_text

                            cat_item = launchy.CatItem(PRE_TAG + action_json,
                                                       entry_display_text,
                                                       self.getID(), icon)

                            resultsList.push_back(cat_item)
                            if first_result:
                                first_result = False
                                inputData.setTopResult(cat_item)

            finally:
                c.close()

        if DO_TIMING:
            end_time = time.time()

            # noinspection PyUnboundLocalVariable
            print "elapsed time %0.0f ms" % ((end_time - start_time) * 1000)

    # noinspection PyPep8Naming
    def getCatalog(self, resultsList):
        pass

    # noinspection PyPep8Naming
    def launchItem(self, inputDataList, catItemOrig):
        # The user chose our catalog item, print it
        cat_item = inputDataList[-1].getTopResult()
        full_path = cat_item.fullPath
        print "I was asked to launch: ", full_path

        assert full_path.startswith(PRE_TAG)
        full_path = full_path[len(PRE_TAG):]

        action = json.loads(full_path)

        field_name = action["field"]
        field_value = action["value"]
        field_def_number = action["field_def_number"]

        for table_entry in self.config["tables"]:
            table_name = table_entry["name"]
            if table_name == action["table"]:
                field_defs = table_entry["fields"]
                field_defs_entry = self.field_defs_entry_proper(field_defs[field_name])
                field_def = field_defs_entry[field_def_number]
                self.do_action(field_def, field_value)
                break
        else:
            assert False


launchy.registerPlugin(LaunchySQLite)

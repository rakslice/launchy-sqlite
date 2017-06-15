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
        self.friendly_name = self.config["friendly_name"]

        self.conn = None

    def init(self):
        self.conn = sqlite3.connect(self.database_filename)

    def getID(self):
        return self.hash

    def getName(self):
        return self.name

    def getIcon(self):
        return self.icon

    def getLabels(self, inputDataList):
        pass

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

    @staticmethod
    def has_valid_action(field_def):
        if "action_url_pattern" in field_def:
            return True
        return False

    @staticmethod
    def do_action(field_def, field_value):
        if "action_url_pattern" in field_def:
            url = field_def["action_url_pattern"].replace("%s", urllib.quote(field_value))
            webbrowser.open(url)

    def getResults(self, inputDataList, resultsList):
        # Take the text from the first input item and add a new
        # Catalog item with our plugin id

        # print len(inputDataList)
        text = inputDataList[0].getText()

        # print inputDataList

        for table_entry in self.config["tables"]:
            table_name = table_entry["name"]
            search_fields = table_entry["search_fields"]
            output_fields = []
            field_defs = table_entry["fields"]
            for field_name, field_def in field_defs.iteritems():
                if self.has_valid_action(field_def):
                    output_fields.append(field_name)
                else:
                    print "field %s has no valid action; skipping" % field_name

            icon_url_field = table_entry.get("icon_url_field")
            if icon_url_field:
                output_fields.append(icon_url_field)

            output_clause = ", ".join(sqlite_escape(x) for x in output_fields)
            search_clause = " OR ".join("%s LIKE ?" % sqlite_escape(x) for x in search_fields)
            query = "SELECT %s FROM %s WHERE %s" % (output_clause, sqlite_escape(table_name), search_clause)
            args = ["%" + text.replace("%", "%%") + "%"] * len(search_fields)

            # print "running query: " + query
            # print "with args: " + repr(args)

            c = self.conn.cursor()
            assert isinstance(c, sqlite3.Cursor)
            try:
                c.execute(query, args)
                result_rows = c.fetchall()
                # print "got %d rows" % len(result_rows)
                for result_row in result_rows:

                    icon = self.getIcon()
                    # noinspection PyBroadException
                    try:
                        if icon_url_field:
                            icon_url = result_row[-1]
                            if icon_url:
                                assert isinstance(icon_url, basestring)
                                icon_filename = os.path.join(launchy.getIconsPath(), url_hash(icon_url) + ".png")
                                if not os.path.exists(icon_filename):
                                    self.download(icon_url, icon_filename)
                                icon = icon_filename
                    except Exception:
                        print "error getting icon"
                        traceback.print_exc()
                    print "icon is " + icon

                    for output_column_name, output_value in zip(output_fields, result_row):

                        if not output_value:
                            continue

                        field_def = field_defs.get(output_column_name)
                        if field_def is None:
                            continue

                        if not self.has_valid_action(field_def):
                            continue

                        action_name = field_def.get("action_name")
                        if action_name is None:
                            action_name = "Open %s" % output_column_name

                        action = {"table": table_name, "field": output_column_name, "value": output_value}
                        action_json = json.dumps(action)

                        resultsList.push_back(launchy.CatItem(action_json,
                                                              str(output_value) + ": " + action_name,
                                                              self.getID(), icon))
            finally:
                c.close()

    def getCatalog(self, resultsList):
        pass

    def launchItem(self, inputDataList, catItemOrig):
        # The user chose our catalog item, print it
        catItem = inputDataList[-1].getTopResult()
        print "I was asked to launch: ", catItem.fullPath
        action = json.loads(catItem.fullPath)

        field_name = action["field"]
        field_value = action["value"]

        for table_entry in self.config["tables"]:
            table_name = table_entry["name"]
            if table_name == action["table"]:
                field_defs = table_entry["fields"]
                field_def = field_defs[field_name]
                self.do_action(field_def, field_value)
                break
        else:
            assert False




launchy.registerPlugin(LaunchySQLite)

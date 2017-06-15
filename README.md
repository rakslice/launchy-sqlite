# launchy-sqlite
a Launchy plugin to search records from an SQLite database

# To install

- You'll need to download and install:
  - [Python 2.7](https://www.python.org/downloads/)
  - [Launchy 2.5+](https://www.launchy.net/download.php#windows)
  - [PyLaunchy](https://sourceforge.net/projects/pylaunchy/files/pylaunchy/0.9.0/)
  - [IrfanView](http://www.irfanview.com/) for image conversions, if you want to use non-PNG icon URLs
  
- Put `sqlite.py` in your `Launchy\plugins\python` directory
- Copy the supplied `sqlite_config.example.json` to `Launchy\plugins\python\sqlite_config.json` and modify it as needed (see below).

# Configuration settings

`sqlite_config.json` is a JSON configuration file that tells launchy-sqlite what to do.  

Top level:

- `database`: the filename of the SQLite database to use. Remember that backslashes (`\`) need to be escaped in JSON strings
- `tables`: a list with a section for each database table to show (array of table objects)

Table:

- `name`: name of the table in the sqlite database
- `display_name_field`: a field to use as a display name for the record in the Launchy search result (optional)
- `search_fields`: a list of text fields to search for the text typed into Launchy
- `icon_url_field`: a field with a URL to an icon to display for Launchy search results for this record (optional)
- `fields`: a list of fields with associated actions that individual search results should be shown for (array of field objects).

Field:

- `action_name`: A display name for the action associated with this field
- `action_url_pattern`: A URL to open if this search result is selected; this can contain a `%s` placeholder to be filled in with the value from this field in the database row
  
# Development

- Pylaunchy docs
  - [Simple Plugin Tutorial](http://pylaunchy.sourceforge.net/docs/simple_plugin.html)


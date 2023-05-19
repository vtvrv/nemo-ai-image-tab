#!/usr/bin/python
# coding: utf-8

import locale, gettext, os, re

try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Nemo', '3.0')
from gi.repository import GObject, Gtk, Nemo
from PIL import Image

GUI = """
<interface>
  <requires lib="gtk+" version="3.0"/>
  <object class="GtkScrolledWindow" id="mainWindow">
    <property name="visible">True</property>
    <property name="can_focus">True</property>
    <property name="hscrollbar_policy">never</property>
    <child>
      <object class="GtkViewport" id="viewport1">
        <property name="visible">True</property>
        <property name="can_focus">False</property>
        <child>
          <object class="GtkGrid" id="grid">
            <property name="visible">True</property>
            <property name="can_focus">False</property>
            <property name="vexpand">True</property>
            <property name="row_spacing">4</property>
            <property name="column_spacing">16</property>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>"""


class AIinfoPropertyPage(GObject.GObject, Nemo.PropertyPageProvider, Nemo.NameAndDescProvider):

    def get_property_pages(self, files):
        # files: list of NemoVFSFile
        if len(files) != 1:
            return

        file = files[0]
        if file.get_uri_scheme() != 'file':
            return

        if file.is_directory():
            return

        filename = unquote(file.get_uri()[7:])

        try:
            filename = filename.decode("utf-8")
        except:
            pass

        if not os.path.isfile(filename):
            return

        img = Image.open(filename)

        extension = os.path.splitext(filename)[-1].lower()
        if extension == '.png':
            parameters = img.info['parameters']
        elif extension in [".jpg", ".jpeg", ".webp"]:
            parameters = img._getexif()[37510] #37510 is ExifID for "UserComment" https://exiftool.org/TagNames/EXIF.html
            parameters = parameters.replace(b'\x00', b'').decode("utf-8")
            if parameters.startswith("UNICODE"):
                parameters = parameters[7:]
        else:
            return

        info = {}

        parameters = parameters.replace('\\n', '\n') #Helping improperly embedded prompts

        if parameters.count('\n'): #If has prompt
            prompt_str, setting_str = parameters.rsplit('\n', 1)
            prompt_regex = re.match("^(.*?)\n(?:Negative prompt: )?(.*?)$",
                                    prompt_str+'\n',
                                    flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
            info["Prompt"], info["Negative prompt"] = prompt_regex.groups()
        else: #If only settings
            setting_str = parameters

        settings_regex = re.findall("(.*?): (.*?), ", setting_str + ", ")
        info = info | dict(settings_regex)

        locale.setlocale(locale.LC_ALL, '')
        gettext.bindtextdomain("nemo-extensions")
        gettext.textdomain("nemo-extensions")
        _ = gettext.gettext

        self.property_label = Gtk.Label(_('AI Metadata'))
        self.property_label.show()

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain('nemo-extensions')
        self.builder.add_from_string(GUI)

        self.mainWindow = self.builder.get_object("mainWindow")
        self.grid = self.builder.get_object("grid")

        for i, (key,val) in enumerate(info.items()):
            if val:
                label = Gtk.Label()
                label.set_markup("<b>" + key + ":</b>")
                label.set_justify(Gtk.Justification.LEFT)
                label.set_halign(Gtk.Align.START)
                label.show()
                self.grid.attach(label, 0, i, 1, 1)
                label = Gtk.Label()
                label.set_text(info[key])
                label.set_justify(Gtk.Justification.LEFT)
                label.set_halign(Gtk.Align.START)
                label.set_selectable(True)
                label.set_line_wrap(True)
                label.set_line_wrap_mode(1)  # PANGO_WRAP_WORD_CHAR
                # label.set_max_width_chars(160)
                label.show()
                self.grid.attach(label, 1, i, 1, 1)

        return Nemo.PropertyPage(name="NemoPython::AIinfo", label=self.property_label, page=self.mainWindow),

    def get_name_and_desc(self):
        return [("Nemo AIMeta Info Tab:::View AI image metadata from the properties tab")]


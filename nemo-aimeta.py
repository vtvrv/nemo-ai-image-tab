#!/usr/bin/python
# coding: utf-8

import locale, gettext, os

try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

import gi
gi.require_versions({'Gtk': '3.0', 'Nemo': '3.0'})
from gi.repository import GObject, Gtk, Nemo

from PIL import Image

SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"] #ensure all lowercase

def getinfo(filename):
    img = Image.open(filename)
    extension = os.path.splitext(filename)[-1].lower()
    if extension == '.png':
        parameters = img.info['parameters']
    elif extension in [".jpg", ".jpeg", ".webp"]:
        parameters = img._getexif()[37510]  # 37510 is ExifID for "UserComment" https://exiftool.org/TagNames/EXIF.html
        parameters = parameters.replace(b'\x00', b'').decode("utf-8")
        if parameters.startswith("UNICODE"):
            parameters = parameters[7:]
    else:
        return {}

    parameters = parameters.replace('\\n', '\n')  # Help with improperly embedded prompts
    lines = parameters.rsplit('\n', 1)

    #Assume last line lines[-1] is string of settings
    #lines[-1] looks like this "Step: 4, Model: sd1.5, CFG scale: 5"
    info = {k: v for k, v in (x.split(": ") for x in lines[-1].split(", "))}

    if len(lines) > 1:  # contains positive or negative prompts
        prompts = [x.rstrip('\n') for x in lines[0].split("Negative prompt: ", 1)]  # [positive, negative]
        info['Prompt'] = prompts[0]
        if len(prompts) > 1:
            info['Negative prompt'] = prompts[1]

    return info

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

        if os.path.splitext(filename)[-1].lower() not in SUPPORTED_EXTENSIONS:
            return

        info = getinfo(filename)
        if not info:
            return

        locale.setlocale(locale.LC_ALL, '')
        gettext.bindtextdomain("nemo-extensions")
        gettext.textdomain("nemo-extensions")
        _ = gettext.gettext

        self.property_label = Gtk.Label(('AI Metadata'))
        self.property_label.show()

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain('nemo-extensions')
        self.builder.add_from_string(GUI)

        self.mainWindow = self.builder.get_object("mainWindow")
        self.grid = self.builder.get_object("grid")

        for i, (key,val) in enumerate(info.items()):
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


#!/usr/bin/python
# coding: utf-8

import locale, gettext, os, sys, traceback, json
from PIL import Image
import piexif, piexif.helper

try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

import gi
gi.require_versions({'Gtk': '3.0', 'Nemo': '3.0'})
from gi.repository import GObject, Gtk, Nemo

SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"] #ensure all lowercase


#Patch
#https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/sd_samplers_kdiffusion.py
class sd_samplers():
    samplers_k_diffusion = [
        ('Euler a', 'sample_euler_ancestral', ['k_euler_a', 'k_euler_ancestral'], {}),
        ('Euler', 'sample_euler', ['k_euler'], {}),
        ('LMS', 'sample_lms', ['k_lms'], {}),
        ('Heun', 'sample_heun', ['k_heun'], {}),
        ('DPM2', 'sample_dpm_2', ['k_dpm_2'], {'discard_next_to_last_sigma': True}),
        ('DPM2 a', 'sample_dpm_2_ancestral', ['k_dpm_2_a'], {'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a', 'sample_dpmpp_2s_ancestral', ['k_dpmpp_2s_a'], {}),
        ('DPM++ 2M', 'sample_dpmpp_2m', ['k_dpmpp_2m'], {}),
        ('DPM++ SDE', 'sample_dpmpp_sde', ['k_dpmpp_sde'], {}),
        ('DPM fast', 'sample_dpm_fast', ['k_dpm_fast'], {}),
        ('DPM adaptive', 'sample_dpm_adaptive', ['k_dpm_ad'], {}),
        ('LMS Karras', 'sample_lms', ['k_lms_ka'], {'scheduler': 'karras'}),
        ('DPM2 Karras', 'sample_dpm_2', ['k_dpm_2_ka'], {'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM2 a Karras', 'sample_dpm_2_ancestral', ['k_dpm_2_a_ka'],
         {'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a Karras', 'sample_dpmpp_2s_ancestral', ['k_dpmpp_2s_a_ka'], {'scheduler': 'karras'}),
        ('DPM++ 2M Karras', 'sample_dpmpp_2m', ['k_dpmpp_2m_ka'], {'scheduler': 'karras'}),
        ('DPM++ SDE Karras', 'sample_dpmpp_sde', ['k_dpmpp_sde_ka'], {'scheduler': 'karras'}),
    ]

    all_samplers = [
        #*sd_samplers_compvis.samplers_data_compvis,
        *samplers_k_diffusion
    ]

    samplers_map = {}
    for sampler in all_samplers:
        for i in sampler[2]:
            samplers_map[i] = sampler[0]

#https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/images.py
def read_info_from_image(image):
    items = image.info or {}

    geninfo = items.pop('parameters', None)

    if "exif" in items:
        exif = piexif.load(items["exif"])
        exif_comment = (exif or {}).get("Exif", {}).get(piexif.ExifIFD.UserComment, b'')
        try:
            exif_comment = piexif.helper.UserComment.load(exif_comment)
        except ValueError:
            exif_comment = exif_comment.decode('utf8', errors="ignore")

        if exif_comment:
            items['exif comment'] = exif_comment
            geninfo = exif_comment

        for field in ['jfif', 'jfif_version', 'jfif_unit', 'jfif_density', 'dpi', 'exif',
                      'loop', 'background', 'timestamp', 'duration']:
            items.pop(field, None)

    if items.get("Software", None) == "NovelAI":
        try:
            json_info = json.loads(items["Comment"])
            sampler = sd_samplers.samplers_map.get(json_info["sampler"], "Euler a")

            geninfo = f"""{items["Description"]}
Negative prompt: {json_info["uc"]}
Steps: {json_info["steps"]}, Sampler: {sampler}, CFG scale: {json_info["scale"]}, Seed: {json_info["seed"]}, Size: {image.width}x{image.height}, Clip skip: 2, ENSD: 31337"""
        except Exception:
            print("Error parsing NovelAI image generation parameters:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    return geninfo, items

def parse_geninfo(info):
    info = info.replace('\\n', '\n') #Help with improperly embedded prompts
    lines = info.rsplit('\n', 1)

    setting_str = lines[-1]  # Assume last line is settings
    result = {k: v for k, v in (x.split(": ") for x in setting_str.split(", "))}

    if len(lines) > 1:  # contains positive or negative prompts
        prompts = [x.rstrip('\n') for x in lines[0].split("Negative prompt: ", 1)]
        result["Prompt"] = prompts[0]
        if len(prompts) > 1:
            result["Negative prompt"] = prompts[1]

    return result


def getinfo(filename):
    img = Image.open(filename)
    geninfo, _ = read_info_from_image(img)
    return parse_geninfo(geninfo)

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


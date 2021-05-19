#!/usr/bin/env python3
# coding: utf-8

import argparse
from pydub import AudioSegment
import sys
from PIL import Image
import audioop
from math import ceil, sqrt
import os
from appdirs import *
import pathlib
import json
import time
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from copy import copy
import re


class Utils:

    def image_description(im):
        return {"i_width": im.width, "i_mode": im.mode, "i_size": len(im.tobytes())}

    def audio_description(au):
        return {"a_bitrate": au.frame_rate, "a_channels": au.channels, "a_size": len(au.raw_data)}

    def description(obj):
        if isinstance(obj, Image.Image):
            return Utils.image_description(obj)
        else:
            return Utils.audio_description(obj)

    def conversion_method(args):
        if args.conversion_inverse_a_law:
            return "inverse a-law"
        elif args.conversion_a_law:
            return "a-law"
        elif args.conversion_inverse_u_law:
            return "inverse u-law"
        elif args.conversion_u_law:
            return "u-law"
        else:
            return "linear"



class Parameters:
    # A class to manage parameters

    def create_parser():
        parser = argparse.ArgumentParser(description="Audio/image converter using a raw approach. If no output options are given, the previous runs (history) are used to guess the possible parameters such as image size or bitrate.")

        group_command_line = parser.add_argument_group("Non interactive mode", "Use command line parameters to run conversion without graphical interface")
        group_command_line.add_argument("-i", "--input", help="Input file", type=argparse.FileType('r'))
        group_command_line.add_argument("-o", "--output", help="Requested longitude", type=argparse.FileType('w'))
        group_command_line.add_argument("--ignore-history", help="Ignore history and avoid parameter guessing", action="store_true")

        group_conversion = group_command_line.add_mutually_exclusive_group(required=False)
        group_conversion.add_argument("--conversion-linear", help="Use a linear 8-bits conversion", action="store_true")
        group_conversion.add_argument("--conversion-u-law", help="Use the u-law algorithm within an 8-bits conversion", action="store_true")
        group_conversion.add_argument("--conversion-a-law", help="Use the a-law algorithm within an 8-bits conversion", action="store_true")
        group_conversion.add_argument("--conversion-inverse-u-law", help="Use the inverse u-law algorithm within an 8-bits conversion", action="store_true")
        group_conversion.add_argument("--conversion-inverse-a-law", help="Use the inverse a-law algorithm within an 8-bits conversion", action="store_true")

        group_extra_bytes = group_command_line.add_mutually_exclusive_group(required=False)
        group_extra_bytes.add_argument("-t", "--truncate", help="Truncate data rather than adding empty elements", action="store_true")
        group_extra_bytes.add_argument("-a", "--add-extra-bytes", help="Add empty elements to fill the structure when bytes are missing", action="store_true")

        group_img2aud = parser.add_argument_group("Image to audio options", "Adjust the image to audio conversion")
        group_img2aud.add_argument("--bitrate", help="Bitrate (44.1 kHz or 48 kHz)", choices=[44100, 48000], default=None)
        group_channels = group_img2aud.add_mutually_exclusive_group(required=False)
        group_channels.add_argument("--mono", help="Generate a mono file. Default: stereo", action="store_true")
        group_channels.add_argument("--stereo", help="Generate a stereo file. Default: stereo", action="store_true")

        group_aud2img = parser.add_argument_group("Audio to image options", "Adjust the audio to image conversion")
        group_size = group_aud2img.add_mutually_exclusive_group(required=False)
        group_size.add_argument("-r", "--ratio", help="Ratio", type=float, default=None)
        group_size.add_argument("-w", "--width", help="Number of pixels (width)", type=int, default=None)

        group_pixels = group_aud2img.add_mutually_exclusive_group(required=False)
        group_pixels.add_argument("--rgb", help="Generate RGB image. Default: RGB", action="store_true")
        group_pixels.add_argument("--greyscale", help="Generate greyscale image. Default: RGB", action="store_true")
        group_pixels.add_argument("--rgba", help="Generate RGBA image. Default: RGB", action="store_true")

        parser.add_argument("-v", "--verbose", help="Verbose messages", action="store_true")

        return parser

    def has_image_size_parameter(args):
        return args.width != None or args.ratio != None

    def has_image_mode_parameter(args):
        return args.rgb or args.rgba or args.greyscale

    def has_audio_channel_parameter(args):
        return args.mono or args.stereo

    def has_extra_bytes_method(args):
        return args.truncate or args.add_extra_bytes

    def has_conversion_method(args):
        return args.conversion_a_law or args.conversion_inverse_a_law or args.conversion_u_law or args.conversion_inverse_u_law or args.conversion_linear



class History:
    # A class that uses previous runs to guess target properties.
    # 
    # Without spectific option, the script is using history to adjust the properties of the output. 
    # For example, in the following sequence, the first run produces a stereo 44.1 kHz audio file 
    # (default format), and store in the history the specific properties of the input image 
    # (width, height, RGB/RGBA). The second run uses the history to identify the correct image
    # parameters, using the properties of the audio file (number of samples, number of channels 
    # and sample rate)  as a filtering to identify the possible configuration of the audio file
    # ancestor.
    # 
    # ```rawdodendron.py -i image.png -o audio.wav``` to convert an image to an audio file
    # ```rawdodendron.py -i audio.wav -o image.png``` to convert an audio file to an image
    history_dir = user_data_dir("rawdodendron")
    history_file = pathlib.Path(history_dir).joinpath("history.json")

    def __init__(self):
        self.create_history_dir()    


    def create_history_dir(self):
        try:
            os.makedirs(self.history_dir)
        except:
            pass


    def load_history(self):
        try:
            json_file = open(self.history_file)
            data = json.load(json_file)
            return data
        except:
            return {}

    def store_history(self, history):
        with open(self.history_file, 'w') as outfile:
            json.dump(history, outfile)


    def description_matches(full, subpart):
        for key in subpart:
            if subpart[key] != full[key]:
                return False
        return True

    def get_params_from_history(self, size, desc, from_image):
        history = self.load_history()
        str_size = str(size)
        if str_size in history:
            possible = [h for h in history[str_size] if h["from_image"] != from_image and History.description_matches(h, desc)]
            if len(possible) == 0:
                return None
            # get the most recent
            print("Found a probable output configuration from history")
            sorted_possible = sorted(possible, key=lambda k: k["timestamp"], reverse=True) 
            return sorted_possible[0]
        else:
            return None

    def store_params_to_history(self, data):
        # add current timestamp
        data["timestamp"] = time.time()

        # get history
        history = self.load_history()
        # create history at first call
        if history == None:
            history = {}
        
        # index by size of the output
        size = str(data["a_size"] if data["from_image"] else data["i_size"])

        # create an entry if first time we meet this size
        if not size in history:
            history[size] = []
        history[size].append(data)

        self.store_history(history)


    def consolidate_extra_bytes_method(args, data):
        if not Parameters.has_extra_bytes_method(args):
            if data == None or args.ignore_history:
                args.add_extra_bytes = True
            else:
                args.truncate = (data["from_image"] and data["i_size"] >= data["a_size"]) or ((not data["from_image"]) and data["i_size"] <= data["a_size"])
                args.add_extra_bytes = not args.truncate
    
    def consolidate_conversion_method(args, data):
        if not Parameters.has_conversion_method(args):
            if data == None or args.ignore_history:
                args.conversion_linear = True
                args.conversion_u_law = False
                args.conversion_inverse_u_law = False
                args.conversion_a_law = False
                args.conversion_inverse_a_law = False
            else:
                # inverse previous conversion
                args.conversion_linear = data["conversion_method"] == "linear"
                args.conversion_u_law = data["conversion_method"] == "inverse u-law"
                args.conversion_inverse_u_law = data["conversion_method"] == "u-law"
                args.conversion_a_law = data["conversion_method"] == "inverse a-law"
                args.conversion_inverse_a_law = data["conversion_method"] == "a-law"

    def consolidate_parameters_from_image(self, args, im):
        # consolidate args

        data = self.get_params_from_history(len(im.tobytes()), Utils.image_description(im), True)

        if data != None and not args.ignore_history:
            # try to consolidate using history
            if args.bitrate == None and "a_bitrate" in data:
                args.bitrate = data["a_bitrate"]
            if not Parameters.has_audio_channel_parameter(args) and "a_channels" in data:
                args.mono = data["a_channels"] == 1
                args.stereo = data["a_channels"] == 2
        
        # set default values
        if not Parameters.has_audio_channel_parameter(args):
            args.stereo = True
        if args.bitrate == None:
            args.bitrate = 44100
        
        History.consolidate_extra_bytes_method(args, data)
        History.consolidate_conversion_method(args, data)


    def consolidate_parameters_from_audio(self, args, au):
        # consolidate args
        data = self.get_params_from_history(len(au.raw_data), Utils.audio_description(au), False)
        if data != None and not args.ignore_history:
            # try to consolidate using history
            if not Parameters.has_image_size_parameter(args) and "i_width" in data:
                args.width = data["i_width"]
            if not Parameters.has_image_mode_parameter(args) and "i_mode" in data:
                args.rgb = data["i_mode"] == "RGB"
                args.rgba = data["i_mode"] == "RGBA"
                args.greyscale = data["i_mode"] == "L"

        # set default values
        if not Parameters.has_image_size_parameter(args):
            args.ratio = 3/2 # default ratio value
        if not Parameters.has_image_mode_parameter(args):
            args.rgb = True

        History.consolidate_extra_bytes_method(args, data)
        History.consolidate_conversion_method(args, data)

    def store_parameters(self, au, im, from_image, conversion_method):
        # store configuration
        new_data = {"from_image": from_image, "conversion_method": conversion_method }
        new_data.update(Utils.image_description(im))
        new_data.update(Utils.audio_description(au))
        self.store_params_to_history(new_data)


class Rawdodendron:

    # main class that convert an image to an audio file, or an audio file to an image
    def load_input_file(filename, verbose):
        try:
            # try to load the input as an audio file
            au = AudioSegment.from_file(filename)

            if verbose:
                print("Audio properties: ", "channels:", au.channels, ", sample_width:", au.sample_width, ", frame_rate", au.frame_rate, ", duration:", au.duration_seconds, "s")

            return au
        except: 
            # if the file is not an audio file, try to load it as an image
            im = Image.open(filename)
            if verbose:
                print("Image size:", str(im.width) + "px",  "*", str(im.height) + "px", ", mode:", im.mode)

            return im


    def convert(args):
        print("Input file: ", args.input.name)
        print("Output file: ", args.output.name)

        try:
            input_file = Rawdodendron.load_input_file(args.input.name, args.verbose)
        except TypeError as err:
            print("\nError while reading image:", err, "\n")
            parser.print_help()
            
            if verbose:
                print("\nError: ", sys.exc_info()[0])
            
            exit(1)
        except Exception as err:
            print("\nError: unknown input format", err, "\n")
            parser.print_help()
            
            if verbose:
                print("\nError: ", sys.exc_info()[0])            
            exit(1)

        if input_file == None:
            exit(2)
        elif isinstance(input_file, Image.Image):
            try:
                # try to convert the image file as an audio file
                Rawdodendron.save_as_audio(input_file, args)
            except Exception as e:
                print("\nError while writing audio file:", e, "\n")
                exit(2)
            except:
                print("\nError while writing audio file, unknown error\n")
                exit(2)
            input_file.close()

        elif isinstance(input_file, AudioSegment):
            try:
                # try to convert the audio file as an image
                Rawdodendron.save_as_image(input_file, args)
                
            except Exception as e:
                print("\nError while writing image file", e, "\n")
                exit(2)
            except:
                print("\nError while writing image file, unknown error\n")
                exit(2)

        else:
            exit(1)


    def save_as_audio(im, args):

        # consolidate parameters using history
        history = History()
        history.consolidate_parameters_from_image(args, im)

        # get data
        data = im.tobytes()
        # get information about the output (number of channels)
        channels =  1 if args.mono else 2

        if args.verbose:
            print("")
            
        # apply a byte-to-byte conversion if required
        data = Rawdodendron.apply_conversion(data, args)
    
        # handle extra bytes (truncate or add missing data)
        if len(data) % (channels) != 0:
            if args.truncate:
                if args.verbose:
                    print("Truncate data")
                data = data[:-1]
            else:
                if args.verbose:
                    print("Add missing bytes at the end of binary data")
                data = data + b"\x00"

        # create the audio structure
        au = AudioSegment(
            # raw audio data (bytes)
            data = data,

            # 1 byte (8 bit) samples
            sample_width = 1,

            # 44.1 kHz or 48 kHz frame rate
            frame_rate = args.bitrate,

            # mono or stereo
            channels = channels
        )

        if args.verbose:
            print("Export data: " + args.output.name)

        # try to guess format using extension
        filename, file_extension = os.path.splitext(args.output.name)
        format = file_extension.lower()[1:]
        if format == "wave":
            format = "wav"

        # save file
        file_handle = au.export(args.output.name, format=format)

        # store input and output properties in the history
        history.store_parameters(au, im, True, Utils.conversion_method(args))

    # get the image size from the parameters
    def get_image_size(data, args):
        # it depends on the number of bytes per pixel
        channels = 1 if args.greyscale else 4 if args.rgba else 3

        # if a size is given, we use it
        if args.width != None:
            width = args.width

            height = len(data) / width / channels
            height = ceil(height)
        else:
            # otherwise we use the given ratio
            nb_pixels = ceil(len(data) / channels)
            # args.ratio = width / height
            # nb_pixels = width * height (if no pixel is missing)
            # thus
            width = ceil(sqrt(nb_pixels * args.ratio))
            height = ceil(width / args.ratio)

        # estimate the number of missing pixels
        missing = width * height * channels - len(data)

        # if truncate is required, update the information
        if missing > 0 and args.truncate:
            missing = missing - width * channels
            height = height - 1

        # return the computed image size, and the number of missing pixels (can be negative if the data has to be truncated)
        return width, height, missing


    def apply_conversion(data, args):
        if args.conversion_u_law:
            if args.verbose:
                print("Conversion using u-law")
            data = audioop.lin2ulaw(data, 1)
        elif args.conversion_a_law:
            if args.verbose:
                print("Conversion using a-law")
            data = audioop.lin2alaw(data, 1)
        elif args.conversion_inverse_u_law:
            if args.verbose:
                print("Conversion using inverse u-law")
            data = audioop.ulaw2lin(data, 1)
        elif args.conversion_inverse_a_law:
            if args.verbose:
                print("Conversion using inverse a-law")
            data = audioop.alaw2lin(data, 1)
        return data

    def save_as_image(au, args):

        # convert to 8-bits
        au = au.set_sample_width(1)

        # load history
        history = History()
        history.consolidate_parameters_from_audio(args, au)

        # get data from the audio
        data = au.raw_data

        if args.verbose:
            print("")

        # apply a byte-to-byte conversion if required
        data = Rawdodendron.apply_conversion(data, args)

        # compute image size
        width, height, missing = Rawdodendron.get_image_size(data, args)

        # add missing pixels with an 00 value
        if missing > 0:
            if args.verbose:
                print("Add missing bytes at the end of binary data")
            data = data + b"\x00" * missing
        # if required, truncate data
        elif missing < 0:
            if args.verbose:
                print("Truncate data")
            data = data[:missing]

        # compute the target mode (greyscae, RGB, RGBA)
        mode = "L" if args.greyscale else "RGBA" if args.rgba else "RGB"
        if args.verbose:
            print("Mode: " + mode)

        # create the image
        im = Image.frombytes(mode, (width, height), data, "raw", mode, 0, 1)

        if args.verbose:
            print("Export data: " + args.output.name)

        try:
            # try to save the image
            im.save(args.output.name)
            # finaly, store the configuration in the history logs
            history.store_parameters(au, im, False, Utils.conversion_method(args))
        except Exception as err:
            # if an exception occured, the selected format may not support alpha channels (e.g. jpg)
            if mode == "RGBA":
                # we try to convert the image in RGB format
                if args.verbose:
                    print("Force RGB mode")
                im = im.convert("RGB")

                # and try to save again the image
                im.save(args.output.name)

                # finaly, store the configuration in the history logs
                history.store_parameters(au, im, False, Utils.conversion_method(args))
            else:
                print("\nError:", err, "\n")
                exit(2)


class RawWindow(QMainWindow):

    history = History()
        
    class Input:
        counter = 0

        class OutputDescription:
            def __init__(self, input_name, extension):
                path = pathlib.Path(input_name)
                parent = str(path.parent)
                stem = str(path.stem)
                m = re.search('(.*) \(([0-9]+?)\)$', stem)
                if m:
                    found = m.group(2)
                    i = int(found)
                    stem = m.group(1)
                    self.name = parent + "/" + stem + " (" + str(i) + ")" + extension
                else:
                    self.name = parent + "/" + stem + extension
                    i = 0
                while os.path.exists(self.name):
                    i += 1
                    self.name = parent + "/" + stem + " (" + str(i) + ")" + extension

        def __init__(self, filename, args):
            self.filename = filename
            self.args = copy(args)

            self.id = RawWindow.Input.counter
            RawWindow.Input.counter += 1

            self.load_input_file()

        def get_missing_bytes_method(self):
            if self.args.truncate:
                return "truncate"
            else:
                return "add-extra-bytes"

        def set_missing_bytes_method(self, method):
            self.args.truncate = method == "truncate"
            self.args.add_extra_bytes = method == "add-extra-bytes"
        
        def get_conversion_method(self):
            return Utils.conversion_method(self.args)

        def set_conversion_method(self, method):
            self.args.conversion_linear = method == "linear"
            self.args.conversion_u_law = method == "inverse u-law"
            self.args.conversion_inverse_u_law = method == "u-law"
            self.args.conversion_a_law = method == "inverse a-law"
            self.args.conversion_inverse_a_law = method == "a-law"

        def get_bitrate(self):
            return self.args.bitrate

        def set_bitrate(self, br):
            self.args.bitrate = br

        def get_channels(self):
            if self.args.mono:
                return "mono"
            else:
                return "stereo"

        def set_channels(self, channels):
            self.args.mono = channels == "mono"
            self.args.stereo = channels == "stereo"

        def get_ratio_size(self):
            return self.args.ratio

        def set_ratio_value(self, value):
            self.args.ratio = float(value)
            self.update_size()

        def get_width_size(self):
            return self.args.width

        def set_width_value(self, value):
            self.args.width = int(value)
            self.update_size()

        def get_size_mode(self):
            if self.args.width:
                return "width"
            else:
                return "ratio"
        
        def set_size_mode(self, mode):            
            self.args.ratio = self.width / self.height if mode == "ratio" else None
            self.args.width = self.width if mode == "width" else None

        def get_pixel_mode(self):
            if self.args.greyscale:
                return "greyscale"
            elif self.args.rgba:
                return "rgba"
            else:
                return "rgb"
        
        def set_pixel_mode(self, mode):
            self.args.grayscale = mode == "greyscale"
            self.args.rgb = "rgb"
            self.args.rgba = "rgba"

        # reload the input file and identify if it changed or not
        def file_properties_changed(self):
            new_input_file = Rawdodendron.load_input_file(self.filename, self.args.verbose)
            self.update_size()
            desc = Utils.description(self.input_file)
            new_desc = Utils.description(new_input_file)
            if desc == new_desc:
                self.input_file = new_input_file
                return False
            else:
                return True

        def get_data(self):
            if self.is_image:
                return self.input_file.tobytes()
            else:
                return self.input_file.raw_data

        def update_size(self):
            if self.is_image:
                self.width = None
                self.heigh = None
                self.missing = None
                self.final_size = len(self.input_file.tobytes())
                if self.final_size % (2 if self.get_channels() == "stero" else 1) != 0:
                    if self.args.truncate:
                        self.final_size -= 1
                    else:
                        self.final_size += 1
            else:
                self.width, self.height, self.missing = Rawdodendron.get_image_size(self.get_data(), self.args)
                self.final_size = len(self.input_file.raw_data) + self.missing

        def load_input_file(self):
            self.is_valid = False
            try:
                self.input_file = Rawdodendron.load_input_file(self.filename, self.args.verbose)
                self.is_valid = self.input_file != None

                if self.is_valid:
                    if isinstance(self.input_file, Image.Image):
                        if self.args.verbose:
                            print("Loading image:", self.filename)
                        self.is_image = True
                        RawWindow.history.consolidate_parameters_from_image(self.args, self.input_file)
                        self.update_size()
                        # set output name
                        self.computeNextPossibleOutputName()
                    elif isinstance(self.input_file, AudioSegment):
                        if self.args.verbose:
                            print("Loading audio:", self.filename)
                        self.is_image = False
                        RawWindow.history.consolidate_parameters_from_audio(self.args, self.input_file)
                        self.update_size()
                        # set output name
                        self.computeNextPossibleOutputName()
                        
            except:
                self.is_valid = False

        def computeNextPossibleOutputName(self):
            if self.args.output != None:
                filename = self.args.output.name
                extension = pathlib.Path(self.args.output.name).suffix
            elif self.is_image:
                filename = self.filename
                extension = ".wav"
            else:
                filename = self.filename
                extension = ".png"
            self.args.output = RawWindow.Input.OutputDescription(filename, extension)


        def getFileName(self):
            return os.path.basename(self.filename)

        def set_output_file(self, filename):
            self.args.output.name = filename

        def inverse(self):
            self.filename = self.args.output.name
            self.args.output = None
            self.load_input_file()

        def get_size_info(self):
            if self.is_image:
                return self.final_size / self.args.bitrate
            else:
                return (self.width, self.height)
                

            
        

    class InputWidget(QWidget):
        def __init__(self, input, listWidget, rawWindow, parent = None):
            super(QWidget, self).__init__(parent)
            self.input = input

            self.hbox = QHBoxLayout()
            self.setLayout(self.hbox)

            # add icon
            self.image_size = 32
            self.icon = QLabel()
            self.icon.setFixedWidth(self.image_size)
            self.hbox.addWidget(self.icon)

            # add filename
            self.label = QLabel()
            self.hbox.addWidget(self.label)

            self.delButton = QPushButton()
            self.delButton.setText("Supprimer")
            self.delButton.setFixedSize(self.delButton.sizeHint())
            self.delButton.clicked.connect(lambda x: listWidget.on_delete_input(input, x))
            self.hbox.addWidget(self.delButton)

            self.update()
    
        def update(self):
            if self.input.is_image:
                self.icon.setPixmap(QIcon.fromTheme("image").pixmap(self.image_size))
            else:
                self.icon.setPixmap(QIcon.fromTheme("audio").pixmap(self.image_size))
            self.label.setText(self.input.getFileName())



    class InputListWidget(QWidget):
        def __init__(self, rawWindow, parent = None):
            super(QWidget, self).__init__(parent)
            
            self.rawWindow = rawWindow
            
            self.vbox = QVBoxLayout()
            self.setLayout(self.vbox)

            # create header with buttons
            self.header = QWidget()
            self.vbox.addWidget(self.header)
            self.hbox = QHBoxLayout()
            self.header.setLayout(self.hbox)

            # add button
            self.addButton = QPushButton()
            self.addButton.setText("Ajouter un fichier")
            self.addButton.setIcon(QIcon.fromTheme("document-open"))
            self.hbox.addWidget(self.addButton)
            self.addButton.clicked.connect(rawWindow.on_add_input)

            # clear button
            self.clearButton = QPushButton()
            self.clearButton.setText("Vider la liste")
            self.clearButton.setIcon(QIcon.fromTheme("delete"))
            self.clearButton.clicked.connect(self.on_delete_all)
            self.hbox.addWidget(self.clearButton)

            # create list
            self.list = QListWidget()
            self.list.currentItemChanged.connect(lambda x: rawWindow.on_active_input(self.list.currentItem().input if self.list.currentItem() != None else None, x))
            self.vbox.addWidget(self.list)

        def addInput(self, input):
            widget = RawWindow.InputWidget(input, self, self.rawWindow)
            list_item = QListWidgetItem(self.list)
            list_item.input = input
            list_item.widget = widget
            widget.adjustSize()
            list_item.setSizeHint(widget.sizeHint())
            self.list.setItemWidget(list_item, widget)
            widget.setFocus()
            self.rawWindow.setNbElements(self.list.count())

        def updateWidgets(self):
            for r in range(self.list.count()):
                row = self.list.item(r).widget.update()


        @pyqtSlot()
        def on_delete_all(self):
            self.list.clear()
            self.list.setFocus()
            self.rawWindow.setNbElements(self.list.count())
            self.rawWindow.showMessage("Liste vidée")

        @pyqtSlot()
        def on_delete_input(self, input, e):
            for r in range(self.list.count()):
                row = self.list.item(r)
                if row.input.id == input.id:
                    self.rawWindow.showMessage("Fichier " + input.filename + " retiré de la liste des entrées")
                    self.list.takeItem(r)
                    self.list.setFocus()
                    break
            self.rawWindow.setNbElements(self.list.count())

        def getInputs(self):
            return [self.list.item(r).input for r in range(self.list.count())]
        
        def setFocus(self):
            self.list.setFocus()

    class EditPanel(QWidget):    
        def __init__(self, parent = None):
            super(QWidget, self).__init__(parent)
            self.current = None
            self.vbox = QVBoxLayout()
            self.setLayout(self.vbox)

            self.noContentPanel = QLabel()
            self.noContentPanel.setText("Aucun fichier sélectionné")
            self.vbox.addWidget(self.noContentPanel)

            # create the common panel
            self.commonPanel = QGroupBox("Propriétés principales")
            gridCommonPanel = QGridLayout()
            self.commonPanel.setLayout(gridCommonPanel)
            self.vbox.addWidget(self.commonPanel)

            title = QLabel()
            title.setText("Entrée:")
            gridCommonPanel.addWidget(title, 0, 0)
            self.inputFilename = QLineEdit()
            self.inputFilename.setReadOnly(True)
            gridCommonPanel.addWidget(self.inputFilename, 0, 1, 1, 6)
            
            title = QLabel()
            title.setText("Sortie:")
            gridCommonPanel.addWidget(title, 1, 0)
            self.outputFilename = QLineEdit()
            self.outputFilename.editingFinished.connect(self.onUpdateOutputFile)
            gridCommonPanel.addWidget(self.outputFilename, 1, 1, 1, 5)
            self.outputExplorer = QPushButton()
            self.outputExplorer.setText("Sélectionner...")
            self.outputExplorer.clicked.connect(self.onOutputExplorerClicked)
            gridCommonPanel.addWidget(self.outputExplorer, 1, 6)

            title = QLabel()
            title.setText("Conversion:")
            gridCommonPanel.addWidget(title, 2, 0)
            self.conversion = QComboBox()
            self.conversion_values = [ ("linear", "linéaire"),
                                        ("u-law", "u-law"),
                                        ("inverse u-law", "u-law inverse"),
                                        ("a-law", "a-law"),
                                        ("inverse a-law", "a-law inverse")
                                        ]
            for i in self.conversion_values:
                self.conversion.addItem(i[1])
            self.conversion.currentIndexChanged.connect(self.onUpdateConversion)
            gridCommonPanel.addWidget(self.conversion, 2, 1, 1, 4)
            self.conversionToAll = QPushButton()
            self.conversionToAll.setText("Copier à tous")
            gridCommonPanel.addWidget(self.conversionToAll, 2, 5, 1, 2)

            title = QLabel()
            title.setText("Données incomplètes:")
            gridCommonPanel.addWidget(title, 3, 0)
            self.missingBytes = QComboBox()
            self.missingBytes_values = [ ("truncate", "tronquer"),
                                         ("add-extra-bytes", "compléter")]
            for i in self.missingBytes_values:
                self.missingBytes.addItem(i[1])
            self.missingBytes.currentIndexChanged.connect(self.onUpdateMissingBytes)
            gridCommonPanel.addWidget(self.missingBytes, 3, 1, 1, 4)
            self.missingBytesToAll = QPushButton()
            self.missingBytesToAll.setText("Copier à tous")
            gridCommonPanel.addWidget(self.missingBytesToAll, 3, 5, 1, 2)


            # create the image panel
            self.imagePanel = QGroupBox("Propriétés de l'image cible")
            gridImagePanel = QGridLayout()
            self.imagePanel.setLayout(gridImagePanel)
            self.vbox.addWidget(self.imagePanel)


            title = QLabel()
            title.setText("Mode:")
            gridImagePanel.addWidget(title, 0, 0)
            self.mode = QComboBox()
            self.mode_values = [ ("greyscale", "Dégradé de gris"),
                                ("rgba", "couleur + transparence (RGB)"),
                                ("rgb", "couleur (RGB)")]
            for i in self.mode_values:
                self.mode.addItem(i[1])
            self.mode.currentIndexChanged.connect(self.onUpdateMode)
            gridImagePanel.addWidget(self.mode, 0, 1, 1, 4)
            self.modeToAll = QPushButton()
            self.modeToAll.setText("Copier à tous")
            gridImagePanel.addWidget(self.modeToAll, 0, 5, 1, 2)

            title = QLabel()
            title.setText("Taille:")
            gridImagePanel.addWidget(title, 1, 0)
            self.sizeMode = QComboBox()
            self.sizeMode_values = [ ("ratio", "ratio"),
                                        ("width", "largeur")]
            for i in self.sizeMode_values:
                self.sizeMode.addItem(i[1])
            self.sizeMode.currentIndexChanged.connect(self.onUpdateSizeMode)
            gridImagePanel.addWidget(self.sizeMode, 1, 1, 1, 2)
            self.sizeValue = QLineEdit()
            self.sizeValue.editingFinished.connect(self.onUpdateSizeValue)
            gridImagePanel.addWidget(self.sizeValue, 1, 3, 1, 2)
            self.sizeModeToAll = QPushButton()
            self.sizeModeToAll.setText("Copier à tous")
            gridImagePanel.addWidget(self.sizeModeToAll, 1, 5, 1, 2)

            # create the audio panel
            self.audioPanel = QGroupBox("Propriétés de l'audio cible")
            gridAudioPanel = QGridLayout()
            self.audioPanel.setLayout(gridAudioPanel)
            self.vbox.addWidget(self.audioPanel)

            title = QLabel()
            title.setText("Échantillonage:")
            gridAudioPanel.addWidget(title, 0, 0)
            self.bitrate = QComboBox()
            self.bitrate_values = [ (44100, "44.1 kHz"),
                                    (48000, "48 kHz")]
            for i in self.bitrate_values:
                self.bitrate.addItem(i[1])
            self.bitrate.currentIndexChanged.connect(self.onUpdateBitrate)
            gridAudioPanel.addWidget(self.bitrate, 0, 1, 1, 4)
            self.bitrateToAll = QPushButton()
            self.bitrateToAll.setText("Copier à tous")
            gridAudioPanel.addWidget(self.bitrateToAll, 0, 5, 1, 2)

            title = QLabel()
            title.setText("Canaux:")
            gridAudioPanel.addWidget(title, 1, 0)
            self.channels = QComboBox()
            self.channels_values = [ ("mono", "Mono"),
                                    ("stereo", "Stéréo")]
            for i in self.channels_values:
                self.channels.addItem(i[1])
            self.channels.currentIndexChanged.connect(self.onUpdateChannels)
            gridAudioPanel.addWidget(self.channels, 1, 1, 1, 4)
            self.channelsToAll = QPushButton()
            self.channelsToAll.setText("Copier à tous")
            gridAudioPanel.addWidget(self.channelsToAll, 1, 5, 1, 2)

            self.detailsText = QLabel()
            self.vbox.addWidget(self.detailsText)

            # TODO: connect widgets to update self.input and all other inputs

            self.setCurrent(None)

        def setCurrent(self, input):
            self.current = input
            self.noContentPanel.setVisible(input == None)
            self.commonPanel.setVisible(input != None)
            self.imagePanel.setVisible(input != None and not input.is_image)
            self.audioPanel.setVisible(input != None and input.is_image)
            
            
            # update widget contents
            self.updateUI()

        def getIndexFromList(self, value, l):
            for i in range(len(l)):
                if l[i][0] == value:
                    return i
            print("Error: no corresponding entry:", value, l)
            return 0

        def fullUpdateUI(self):
            self.setCurrent(self.current)

        def updateUI(self):
            if self.current != None:
                self.inputFilename.setText(self.current.filename)
                self.outputFilename.setText(self.current.args.output.name)
                self.missingBytes.setCurrentIndex(self.getIndexFromList(self.current.get_missing_bytes_method(), self.missingBytes_values))
                self.conversion.setCurrentIndex(self.getIndexFromList(self.current.get_conversion_method(), self.conversion_values))

                if self.current.is_image:
                    self.bitrate.setCurrentIndex(self.getIndexFromList(self.current.get_bitrate(), self.bitrate_values))
                    self.channels.setCurrentIndex(self.getIndexFromList(self.current.get_channels(), self.channels_values))
                else:
                    self.mode.setCurrentIndex(self.getIndexFromList(self.current.get_pixel_mode(), self.mode_values))
                    self.sizeMode.setCurrentIndex(self.getIndexFromList(self.current.get_size_mode(), self.sizeMode_values))
                    self.update_sizeMode()
            self.set_detailsText()

        def update_sizeMode(self):
            if self.current.get_size_mode() == "width":
                self.sizeValue.setText(str(self.current.get_width_size()))
                self.sizeValue.setValidator(QIntValidator(1, 100000, self))

            else:
                self.sizeValue.setText(str(self.current.get_ratio_size()))
                self.sizeValue.setValidator(QDoubleValidator(0, 100, 0, self))

        def set_detailsText(self):
            if self.current != None:
                sizes = self.current.get_size_info()
                if self.current.is_image:
                    if sizes > 60 * 3:
                        self.detailsText.setText("Un fichier audio de {:.1f} minutes sera généré".format(sizes / 60))
                    elif sizes > 60:
                        self.detailsText.setText("Un fichier audio de {:.0f} secondes sera généré".format(sizes))
                    else:
                        self.detailsText.setText("Un fichier audio de {:.1f} secondes sera généré".format(sizes))
                else:
                    self.detailsText.setText("Une image de " + str(sizes[0]) + " par " + str(sizes[1]) + " pixels sera générée")
            else:
                self.detailsText.setText("")

        @pyqtSlot()
        def onOutputExplorerClicked(self):
            options = QFileDialog.Options()
            if self.current.is_image:
                filename, _ = QFileDialog.getSaveFileName(self,"Convertir l'image en audio", self.outputFilename.text(),
                            "Sons (*.wav *.ogg *.mp3 *.flac);; Tous les fichiers (*.*)", options=options)
                if filename != "":
                    self.outputFilename.setText(filename)
            else:
                filename, _ = QFileDialog.getSaveFileName(self,"Convertir l'image en audio", self.outputFilename.text(),
                            "Images (*.png *.jpg *.bmp);; Tous les fichiers (*.*)", options=options)
                if filename != "":
                    self.outputFilename.setText(filename)
            
        @pyqtSlot()
        def onUpdateOutputFile(self):
            self.current.set_output_file(self.outputFilename.text())
        
        @pyqtSlot()
        def onUpdateMissingBytes(self):
            self.current.set_missing_bytes_method(self.missingBytes_values[self.missingBytes.currentIndex()][0])
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateConversion(self):
            self.current.set_conversion_method(self.conversion_values[self.conversion.currentIndex()][0])
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateBitrate(self):
            self.current.set_bitrate(self.bitrate_values[self.bitrate.currentIndex()][0])
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateChannels(self):
            self.current.set_channels(self.channels_values[self.channels.currentIndex()][0])
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateMode(self):
            self.current.set_pixel_mode(self.mode_values[self.mode.currentIndex()][0])
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateSizeMode(self):
            self.current.set_size_mode(self.sizeMode_values[self.sizeMode.currentIndex()][0])
            self.update_sizeMode()
            self.set_detailsText()

        @pyqtSlot()
        def onUpdateSizeValue(self):
            if self.current.get_size_mode() == "width":
                self.current.set_width_value(self.sizeValue.text())
            else:
                self.current.set_ratio_value(self.sizeValue.text())
            self.set_detailsText()

    def __init__(self, args, parent = None):
        super(RawWindow, self).__init__(parent)
        self.setAcceptDrops(True)
        self.resize(600, 800)
        self.setWindowTitle("Rawdodendron")

        self.args = args

        bar = self.menuBar()
        file = bar.addMenu("Fichier")
        file.addAction("Ouvrir...").setShortcut(QKeySequence("Ctrl+O"))
        file.addAction("Quitter").setShortcut(QKeySequence("Ctrl+Q"))
        file.triggered[QAction].connect(self.processtrigger)

        # create the main widget and its layout
        self.main_widget = QWidget()
        self.vbox = QVBoxLayout()
        self.main_widget.setLayout(self.vbox)
        self.setCentralWidget(self.main_widget)

        # add a splitter
        self.splitter = QSplitter(Qt.Vertical)
        self.vbox.addWidget(self.splitter)

        # create file list and add it to the splitter
        self.inputs_widget = RawWindow.InputListWidget(self)
        self.splitter.addWidget(self.inputs_widget)

        # create the edit panel and add it tot the splitter
        self.edit_panel = RawWindow.EditPanel()
        self.splitter.addWidget(self.edit_panel)

        self.bottom_bar = QWidget()
        self.hbox = QHBoxLayout()
        self.bottom_bar.setLayout(self.hbox)
        self.vbox.addWidget(self.bottom_bar)

        # add a process button
        self.invertConversion = QRadioButton("Inverser après conversion")
        self.invertConversion.setToolTip("Après conversion, les fichiers de la liste sont remplacés par les fichiers qui ont été générés, pour permettre une conversion réciproque rapide.")
        self.invertConversion.setChecked(True)
        self.hbox.addWidget(self.invertConversion)

        self.processButton = QPushButton("Convertir tous les fichiers")
        self.hbox.addWidget(self.processButton)
        self.processButton.clicked.connect(self.process_inputs)

        self.progressBar = QProgressBar()
        self.hbox.addWidget(self.progressBar)
        self.progressBar.setVisible(False)

        self.setNbElements(0)

        self.inputs_widget.setFocus()

        self.error_dialog = QErrorMessage(self)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.nbElements = 0

        # if args.input is set, add the input file
        if args.input != None:
            self.addInputFile(args.input.name)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
        for f in files:
            self.addInputFile(f)

    def addInputFile(self, filename):
        input = RawWindow.Input(filename, args)
        if input.is_valid:
            print("Loading input file:", filename)
            self.inputs_widget.addInput(input)
            self.status_bar.showMessage(filename + " importé avec succès", 2000)
        else:
            print("Error while loading", filename)
            self.error_dialog.showMessage("Le fichier " + filename + " n'est pas lisible par Rawdodendron.")
            self.status_bar.showMessage(filename + ": format inconnu", 2000)

    
    @pyqtSlot()
    def process_inputs(self):
        inputs = self.inputs_widget.getInputs()

        # disable interface and draw a process bar
        self.processButton.setVisible(False)
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, len(inputs))
        self.progressBar.setValue(0)
        self.inputs_widget.setEnabled(False)
        self.edit_panel.setEnabled(False)
        self.invertConversion.setEnabled(False)
        
        error_dialog = QErrorMessage(self)

        for i, input in enumerate(inputs):
            self.progressBar.setValue(i + 1)
            args = copy(input.args)
            args.ignore_history = True
            if input.file_properties_changed():
                error_dialog.showMessage("Le fichier " + input.filename + " a changé de propriétés depuis son chargement, il sera ignoré")
                self.status_bar.showMessage("Le fichier " + input.filename + " a changé depuis son chargement", 2000)
            else:
                self.status_bar.showMessage("Export vers " + args.output.name, 2000)
                if input.is_image:
                    print("Convert", input.filename, "to", args.output.name)
                    Rawdodendron.save_as_audio(input.input_file, args)
                else:
                    print("Convert", input.filename, "to", args.output.name)
                    Rawdodendron.save_as_image(input.input_file, args)
                # if required, inverse the conversion list
                if self.invertConversion.isChecked():
                    input.inverse()
                # update output name in case of multiple runs
                input.computeNextPossibleOutputName()
        # set focus to the list after conversion
        self.inputs_widget.setFocus()
        # update list
        if self.invertConversion.isChecked():
            self.inputs_widget.updateWidgets()

        # update panel
        self.edit_panel.fullUpdateUI()

        # update interface
        self.inputs_widget.setEnabled(True)
        self.edit_panel.setEnabled(True)
        self.invertConversion.setEnabled(True)
        self.processButton.setVisible(True)
        self.progressBar.setVisible(False)
        self.status_bar.showMessage("Conversions réalisées avec succès", 2000)


    def setNbElements(self, nb = 0):
        self.nbElements = nb
        self.processButton.setEnabled(nb != 0)

    def showMessage(self, msg):
        self.status_bar.showMessage(msg, 2000)

    @pyqtSlot()
    def on_active_input(self, input, e):
        self.edit_panel.setCurrent(input)

    @pyqtSlot()
    def on_add_input(self):
        print("Opening files...")
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self,"Sélection d'images et fichiers son", "",
                            "Images (*.png *.jpg *.bmp);; Sons (*.wav *.ogg *.mp3 *.flac);; Tous les fichiers (*.*)", options=options)
        
        for f in files:
            self.addInputFile(f)

    def processtrigger(self, q):
	
        if (q.text() == "Ouvrir..."):
            self.on_add_input()
        if q.text() == "Quitter":
            if self.nbElements != 0:
                reply = QMessageBox.question(self, "Vraiment quitter?", "La liste n'est pas vide. Voulez-vous vraiment quitter?")
                if reply == QMessageBox.Yes:
                    sys.exit()
            else:
                sys.exit()
                

if __name__ == '__main__':
    
    # create parser
    parser = Parameters.create_parser()

    # load and validate parameters
    args = parser.parse_args()


    if args.input != None and args.output != None:
        # if input and output are provided, run the conversion
        Rawdodendron.convert(args)
    else:
        app = QApplication(sys.argv)
        ex = RawWindow(args=args)
        ex.show()
        sys.exit(app.exec_())



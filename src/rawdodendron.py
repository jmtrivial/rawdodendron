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

history_dir = user_data_dir("rawdodendron")
history_file = pathlib.Path(history_dir).joinpath("history.json")

def create_history_dir():
    try:
        os.makedirs(history_dir)
    except:
        pass

create_history_dir()    

def load_history():
    try:
        json_file = open(history_file)
        data = json.load(json_file)
        return data
    except:
        return None

def store_history(history):
    with open(history_file, 'w') as outfile:
        json.dump(history, outfile)


def has_image_size_parameter(args):
    return args.width != None or args.ratio != None

def has_image_mode_parameter(args):
    return args.rgb or args.rgba or args.greyscale

def has_audio_channel_parameter(args):
    return args.mono or args.stereo

def get_params_from_history(size, from_image):
    history = load_history()
    str_size = str(size)
    if str_size in history:
        possible = [h for h in history[str_size] if h["from_image"] != from_image]
        if len(possible) == 0:
            return None
        # get the most recent
        sorted_possible = sorted(possible, key=lambda k: k["timestamp"], reverse=True) 
        return sorted_possible[0]
    else:
        return None

def store_params_to_history(data):
    # add current timestamp
    data["timestamp"] = time.time()

    # get history
    history = load_history()
    # create history at first call
    if history == None:
        history = {}
    
    # index by size of the output
    size = str(data["a_size"] if data["from_image"] else data["i_size"])

    # create an entry if first time we meet this size
    if not size in history:
        history[size] = []
    history[size].append(data)

    store_history(history)

def has_extra_bytes_method(args):
    return args.truncate or args.add_extra_bytes


def  consolidate_extra_bytes_method(args, data):
    if not has_extra_bytes_method(args):
        if data == None:
            args.add_extra_bytes = True
        else:
            args.truncate = (data["from_image"] and data["i_size"] >= data["a_size"]) or ((not data["from_image"]) and data["i_size"] <= data["a_size"])
            args.add_extra_bytes = not args.truncate


def consolidate_parameters_from_image(args, im):
    # consolidate args
    data = get_params_from_history(len(im.tobytes()), True)
    print("consolidate data from image", data)
    if data != None:
        # try to consolidate using history
        if args.bitrate == None and "a_bitrate" in data:
            args.bitrate = data["a_bitrate"]
        if not has_audio_channel_parameter(args) and "a_channels" in data:
            args.mono = data["a_channels"] == 1
            args.stereo = data["a_channels"] == 2
    
    # set default values
    if not has_audio_channel_parameter(args):
        args.stereo = True
    if args.bitrate == None:
        args.bitrate = 44100
    
    consolidate_extra_bytes_method(args, data)


def consolidate_parameters_from_audio(args, f):
    # consolidate args
    data = get_params_from_history(len(f.raw_data), False)
    if data != None:
        # try to consolidate using history
        if not has_image_size_parameter(args) and "i_width" in data:
            args.width = data["i_width"]
        if not has_image_mode_parameter(args) and "i_mode" in data:
            args.rgb = data["i_mode"] == "RGB"
            args.rgba = data["i_mode"] == "RGBA"
            args.greyscale = data["i_mode"] == "L"

    # set default values
    if not has_image_size_parameter(args):
        args.ratio = 3/2 # default ratio value
    if not has_image_mode_parameter(args):
        args.rgb = True

    consolidate_extra_bytes_method(args, data)


def store_parameters(f, im, from_image):
    # store configuration
    new_data = {"a_bitrate": f.frame_rate, "a_channels": f.channels, "a_size": len(f.raw_data), "from_image": from_image,
                "i_width": im.width, "i_mode": im.mode, "i_size": len(im.tobytes())}
    store_params_to_history(new_data)

def save_as_audio(im, args):
    data = im.tobytes()

    consolidate_parameters_from_image(args, im)

    channels =  1 if args.mono else 2

    if args.verbose:
        print("")
        
    if args.conversion_u_law:
        if args.verbose:
            print("Conversion using u-law")
        data = audioop.lin2ulaw(data, 1)
    elif args.conversion_a_law:
        if args.verbose:
            print("Conversion using a-law")
        data = audioop.lin2alaw(data, 1)

    if len(data) % (channels) != 0:
        if args.truncate:
            if args.verbose:
                print("Truncate data")
            data = data[:-1]
        else:
            if args.verbose:
                print("Add missing bytes at the end of binary data")
            data = data + b"\x00"


    sound = AudioSegment(
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

    file_handle = sound.export(args.output.name, format=format)
    store_parameters(sound, im, True)


def get_image_size(data, args):

    channels = 1 if args.greyscale else 4 if args.rgba else 3

    if args.width != None:
        width = args.width

        height = len(data) / width / channels
        height = ceil(height)

    else:
        nb_pixels = ceil(len(data) / channels)
        # args.ratio = width / height
        # nb_pixels = width * height (if no pixel is missing)
        # thus
        width = ceil(sqrt(nb_pixels * args.ratio))
        height = ceil(width / args.ratio)

    missing = width * height * channels - len(data)

    if missing > 0 and args.truncate:
        missing = missing - width * channels
        height = height - 1

    return width, height, missing


def save_as_image(f, args):

    data = f.raw_data

    consolidate_parameters_from_audio(args, f)

    if args.verbose:
        print("")

    if args.conversion_u_law:
        if args.verbose:
            print("Conversion using u-law")
        data = audioop.ulaw2lin(data, 1)
    elif args.conversion_a_law:
        if args.verbose:
            print("Conversion using a-law")
        data = audioop.alaw2lin(data, 1)

    width, height, missing = get_image_size(data, args)

    if missing > 0:
        if args.verbose:
            print("Add missing bytes at the end of binary data")
        data = data + b"\x00" * missing
    elif missing < 0:
        if args.verbose:
            print("Truncate data")
        data = data[:missing]


    mode = "L" if args.greyscale else "RGBA" if args.rgba else "RGB"
    if args.verbose:
        print("Mode: " + mode)
    im = Image.frombytes(mode, (width, height), data, "raw", mode, 0, 1)

    if args.verbose:
        print("Export data: " + args.output.name)

    try:
        im.save(args.output.name)
        store_parameters(f, im, False)
    except Exception:
        if mode == "RGBA":
            if args.verbose:
                print("Force RGB mode")
            im = im.convert("RGB")
            im.save(args.output.name)
            store_parameters(f, im, False)



parser = argparse.ArgumentParser(description="Audio/image converter using a raw approach. If no output options are given, the previous runs (history) are used to guess the possible parameters such as image size or bitrate.")

group_command_line = parser.add_argument_group("Non interactive mode", "Use command line parameters to run conversion without graphical interface")
group_command_line.add_argument("-i", "--input", help="Input file", type=argparse.FileType('r'))
group_command_line.add_argument("-o", "--output", help="Requested longitude", type=argparse.FileType('w'))

group_conversion = group_command_line.add_mutually_exclusive_group(required=False)
group_conversion.add_argument("--conversion-basic", help="Use a basic 8-bits conversion", action="store_true")
group_conversion.add_argument("--conversion-u-law", help="Use the u-law algorithm within an 8-bits conversion", action="store_true")
group_conversion.add_argument("--conversion-a-law", help="Use the a-law algorithm within an 8-bits conversion", action="store_true")

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


# load and validate parameters
args = parser.parse_args()


if args.input != None and args.output != None:

    print("Input file: ", args.input.name)
    print("Output file: ", args.output.name)

    try:

        f = AudioSegment.from_file(args.input.name)

        if args.verbose:
            print("Audio properties: ", "channels:", f.channels, ", sample_width:", f.sample_width, ", frame_rate", f.frame_rate, ", duration:", f.duration_seconds, "s")

        try:        
            save_as_image(f, args)
        except Exception as e:
            print("")
            print("Error while writing image file", e)
            print("")
            exit(2)

    except: 

        try:
            im = Image.open(args.input.name)

            if args.verbose:
                print("Image size:", str(im.width) + "px",  "*", str(im.height) + "px", ", mode:", im.mode)

            try:
                save_as_audio(im, args)
            except Exception as e:
                print("")
                print("Error while writing audio file:", e)
                print("")
                exit(2)

            im.close()

        except TypeError as err:

            print("")
            print("Error while reading image")
            print("")
            
            parser.print_help()
            
            if args.verbose:
                print("")
                print("Error: ", err, sys.exc_info()[0])
            
            exit(1)
        except Exception as err:
            
            print("")
            print("Error: unknown input format")
            print("")
            
            parser.print_help()
            
            if args.verbose:
                print("")
                print("Error: ", err, sys.exc_info()[0])
            
            exit(1)


    pass
else:
    print ("Interactive mode not yet implemented.")



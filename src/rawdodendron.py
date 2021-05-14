#!/usr/bin/env python3
# coding: utf-8

import argparse
from pydub import AudioSegment
import sys
from PIL import Image
import audioop
from math import ceil, sqrt
import os


def save_as_audio(im, args):
    data = im.tobytes()

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
    except Exception:
        if mode == "RGBA":
            if args.verbose:
                print("Force RGB mode")
            im = im.convert("RGB")
            im.save(args.output.name)



parser = argparse.ArgumentParser(description="Audio/image converter using a raw approach.")

group_command_line = parser.add_argument_group("Non interactive mode", "Use command line parameters to run conversion without graphical interface")
group_command_line.add_argument("-i", "--input", help="Input file", type=argparse.FileType('r'))
group_command_line.add_argument("-o", "--output", help="Requested longitude", type=argparse.FileType('w'))

group_conversion = group_command_line.add_mutually_exclusive_group(required=False)
group_conversion.add_argument("--conversion-basic", help="Use a basic 8-bits conversion", action="store_true")
group_conversion.add_argument("--conversion-u-law", help="Use the u-law algorithm within an 8-bits conversion", action="store_true")
group_conversion.add_argument("--conversion-a-law", help="Use the a-law algorithm within an 8-bits conversion", action="store_true")

group_command_line.add_argument("-t", "--truncate", help="Truncate data rather than adding empty elements", action="store_true")

group_img2aud = parser.add_argument_group("Image to audio options", "Adjust the image to audio conversion")
group_img2aud.add_argument("--bitrate", help="Bitrate (44.1 kHz or 48 kHz)", choices=[44100, 48000], default=44100)
group_img2aud.add_argument("--mono", help="Generate a mono file. Default: stereo", action="store_true")

group_aud2img = parser.add_argument_group("Audio to image options", "Adjust the audio to image conversion")
group_size = group_aud2img.add_mutually_exclusive_group(required=False)
group_size.add_argument("-r", "--ratio", help="Ratio", type=float, default=3/2)
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



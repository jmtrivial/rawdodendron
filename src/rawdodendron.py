#!/usr/bin/env python3
# coding: utf-8

import argparse
from pydub import AudioSegment
import sys
from PIL import Image


def save_as_audio(im, args):
    # TODO
    pass


def save_as_image(f, args):
    # TODO
    pass


parser = argparse.ArgumentParser(description="Audio/image converter using a raw approach.")

group_command_line = parser.add_argument_group("Non interactive mode", "Use command line parameters to run conversion without graphical interface")
group_command_line.add_argument("-i", "--input", help="Input file", type=argparse.FileType('r'))
group_command_line.add_argument("-o", "--output", help="Requested longitude", type=argparse.FileType('w'))

group_img2aud = parser.add_argument_group("Image to audio options", "Adjust the image to audio conversion")
group_img2aud.add_argument("--bitrate", help="Bitrate", choices=[44100, 48000])


group_aud2img = parser.add_argument_group("Audio to image options", "Adjust the audio to image conversion")
group_format = group_aud2img.add_mutually_exclusive_group(required=False)
group_format.add_argument("-r", "--ratio", help="Ratio", type=float)
group_format.add_argument("-w", "--width", help="Number of pixels (width)", type=int)
group_aud2img.add_argument("--greyscale", help="Generate greyscale image. Default: RGB", action="store_true")

parser.add_argument("-v", "--verbose", help="Verbose messages", action="store_true")


# load and validate parameters
args = parser.parse_args()

if args.input != None or args.output != None:
    if args.input == None or args.output == None:
        print("Error: input and output should be both defined")
        print("")
        parser.print_help()
        exit(1)

    print("Input file: ", args.input.name)
    print("Output file: ", args.output.name)

    try:

        f = AudioSegment.from_file(args.input.name)

        if args.verbose:
            print("Audio properties: ", "channels:", f.channels, ", sample_width:", f.sample_width, ", frame_rate", f.frame_rate, ", duration:", f.duration_seconds, "s")

        try:        
            save_as_image(f, args)
        except:
            print("Error while writing image file")
            print("")
            exit(2)

    except: 

        try:
            im = Image.open(args.input.name)
            # im.getdata()
            if args.verbose:
                print("Image size:", str(im.width) + "px",  "*", str(im.height) + "px")

            try:
                save_as_audio(im, args)
            except:
                print("Error while writing audio file")
                print("")
                exit(2)

            im.close()

        except TypeError as err:

            print("Error while reading image")
            print("")
            
            parser.print_help()
            
            if args.verbose:
                print("")
                print("Error: ", err, sys.exc_info()[0])
            
            exit(1)
        except Exception as err:
            
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



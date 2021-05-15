# rawdodendron

<img src="./images/rhododendron.svg" width="200px" height="200px" alt="Rhododendron" align="right">


An audio/image converter using a raw approach

## Dependancies

* [pydub](http://pydub.com/)
* [pillow](https://pillow.readthedocs.io/en/stable/)
* [argparse](https://docs.python.org/3/library/argparse.html)
* [appdirs](https://pypi.org/project/appdirs/)

### Install dependancies on a debian system

```
sudo apt install python3-pydub python3-pil python3-appdirs
```

## Installation

- Download this repository
- run ```./install.sh```

## Examples

Some images generated from an RGBA png version of the initial *rhododendron* image, using the following process:

* convert the image to an audio file
* apply an audio processing algorithm (compression, reverb)
* convert back to an image

<img src="./samples/demo/rhododendron-compression.png" width="200px" height="200px" alt="Rhododendron (with compression)">

<img src="./samples/demo/rhododendron-reverb.png" width="200px" height="200px" alt="Rhododendron (with reverb)">

The last image is the result of a reverb, but from an RGB image (without alpha channel):

<img src="./samples/demo/rhododendron-reverb.jpg" width="200px" height="200px" alt="Rhododendron (with reverb)">

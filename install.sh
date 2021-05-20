#!/bin/sh


LOCAL_BIN=/usr/local/bin
if [ -d "$LOCAL_BIN" ]; then
    echo "Copy script to $LOCAL_BIN"
    sudo cp ./src/rawdodendron.py $LOCAL_BIN    
fi

if command -v apt &> /dev/null; then
    echo "Install dependancies (debian version)"
    sudo apt install python3-pydub python3-pil python3-appdirs python3-pyqt5
fi

if command -v kf5-config &> /dev/null; then
    dirs=`kf5-config --path services`
    export IFS=":"
    for dir in $dirs; do
        if [ -w "$dir" ]; then
            echo "Copy service menus to $dir"
            for i in desktop-menus/*; do
                cp $i "$dir"
            done
            break
        fi
    done
    
fi




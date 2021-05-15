#!/bin/sh


LOCAL_BIN=/usr/local/bin
if [ -d "$LOCAL_BIN" ]; then
    echo "Copy script to $LOCAL_BIN"
    sudo cp ./src/rawdodendron.py $LOCAL_BIN

    if ! command -v kf5-config &> /dev/null; then
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
    
fi



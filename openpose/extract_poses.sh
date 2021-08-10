#!/bin/bash

dataset='JAAD'
limit=360

cd /openpose # it needs to be run there to find 'models' dir

i=1
for filename in /datasets/${dataset}/videos/*.mp4; do
    name=$(basename "$filename" .mp4)
    echo "Processing ${name}..."
    ./build/examples/openpose/openpose.bin \
        --video ${filename} \
        --write_json /outputs/${dataset}/${name} \
        --model_pose BODY_25 \
        --display 0 \
        --render_pose 0
        # --hand
        # --write_video /outputs/${dataset}/${name}.avi
    ((i=i+1))
    if [ $i -gt $limit ]; then
        break
    fi
done
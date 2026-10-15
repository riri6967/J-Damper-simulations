#!/bin/bash
# Run one or more OpenFOAM case sets inside WSL and copy the results back to Windows.
#
#   Usage (in the Ubuntu terminal):
#     bash "/mnt/c/Users/<you>/Downloads/Pneumatics and Hydraulics/cfd/openfoam/run_in_wsl.sh" s01 gci_coarse gci_fine
#     NP=4 bash .../run_in_wsl.sh t_oscillatory        # fewer cores
#
# Each set is copied to ~/inerter/<set> (Linux filesystem: much faster than /mnt/c),
# run with its own Allrun, then postProcessing/ and the logs are copied back next to the
# Windows copy of every case. The bulky field data stays in ~/inerter.
NP=${NP:-8}
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /usr/lib/openfoam/openfoam2406/etc/bashrc || { echo "OpenFOAM v2406 not found"; exit 1; }
[ $# -gt 0 ] || { echo "usage: run_in_wsl.sh <set> [<set> ...]   (sets: $(cd "$SRC" && ls -d */ | tr -d / | tr '\n' ' '))"; exit 1; }

for set in "$@"; do
    [ -d "$SRC/$set" ] || { echo "no case set $SRC/$set"; exit 1; }
    echo "##### $set  ($(date +%H:%M))"
    rm -rf ~/inerter/"$set"; mkdir -p ~/inerter
    cp -r "$SRC/$set" ~/inerter/
    ( cd ~/inerter/"$set" && chmod +x Allrun && ./Allrun "$NP" 2>&1 | tee log.Allrun )
    for c in ~/inerter/"$set"/*/; do
        c=$(basename "$c"); [ "$c" = mesh ] && continue
        rm -rf "$SRC/$set/$c/postProcessing"
        [ -d ~/inerter/"$set/$c/postProcessing" ] && cp -r ~/inerter/"$set/$c/postProcessing" "$SRC/$set/$c/"
        cp ~/inerter/"$set/$c"/log.* "$SRC/$set/$c/" 2>/dev/null
    done
    cp ~/inerter/"$set"/log.Allrun "$SRC/$set/"
    echo "##### $set finished ($(date +%H:%M))"
done
echo "ALL SETS DONE"

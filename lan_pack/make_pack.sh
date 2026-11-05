#!/bin/sh
# lan_pack/files = a Reverse Studio build without the player-specific parts (music control, plugin list)
# usage: lan_pack/make_pack.sh ../blur_extracted/mods/reverse_studioN
set -e
cd "$(dirname "$0")"
rm -rf files && cp -r "$1" files
rm -rf files/amax/plugins/plugins.lua files/amax/plugins/musicctl files/audio

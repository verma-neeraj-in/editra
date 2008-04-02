#!/bin/bash

#
# Use epydoc to generate the api docs from the projects source code
#

epydoc --output=../../docs/editra_api \
       --no-frames \
       --css=./editra.css \
       --name=Editra \
       --html \
       ../../.

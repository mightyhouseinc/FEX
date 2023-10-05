from enum import Flag
import json
import struct
import sys
from json_config_parse import parse_json

if (len(sys.argv) < 3):
    sys.exit()

output_file = sys.argv[2]
with open(sys.argv[1], "r") as asm_file:
    asm_text = asm_file.read()
json_text = asm_text.split("%ifdef CONFIG")
if (len(json_text) > 1):
    json_text = json_text[1].split("%endif")
if (len(json_text) > 1):
    json_text = json_text[0].strip()

    parse_json(json_text, output_file)

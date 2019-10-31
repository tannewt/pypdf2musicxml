#!/usr/bin/env python

'''
usage:   extract.py <some.pdf>
Locates Form XObjects and Image XObjects within the PDF,
and creates a new PDF containing these -- one per page.
Resulting file will be named extract.<some.pdf>
'''

import sys
import os
import math

from music21 import *

from pdfrw import PdfReader, PdfWriter, PdfTokens
from pdfrw.findobjs import page_per_xobj

CLEF_MAPPING = {"(&)": clef.TrebleClef,
                "(V)": clef.Treble8vbClef,
                "(?)": clef.BassClef}

inpfn, = sys.argv[1:]
outfn = 'extract.' + os.path.basename(inpfn)
doc = PdfReader(inpfn)
page = doc.pages[0]
# page.Contents.stream = page.Contents.stream[:21000]
tokens = PdfTokens(page.Contents.stream)
indent = 0
commands = ["q", "Q", "ET", "BT", "cm", "Tm", "Tf", "s", "m", "l", "S", "TJ", "f", "Tj", "k", "re", "W", "n", "K", "w", "c"]
params = []
items = []
subcommands = []
for token in tokens:
    if token == "q":
        indent += 1
        if subcommands:
            items.append(subcommands)
        subcommands = []
    elif token == "Q":
        indent -= 1
        items.append(subcommands)
        #print(subcommands)
        subcommands = []
        #print()
    elif token in commands:
        #print(token, params)
        subcommands.append((token, params))
        params = []
        pass
    else:
        params.append(token)
        #print("  "*indent, token)

def subcommands_to_string(subcommands, nest=True):
    parts = []
    if nest:
        parts.append("q")
    for command, params in subcommands:
        parts.extend(params)
        parts.append(command)
    if nest:
        parts.append("Q")
    return " ".join(parts)
new_contents = ["q"]
header = [('re', ['0', '-0.2399902', '612', '792']), ('W', []), ('n', []), ('w', ['1.30291']), ('K', ['0', '0', '0', '1']), ('k', ['0', '0', '0', '1'])]
new_contents.append(subcommands_to_string(header, nest=False))
staff_lines = []
staff_length = None
staves = []
clefs = []
time_signatures = []
bars = []

def find_stave(y):
    for stave in staves:
        if stave["bounds"][0] <= y <= stave["bounds"][1]:
            return stave

    closest = None
    distance = 6000
    for stave in staves:
        min_y, max_y = stave["bounds"]
        d = min(abs(y - min_y), abs(y - max_y))
        if d < distance:
            closest = stave
            distance = d
    return closest

piano_pairs = []
systems = []
system_start = 0

for item in items:
    if not item or len(item) < 2:
        continue
    if item[1][0] == "m": # line of some sort
        x1, y1 = map(float, item[1][1])
        x2, y2 = map(float, item[2][1])
        # print(item)
        # print(x1, y1, x2, y2)
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if x1 == x2:
            #print(length, x1, y1, y2)
            bars.append((x1, y1, y2))
            item.insert(0, ('RG', ['0', '0.5', '1']))
        elif y1 == y2:
            if length < 40:
                item.insert(0, ('RG', ['0.5', '1', '0.5']))
            else:
                if not staff_lines:
                    staff_length = length
                staff_lines.append(y1)
                if len(staff_lines) == 5:
                    item.insert(0, ('RG', ['0.5', '0', '1']))
                    min_y = min(staff_lines)
                    max_y = max(staff_lines)

                    stave = {"all":staff_lines,"bounds":(min_y, max_y), "notes":stream.Part(), "symbols":[], "measure_count":0}
                    i = 0
                    while i < len(bars):
                        bar = bars[i]
                        x, y1, y2 = bar
                        if y1 == max_y and y2 == min_y:
                            stave["symbols"].append(("|", x, None))
                            bars.remove(bar)
                        elif len(staves) > system_start and staves[system_start]["bounds"][1] == y1 and y2 == min_y:
                            systems.append((system_start, len(staves)))
                            system_start = len(staves) + 1
                            bars.remove(bar)
                        elif staves and staves[-1]["bounds"][1] == y1 and y2 == min_y:
                            staves[-1]["symbols"].append(("|", x, None))
                            stave["symbols"].append(("|", x, None))
                            pair = (len(staves) - 1, len(staves))
                            if pair not in piano_pairs:
                                piano_pairs.append(pair)
                            bars.remove(bar)
                        else:
                            i += 1
                    staves.append(stave)
                    staff_lines = []

                    # Look for our clef
                    for clef in clefs:
                        symbol, x, y = clef
                        if min_y <= y <=max_y:
                            stave["clef"] = CLEF_MAPPING[symbol]()
                            stave["notes"].append(CLEF_MAPPING[symbol]())
                            clefs.remove(clef)
                            break
                    # Look for time signatures
                    i = 0
                    while i < len(time_signatures):
                        denominator = time_signatures[i]
                        numerator = time_signatures[i + 1]
                        dsymbol, dx, dy = denominator
                        nsymbol, nx, ny = numerator
                        if min_y <= dy <=max_y and min_y <= ny <= max_y:
                            nsymbol = nsymbol.strip("()")
                            dsymbol = dsymbol.strip("()")
                            stave["notes"].append(meter.TimeSignature("{}/{}".format(nsymbol, dsymbol)))
                            time_signatures.remove(denominator)
                            time_signatures.remove(numerator)
                        else:
                            i += 2
                else:
                    item.insert(0, ('RG', ['0.2', '0.2', '0.2']))

        else:
            #print(item)
            pass
    elif item[1][0] == "BT" and item[4][0] == "Tj": # text/notes of some sort
        symbol = item[4][1][0]
        x_scale = float(item[0][1][0])
        y_scale, x, y = map(float, item[0][1][-3:])
        x /= x_scale
        y /= y_scale
        if symbol in ["<cf>", "(.)", "(J)", "(!)", "(j)", "<e4>"]: # notes
            bars = [] # Clear bars so we ignore note stems
            #print(item)

            stave = find_stave(y)
            if stave:
                item.insert(0, ('rg', ['0.5', '0', '0']))
            else:
                item.insert(0, ('rg', ['1', '0', '0']))
            if symbol in ["(J)", "(j)"]:
                x += 0.1
            stave["symbols"].append((symbol, x, y))
        elif symbol in CLEF_MAPPING: # clefs
            clefs.append((symbol, x, y))
            item.insert(0, ('rg', ['0.8', '0', '0']))
        elif symbol in ["(8)", "(12)"]: # time signature
            time_signatures.append((symbol, x, y))
            item.insert(0, ('rg', ['0.6', '0', '0']))
        elif symbol in []:
            # (q.) is dotted quarter with stem
            # (f) is forte
            # (,) is measure 4 ?
            # (-) is measure 8 ?
            item.insert(0, ('rg', ['0.6', '0.6', '0']))
        else:
            pass
            #print(item)
    elif len(item) == 5 and item[0][0] == "m" and item[1][0] == "l" and item[4][0] == "f":
        x1, y1 = [float(x) / 0.24 for x in item[0][1]]
        x2, _ = [float(x) / 0.24 for x in item[1][1]]
        item.insert(0, ('rg', ['0', '0.6', '0']))
        #time_signatures.append(("_", x, y))
        stave = find_stave(y1)
        stave["symbols"].append(("_", x2-22, x1))
    else:
        pass
        #print(item)
    new_contents.append(subcommands_to_string(item))
new_contents.append("q")
page.Contents.stream = " ".join(new_contents)
print()

DURATION = {
    "(.)": ".",
    "(J)": "8",
    "(j)": "8"
}

RESTS = {
    "(!)": 6,
    "<e4>": 0.5
}

NOTES = {
    "<cf>": "4"
}

PITCHES = ["c", "d", "e", "f", "g", "a", "b"]
CLEF_OFFSET = {
"treble": -5,
"\"treble_8\"" : -5,
"bass" : -3
}

for stave in staves:
    notes = stave["notes"]
    stave["symbols"].sort(key=lambda x: x[1])
    current_measure = stream.Measure()
    current_chord = chord.Chord()
    current_x = None
    flag_bars = []
    baseline = stave["all"][-1] - 1
    gap = (stave["all"][-2] - stave["all"][-1]) / 2
    clef = stave["clef"]
    for symbol, x, y in stave["symbols"]:
        if current_x is None:
            current_x = x
        print(symbol, x, y)
        if symbol in DURATION:
            if symbol in ["(j)", "(J)"]:
                current_chord.duration.quarterLength /= 2
            elif symbol == "(.)":
                current_chord.duration.dots = 1
        elif symbol in RESTS or symbol in NOTES:
            if x != current_x:
                if current_chord:
                    flag_bars = [f for f in flag_bars if f[1] > current_x]
                    print(current_x, current_chord, flag_bars)
                    for flag_bar in flag_bars:
                        # Skip flag bars that haven't started
                        if flag_bar[0] > current_x:
                            continue
                        print("divide", flag_bar)
                        current_chord.duration.quarterLength /= 2
                    current_measure.append(current_chord)
                    current_chord = chord.Chord()
                current_x = x
            if symbol in RESTS:
                current_chord = note.Rest(quarterLength=RESTS[symbol])
                continue
            index = int(round((y - baseline) / gap))
            index += clef.lowestLine
            p = pitch.Pitch()
            p.diatonicNoteNum = index
            current_chord.add(p)
        elif symbol == "|":
            flag_bars = [f for f in flag_bars if f[1] > current_x]
            for flag_bar in flag_bars:
                current_chord.duration.quarterLength /= 2
            current_measure.append(current_chord)
            notes.append(current_measure)
            current_measure = stream.Measure()
            current_chord = chord.Chord()
            current_x = x
        elif symbol == "_":
            flag_bars.append((x,y))
        else:
            print(symbol, x, y)
    del stave["symbols"]

names = ["soprano", "alto", "tenor", "bass"]

combined = {
}

stave_count = systems[0][1] + 1
for i in range(systems[0][0], systems[0][1] + 1):
    staff = staves[i]
    for element in staff["notes"]:
        if isinstance(element, stream.Measure):
            staff["measure_count"] += 1
            element.number = staff["measure_count"]

    if i in piano_pairs[0]:
        if i == piano_pairs[0][0]:
            combined["piano"] = [staves[i]["notes"], None]
        else:
            combined["piano"][1] = staves[i]["notes"]
            piano_pairs.pop(0)
    else:
        combined[names[i]] = staves[i]["notes"]

for system in systems[1:]:
    voices = set(combined.keys())
    stave_count = system[1] - system[0] + 1
    for i in range(system[0], system[1] + 1):
        notes = staves[i]["notes"]
        # if measure_count is None:
        #     print(notes)
        #     measure_count = notes.count("|")
        if i in piano_pairs[0]:
            if i == piano_pairs[0][0]:
                for element in notes:
                    # if isinstance(element, stream.Measure):
                    #     combined["piano"][0]["measure_count"] += 1
                    #     element.number = combined["piano"][0]["measure_count"]
                    combined["piano"][0].append(element)
            else:
                for element in notes:
                    # if isinstance(element, stream.Measure):
                    #     combined["piano"][0]["measure_count"] += 1
                    #     element.number = combined["piano"][1]["measure_count"]
                    combined["piano"][1].append(element)
                piano_pairs.pop(0)
                voices.remove("piano")
    # for voice in voices:
    #     combined[voice].extend(["R1", "|"] * measure_count)

s = stream.Score()
s.append(combined["piano"])
single = s.parts[0].measures(1, 1)
print("single", single)
double = s.parts[0].measures(1, 2)
double.insert(0, tempo.MetronomeMark(text="Allegro", number=120, referent=note.Note(quarterLength=1.5)))
print("double", double)
double.show("text", addEndTimes=True)
double.show()
#print(single.write())
print(double.write())

outdata = PdfWriter("first.pdf")
outdata.addpage(doc.pages[0])
outdata.write()
#pages = list(page_per_xobj(, margin=0.5*72))
# if not pages:
#     raise IndexError("No XObjects found")

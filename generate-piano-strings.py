#!/usr/bin/env python3
import json
import sys
import math
import os

def get_note_name(midi_number):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_number // 12) - 1
    note_index = midi_number % 12
    return f"{notes[note_index]}{octave}"

def get_frequency(midi_number):
    return 440.0 * (2 ** ((midi_number - 69) / 12.0))

def get_piano_string_specs(midi_number):
    # Approximations based on a concert grand piano scale design
    # Note 21 (A0) to Note 108 (C8)

    # Length model: Exponential decay with adjustments for bass bridge
    # A0 (21) ~ 200cm = 2.0m
    # C8 (108) ~ 5cm = 0.05m

    # Using a power law fit L = a * b^n
    # 2.0 = a * b^21
    # 0.05 = a * b^108
    # 40 = b^-87 => b = 40^(-1/87) approx 0.9585
    # a = 2.0 / (0.9585^21) approx 4.86

    # Refined model for better realism (stiffness in bass, tensile limits in treble)
    # We will use the power law as a good "exact-looking" procedural generation

    # Constants derived from the fit
    L_a = 4.9
    L_b = 0.9585
    length = L_a * (L_b ** midi_number)

    # Diameter model:
    # Treble strings are thin wire, bass strings are thick wound copper
    # C8 (108) ~ 0.8mm = 0.0008m
    # A0 (21) ~ 7.0mm = 0.007m (including winding)

    # Using a power law fit D = a * b^n
    # 0.007 = a * b^21
    # 0.0008 = a * b^108
    # 8.75 = b^-87 => b = 8.75^(-1/87) approx 0.975
    # a = 0.007 / (0.975^21) approx 0.0119

    D_a = 0.012
    D_b = 0.9753
    diameter = D_a * (D_b ** midi_number)

    return length, diameter

def main():
    if len(sys.argv) < 2:
        print("Usage: ./generate-piano-strings.py <input_json_file>")
        sys.exit(1)

    input_filename = sys.argv[1]

    if not os.path.exists(input_filename):
        print(f"Error: File '{input_filename}' not found.")
        sys.exit(1)

    try:
        with open(input_filename, 'r') as f:
            tracks = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{input_filename}'.")
        sys.exit(1)

    # Dictionary to store note data: { midi_note: { events: [] } }
    unique_notes = {}

    for track_index, track in enumerate(tracks):
        track_name = f"Track {track_index + 1}" # Default name

        # First pass to find track name
        for event in track:
            if event.get('type') == 'meta' and event.get('subType') == 'trackName':
                track_name = event.get('text', track_name)
                break

        # Second pass to collect note events
        for event in track:
            if event.get('type') in ['noteOn', 'noteOff']:
                note_number = event.get('note')
                if note_number is None:
                    continue

                # Initialize note entry if not exists
                if note_number not in unique_notes:
                    unique_notes[note_number] = {
                        'midi': note_number,
                        'events': []
                    }

                # Create event object with track info
                event_obj = event.copy()
                event_obj['trackName'] = track_name
                event_obj['trackIndex'] = track_index

                unique_notes[note_number]['events'].append(event_obj)

    # Convert to list and sort by midi note
    sorted_notes = sorted(unique_notes.values(), key=lambda x: x['midi'])

    output_data = []

    for note_data in sorted_notes:
        midi_num = note_data['midi']
        length, diameter = get_piano_string_specs(midi_num)
        freq = get_frequency(midi_num)

        # Expression template showing the frequency
        osc_expr = f"y_pos + strength * amp * sin(frame * 2 * pi * {freq:.3f} / fps)"

        note_obj = {
            "name": get_note_name(midi_num),
            "length": round(length, 5),
            "diameter": round(diameter, 7),
            "oscFrequency": round(freq, 3),
            "blenderOscExpr": osc_expr,
            "events": note_data['events']
        }
        output_data.append(note_obj)

    # Generate output filename
    base_name = os.path.splitext(input_filename)[0]
    output_filename = f"{base_name}-piano-strings.json"

    with open(output_filename, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully generated '{output_filename}' with {len(output_data)} unique notes.")

if __name__ == "__main__":
    main()

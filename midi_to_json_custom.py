#!/usr/bin/env python3
import sys
import struct
import json

def read_variable_length(data, offset):
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            break
    return value, offset

def parse_midi(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    if data[0:4] != b'MThd':
        print("Invalid MIDI file: Missing MThd header")
        return None

    header_len = struct.unpack('>I', data[4:8])[0]
    format_type, num_tracks, time_division = struct.unpack('>HHH', data[8:8+header_len])

    offset = 8 + header_len
    ticks_per_quarter = time_division

    if time_division & 0x8000:
        print("SMPTE time division not supported in this simple parser.")
        return None

    tracks = []
    all_events = [] # For tempo map calculation: (absolute_ticks, type, subtype, data...)

    for track_idx in range(num_tracks):
        if data[offset:offset+4] != b'MTrk':
            print(f"Expected MTrk at offset {offset}")
            break

        offset += 4
        track_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        track_end = offset + track_len

        absolute_ticks = 0
        last_status = 0
        track_events = []

        while offset < track_end:
            delta_time, offset = read_variable_length(data, offset)
            absolute_ticks += delta_time

            status = data[offset]

            if status >= 0x80:
                offset += 1
                if status < 0xF0:
                    last_status = status
            else:
                if last_status == 0:
                    print("Error: Running status used without previous status")
                    break
                status = last_status

            event_type = status >> 4
            channel = status & 0x0F

            event = {
                "absoluteTicks": absolute_ticks,
                "channel": channel
            }

            if status == 0xFF: # Meta Event
                meta_type = data[offset]
                offset += 1
                length, offset = read_variable_length(data, offset)
                meta_data = data[offset:offset+length]
                offset += length

                event["type"] = "meta"
                event["metaType"] = meta_type

                if meta_type == 0x51 and length == 3: # Set Tempo
                    microseconds = (meta_data[0] << 16) | (meta_data[1] << 8) | meta_data[2]
                    event["subType"] = "setTempo"
                    event["tempo"] = microseconds
                    all_events.append(event) # Add to global list for tempo map
                elif meta_type == 0x03: # Track Name
                    event["subType"] = "trackName"
                    try:
                        event["text"] = meta_data.decode('utf-8')
                    except:
                        event["text"] = str(meta_data)
                elif meta_type == 0x2F:
                    event["subType"] = "endOfTrack"
                else:
                    event["subType"] = "unknown"

            elif status == 0xF0 or status == 0xF7: # Sysex
                length, offset = read_variable_length(data, offset)
                offset += length
                event["type"] = "sysex"

            else: # Channel Voice Message
                if event_type == 0x8: # Note Off
                    note = data[offset]
                    velocity = data[offset+1]
                    offset += 2
                    event["type"] = "noteOff"
                    event["note"] = note
                    event["velocity"] = velocity
                elif event_type == 0x9: # Note On
                    note = data[offset]
                    velocity = data[offset+1]
                    offset += 2
                    if velocity == 0:
                        event["type"] = "noteOff"
                        event["note"] = note
                        event["velocity"] = 0
                    else:
                        event["type"] = "noteOn"
                        event["note"] = note
                        event["velocity"] = velocity
                elif event_type == 0xA: # Poly Key Pressure
                    note = data[offset]
                    pressure = data[offset+1]
                    offset += 2
                    event["type"] = "polyphonicKeyPressure"
                    event["note"] = note
                    event["pressure"] = pressure
                elif event_type == 0xB: # Control Change
                    controller = data[offset]
                    value = data[offset+1]
                    offset += 2
                    event["type"] = "controlChange"
                    event["controller"] = controller
                    event["value"] = value
                elif event_type == 0xC: # Program Change
                    program = data[offset]
                    offset += 1
                    event["type"] = "programChange"
                    event["program"] = program
                elif event_type == 0xD: # Channel Pressure
                    pressure = data[offset]
                    offset += 1
                    event["type"] = "channelPressure"
                    event["pressure"] = pressure
                elif event_type == 0xE: # Pitch Bend
                    lsb = data[offset]
                    msb = data[offset+1]
                    offset += 2
                    value = (msb << 7) | lsb
                    event["type"] = "pitchBend"
                    event["value"] = value

            track_events.append(event)

        tracks.append(track_events)

    # Build Tempo Map
    # Sort all tempo events by absolute ticks
    tempo_events = [e for e in all_events if e.get("subType") == "setTempo"]
    tempo_events.sort(key=lambda x: x["absoluteTicks"])

    # Ensure initial tempo
    if not tempo_events or tempo_events[0]["absoluteTicks"] > 0:
        tempo_events.insert(0, {"absoluteTicks": 0, "tempo": 500000}) # Default 120 BPM

    def ticks_to_seconds(ticks):
        current_time = 0.0
        current_tick = 0
        current_tempo = 500000 # Default

        for te in tempo_events:
            if ticks < te["absoluteTicks"]:
                break

            delta = te["absoluteTicks"] - current_tick
            current_time += (delta * current_tempo) / (ticks_per_quarter * 1000000.0)

            current_tick = te["absoluteTicks"]
            current_tempo = te["tempo"]

        delta = ticks - current_tick
        current_time += (delta * current_tempo) / (ticks_per_quarter * 1000000.0)
        return current_time

    # Convert all events to seconds
    processed_tracks = []
    max_time = 0
    last_note_off = 0

    for track in tracks:
        processed_track = []
        for event in track:
            event["time"] = ticks_to_seconds(event["absoluteTicks"])
            processed_track.append(event)

            if event["time"] > max_time:
                max_time = event["time"]
            if event.get("type") == "noteOff" and event["time"] > last_note_off:
                last_note_off = event["time"]

        processed_tracks.append(processed_track)

    print(f"Parsed {len(tracks)} tracks.")
    print(f"Last Note Off Time (Raw): {last_note_off:.4f} seconds")
    print(f"Total Duration (Raw): {max_time:.4f} seconds")

    return processed_tracks, last_note_off

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Convert MIDI to JSON with optional time scaling.')
    parser.add_argument('midi_file', help='Input MIDI file')
    parser.add_argument('--target-duration', type=float, help='Target duration for the last note off (in seconds). If provided, time will be scaled.')

    args = parser.parse_args()

    json_data, last_note_off = parse_midi(args.midi_file)

    if json_data:
        scale_factor = 1.0
        if args.target_duration:
            if last_note_off > 0:
                scale_factor = args.target_duration / last_note_off
                print(f"Scaling time by {scale_factor:.6f} to match target duration of {args.target_duration}s")

                # Apply scaling
                for track in json_data:
                    for event in track:
                        event["time"] *= scale_factor
            else:
                print("Warning: Last note off is 0, cannot scale.")

        output_file = args.midi_file.replace(".mid", ".json").replace(".midi", ".json")
        if output_file == args.midi_file:
            output_file += ".json"

        with open(output_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        print(f"Saved to {output_file}")

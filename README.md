# Dance of the Sugar Plum Fairy

This is my first fully open-source animation project.

The full animation can be viewed on YouTube:


I used the following tools:

1. Bitwig Studio 5.3.13
2. Blender 5.0
3. VSCode with GitHub Copilot + Gemini 3 Pro

# Background

I started this project while watching Polyfjord's excellent Audio Visualizer
Master Class: https://www.youtube.com/watch?v=amJKrcopZ8A

As I was working on it, I realized that instead of using Wavefront OBJ
files as an intermediary, I could have Copilot help me write Python script
to first parse standardized "*.dawproject" files and dump JSON data, then
further help me write Blender Python files to load the JSON data and create
objects, lights, materials, and animation directly within Blender.

I'm a huge fan of bell choirs and chimes, and "Dance of the Sugar Plum Fairy"
is one of my favorite songs. So I imported a free-to-use MIDI file of the
song into Bitwig Studio, assigned all the instruments and adjusted their
volumes, then rendered out a WAV file and "*.dawproject" files, separating
the parts into the chimes ("Celesta") and violins.

From there, I converted the data to JSON file and started work on the
Blender scripts to build up the objects, lights, materials, and animation.

Finally, I rendered the images out to EXR files and composited them together
to a final H.264+AAC video and uploaded to YouTube.

----------------------------------------------------------------------

Enjoy!

----------------------------------------------------------------------

# License

Copyright 2025 Glenn M. Lewis. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

----------------------------------------------------------------------

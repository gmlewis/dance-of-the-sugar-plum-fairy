import OpenEXR, Imath, glob, os

def batch_set_interop(pattern, prefix, interop_id):
    for filepath in sorted(glob.glob(pattern)):
        outfile = prefix + os.path.basename(filepath)
        with OpenEXR.InputFile(filepath) as infile:
            header = infile.header()
            header['colorInteropID'] = Imath.StringAttribute(interop_id)
        with OpenEXR.OutputFile(outfile, header) as outf: pass  # No pixels = instant
        print(f"Set {interop_id} on {outfile}")

batch_set_interop('DanceOfTheSugarPlumFairy_EVEE_v41_*.exr', 'dark_', 'lin_rec709_scene')
batch_set_interop('DanceOfTheSugarPlumFairy_EVEE_v41_*.exr', 'light_', '')  # Empty

#!/usr/bin/env python3
"""
A wrapper around the 'slicer' reporting tool (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis)
that generates a web page with a row of image slices for each subject in the BIDS repository.
In this way you can do a simple visual quality control of any datatype in your BIDS repository

Requires an existing installation of FSL/slicer
"""

import argparse
import logging
import subprocess
import sys
import csv
from pathlib import Path
try:
    from bidscoin import bidscoin
except ImportError:
    sys.path.append(str(Path(__file__).parents[1]))             # This should work if bidscoin was not pip-installed
    import bidscoin

html_head = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Slice report</title>
    <style>
        body { background-color: #181818; font-family: Arial; }
        h3   { color: #FFFFFF; }
        p    { color: #D1D1D1; }
        a    { color: #D1D1D1; text-decoration: none; }
        a:hover, a:active { color: orange; }
    </style>
</head>

<body>

"""


def parsemainopts(mainopts: list) -> str:
    """Check the MAINOPTS arguments and return them to a string that can be passed to slicer"""
    for n, mainopt in enumerate(mainopts):
        if mainopts[n-1] == 'l': continue                       # Skip checking the LUT string
        if not (mainopt in ('L','l','i','e','t','n','u','s','c') or mainopt.replace('.','').replace('-','').isdecimal()):
            print(f"Invalid MAINOPTS: {' '.join(mainopts)}"); sys.exit(2)
        if mainopt.isalpha():
            mainopts[n] = '-' + mainopts[n]

    return  f"{' '.join(mainopts)}"


def parseoutputopts(opts: list, name: str) -> tuple:
    """
    Check the NAME arguments and append slicer output images to them

    :return: (outputopts: str, outputimages: list)
    """
    sliceimages = []
    outputopts  = ''
    isnumber    = lambda arg: arg.replace('.','').replace('-','').isdecimal()
    for n, outputopt in enumerate(opts):
        if not (outputopt in ('x', 'y', 'z', 'a', 'A', 'S') or isnumber(outputopt)):
            print(f"Invalid {name}: '{outputopt}' in '{' '.join(opts)}'"); sys.exit(2)
        if outputopt.isalpha():
            sliceimages.append(f"slice_tmp{n}.png")
            if outputopt == 'a':
                outputopts += f"-{outputopt} {sliceimages[-1]} "
            elif outputopt in ('x', 'y', 'z', 'A'):
                if not isnumber(opts[n+1]):
                    print(f"Invalid {name}: '{opts[n + 1]}' in '{' '.join(opts)}'"); sys.exit(2)
                outputopts += f"-{outputopt} {opts[n+1]} {sliceimages[-1]} "
            elif outputopt == 'S':
                if not (isnumber(opts[n+1]) and isnumber(opts[n+2])):
                    print(f"Invalid {name}: {outputopt} >> '{' '.join(opts)}'"); sys.exit(2)
                outputopts += f"-{outputopt} {opts[n+1]} {opts[n+2]} {sliceimages[-1]} "

    return outputopts, sliceimages


def appendslices(inputimage, outlineimage, mainopts, outputopts, reportses, slicerimages, outputimage):
    """Run slicer and append the sliced images to a row"""

    # Slice the image
    command = f"slicer {inputimage} {outlineimage} {mainopts} {outputopts}"
    LOGGER.bcdebug(f"Running: {command}")
    process = subprocess.run(command, cwd=reportses, shell=True, capture_output=True, text=True)
    if process.stderr or process.returncode!=0:
        LOGGER.error(f"{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
        sys.exit(process.returncode)

    # Append the sliced images to a row
    command = f"pngappend {' + '.join(slicerimages)} {outputimage}"
    process = subprocess.run(command, cwd=reportses, shell=True, capture_output=True, text=True)
    if process.stderr or process.returncode!=0:
        LOGGER.error(f"{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
        sys.exit(process.returncode)

    # Clean up the intermediate slicer output images
    for slicerimage in slicerimages:
        (reportses/slicerimage).unlink()


def slicereport(bidsdir: str, pattern: str, outlinepattern: str, outlineimage: str, subjects: list, reportdir: str, qccols: list, mainopts: list, outputopts: list, suboutputopts: list):
    """
    :param bidsdir:         The bids-directory with the subject data
    :param pattern:         Globlike search pattern to select the images in bidsdir to be reported, e.g. 'anat/*_T1w*'
    :param outlinepattern:  Globlike search pattern to select red-outline images that are projected on top of the reported images. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir`
    :param outlineimage:    A common red-outline image that is projected on top of all images
    :param subjects:        Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param reportdir:       The folder where the report is saved
    :param qccols:          Column names for creating an accompanying tsv-file to store QC-rating scores
    :param mainopts:        Slicer main options
    :param outputopts:      Slicer output options
    :param suboutputopts:   Slicer output options for creating the subreports (same as OUTPUTOPTS)
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}"); return
    if not reportdir:
        reportdir = bidsdir/'derivatives/slicereport'
    else:
        reportdir = Path(reportdir).resolve()
    if outlineimage:
        if outlinepattern:
            print('The "--outlineimage" and "--outlinepattern" arguments are mutually exclusive, please specify one or the other'); return
        outlineimage = Path(outlineimage).resolve()
        if not outlineimage.is_file():
            print(f"Could not find the common outline image: {outlineimage}"); return
    if outlinepattern and ':' in outlinepattern:
        outlinedir, outlinepattern = outlinepattern.split(':',1)
        outlinedir = Path(outlinedir).resolve()
        if not outlinedir.is_dir():
            print(f"Could not find the outline folder: {outlinedir}"); return
    else:
        outlinedir = bidsdir

    # Format the slicer main and output options and sliced images
    mainopts                       = parsemainopts(mainopts)
    outputopts, slicerimages       = parseoutputopts(outputopts, 'OUTPUTOPTS')
    suboutputopts, subslicerimages = parseoutputopts(suboutputopts, 'SUBOUTPUTOPTS')

    # Get the list of subjects
    if not subjects:
        subjects = bidscoin.lsdirs(bidsdir, 'sub-*')
        if not subjects:
            print(f"No subjects found in: {bidsdir/'sub-*'}"); return
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in subjects]               # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Start logging
    reportdir.mkdir(parents=True, exist_ok=True)
    (reportdir/'slicereport.log').unlink(missing_ok=True)
    bidscoin.setup_logging(reportdir/'slicereport.log')
    LOGGER.info(f"Command: {' '.join(sys.argv)}")

    # Create the report index file
    report = reportdir/'index.html'
    report.write_text(f'{html_head}<h3><span style="color: #D3D3D3">Command:</span> slicereport {" ".join(sys.argv[1:])}</h3><br>\n')

    # Create a QC tsv-file
    qcfile = reportdir/'qcscores.tsv'
    if qccols:
        with open(qcfile, 'wt') as fid:
            tsv_writer = csv.writer(fid, delimiter='\t')
            tsv_writer.writerow(['subject/session'] + qccols)

    # Loop over the subject/session-directories
    for subject in subjects:
        sessions = bidscoin.lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = [subject]
            subses   = ''
        else:
            subses   = subject.name + '/'
        for session in sessions:

            # Write a row in the QC tsv-file
            if qccols:
                with open(qcfile, 'a') as fid:
                    tsv_writer = csv.writer(fid, delimiter='\t')
                    tsv_writer.writerow([str(session.relative_to(bidsdir))] + len(qccols) * ['n/a'])

            # Search for the image(s) to report
            LOGGER.info(f"Processing images in: {session.relative_to(bidsdir)}")
            images = sorted([str(match.with_suffix('').with_suffix('')) for match in session.glob(pattern) if '.nii' in match.suffixes])
            if not images:
                LOGGER.warning(f"Could not find images using: {session.relative_to(bidsdir)}/{pattern}")
                continue
            outlineimages = [''] * len(images)
            if outlinepattern:
                outlinesession = outlinedir/session.relative_to(bidsdir)
                outlineimages  = sorted([str(match.with_suffix('').with_suffix('')) for match in outlinesession.glob(outlinepattern) if '.nii' in match.suffixes])
                if len(outlineimages) != len(images):
                    LOGGER.error(f"Nr of outline images ({len(outlineimages)}) in {outlinesession.relative_to(bidsdir)} should be the same as the number of underlying images ({len(images)})")
                    outlineimages = [''] * len(images)

            # Generate the report row(s)
            reportses = reportdir/session.relative_to(bidsdir)
            reportses.mkdir(parents=True, exist_ok=True)
            for n, image in enumerate(images):

                # Generate the sliced image row
                outline  = outlineimages[n] if outlinepattern else outlineimage
                slicerow = f"{Path(image).name}.png"
                appendslices(image, outline, mainopts, outputopts, reportses, slicerimages, slicerow)

                # Add a row to the report
                caption = f"{Path(image).relative_to(bidsdir)}{'&nbsp;&nbsp;&nbsp;['+str(Path(outline).relative_to(outlinedir))+']' if outline else ''}"
                with report.open('a') as fid:
                    fid.write(f'\n<p><a href="{subses + session.name}/index.html">'
                              f'<image src="{subses + session.name}/{slicerow}"><br>\n{caption}</a></p>\n')

                # Add a subreport
                if suboutputopts:
                    slicerow = f"{Path(image).name}_s.png"
                    appendslices(image, outline, mainopts, suboutputopts, reportses, subslicerimages, slicerow)
                (reportses/'index.html').write_text(f'{html_head}<h3>{caption}</h3>\n\n'
                                                    f'<image src="{slicerow}">\n\n</body></html>')

    # Finish off
    errors = bidscoin.reporterrors().replace('\n', '<br>\n')
    if errors:
        footer = '<h3 style="color:#EE4B2B">The following errors and warnings were reported:</h3>\n'
    else:
        footer = '<h3 style="color:#50C878">No errors or warnings were reported</h3>\n'
    with report.open('a') as fid:
        fid.write(f'\n<br>{footer}<p>\n{errors}</p>\n\n</body></html>')
    if qccols:
        LOGGER.info(' ')
        LOGGER.info('To store QC ratings, open:')
        LOGGER.info(qcfile)
    LOGGER.info(' ')
    LOGGER.info('To view the slice report, point your web browser at:')
    LOGGER.info(f"{report}\n ")


def main():
    """Console script usage"""

    epilogue = """
MAINOPTS:
  L                  : Label slices with slice number.
  l [LUT]            : Use a different colour map from that specified in the header.
  i [MIN] [MAX]      : Specify intensity min and max for display range.
  e [THR]            : Use the specified threshold for edges (if > 0 use this proportion of max-min,
                       if < 0, use the absolute value)
  t                  : Produce semi-transparent (dithered) edges.
  n                  : Use nearest-neighbour interpolation for output.
  u                  : Do not put left-right labels in output.
  s                  : Size scaling factor
  c                  : Add a red dot marker to top right of image

OUTPUTOPTS:
  x/y/z [SLICE] [..] : Output sagittal, coronal or axial slice (if [SLICE] > 0 it is a
                       fraction of image dimension, if < 0, it is an absolute slice number)
  a                  : Output mid-sagittal, -coronal and -axial slices into one image
  A [WIDTH]          : Output _all_ axial slices into one image of _max_ width [WIDTH]
  S [SAMPLE] [WIDTH] : As `A` but only include every [SAMPLE]'th slice

examples:
  slicereport myproject/bids anat/*_T1w*
  slicereport myproject/bids fmap/*_phasediff* -o fmap/*_magnitude1*
  slicereport myproject/bids/derivatives/fmriprep anat/*run-?_desc-preproc_T1w* -o anat/*run-?_label-GM*
  slicereport myproject/bids/derivatives/deface anat/*_T1w* -o myproject/bids:anat/*_T1w* --mainopts L e 0.05
  slicereport myproject/bids anat/*_T1w* --outputopts x 0.4 x 0.5 x 0.6 z 0.3 z 0.4 z 0.5 z 0.6 z 0.7\n """

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=__doc__, epilog=epilogue)
    parser.add_argument('bidsfolder',               help='The bids-directory with the subject data')
    parser.add_argument('pattern',                  help="Globlike search pattern to select the images in bidsdir to be reported, e.g. 'anat/*_T2starw*'")
    parser.add_argument('-o','--outlinepattern',    help="Globlike search pattern to select red outline images that are projected on top of the reported images (i.e. 'outlinepattern' must yield the same number of images as 'pattern'. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir` (see examples below)`")
    parser.add_argument('-i','--outlineimage',      help='A common red-outline image that is projected on top of all images')
    parser.add_argument('-p','--participant_label', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed', nargs='+')
    parser.add_argument('-r','--reportfolder',      help="The folder where the report is saved (default: bidsfolder/derivatives/slicereport)")
    parser.add_argument('-q','--qcscores',          help="Column names for creating an accompanying tsv-file to store QC-rating scores (default: rating_overall)", default=['rating_overall'], nargs='+')
    parser.add_argument('--mainopts',               help='Main options of slicer (see below). (default: "s 1")', default=['s','1'], nargs='+')
    parser.add_argument('--outputopts',             help='Output options of slicer (see below). (default: "x 0.4 x 0.5 x 0.6 y 0.4 y 0.5 y 0.6 z 0.4 z 0.5 z 0.6")', default=['x','0.4','x','0.5','x','0.6','y','0.4','y','0.5','y','0.6','z','0.4','z','0.5','z','0.6'], nargs='+')
    parser.add_argument('--suboutputopts',          help='Output options of slicer for creating the subreports (same as OUTPUTOPTS, see below). (default: "S 4 1600")', default=['S', '4', '1600'], nargs='+')
    args = parser.parse_args()

    slicereport(bidsdir        = args.bidsfolder,
                pattern        = args.pattern,
                outlinepattern = args.outlinepattern,
                outlineimage   = args.outlineimage,
                subjects       = args.participant_label,
                reportdir      = args.reportfolder,
                qccols         = args.qcscores,
                mainopts       = args.mainopts,
                outputopts     = args.outputopts,
                suboutputopts  = args.suboutputopts)


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)

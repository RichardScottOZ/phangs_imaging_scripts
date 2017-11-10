# NB: CASA doesn't always include the pwd in the module search path. I
# had to modify my init.py file to get this to import. See the README.

import os
import numpy as np
import scipy.ndimage as ndimage
import glob

# Other PHANGS scripts
import line_list

# Analysis utilities
import analysisUtils as au

# CASA imports
from taskinit import *

from concat import concat
from exportfits import exportfits
from flagdata import flagdata
from imhead import imhead
from imstat import imstat
from imregrid import imregrid
from importfits import importfits
from mstransform import mstransform
from split import split
from statwt import statwt
from tclean import tclean
from uvcontsub import uvcontsub

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Interface to the text file keys that steer the process
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

def read_ms_key(fname='../scripts/ms_file_key.txt'):
    """
    Read the measurement set key into a big dictionary. This maps
    locations of reduced files to galaxy, project, and data set name.
    """
    infile = open(fname, 'r')

    ms_key = {}

    while True:
        line  = infile.readline()    
        if len(line) == 0:
            break
        if line[0] == '#':
            continue
        words = line.split()
        if len(words) < 4:
            continue

        this_gal = words[0]
        this_proj = words[1]
        this_ms = words[2]
        this_file = words[3]

        if ms_key.has_key(this_gal) == False:
            ms_key[this_gal] = {}
        if ms_key[this_gal].has_key(this_proj) == False:
            ms_key[this_gal][this_proj] = {}
        ms_key[this_gal][this_proj][this_ms] = this_file
        
    infile.close()
    
    return ms_key

def read_dir_key(fname='../scripts/dir_key.txt'):
    """
    Read the directory key, which gives us a general way to sort out
    which MS files go in which directory. This is relevant mainly for
    cases where multiple science goals target a single galaxy. In
    those cases, we want the whole galaxy in one directory. This gives
    a way to map, e.g., ngc3627north to ngc3627/
    """
    infile = open(fname, 'r')
    
    dir_key = {}

    while True:
        line  = infile.readline()    
        if len(line) == 0:
            break
        if line[0] == '#':
            continue
        words = line.split()
        if len(words) < 2:
            continue

        this_ms = words[0]
        this_dir = words[1]    
        dir_key[this_ms] = this_dir
        
    infile.close()
    
    return dir_key

def dir_for_gal(gal=None):
    """
    Return the working directory given a galaxy name. See above.
    """

    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    dir_key = read_dir_key()
    if dir_key.has_key(gal):
        this_dir = '../'+dir_key[gal]+'/'
    else:
        this_dir = '../'+gal+'/'

    return this_dir

def list_gal_names():
    """
    List the full set of galaxy names known from the ms_file_key
    """
    ms_key = read_ms_key()
    gal_names = ms_key.keys()
    gal_names.sort()
    return gal_names

def read_mosaic_key(fname='../scripts/mosaic_definitions.txt'):
    """
    Read the file containing the centers and velocities for each
    mosaic. Note that for cases where the galaxy is observed several
    times, the RA and DEC refer to the intended center of the mosaic,
    NOT the center of the galaxy. In other cases, we tend use the NED
    center.
    """
    infile = open(fname, 'r')

    mosaic_key = {}

    while True:
        line  = infile.readline()    
        if len(line) == 0:
            break
        if line[0] == '#':
            continue
        words = line.split()

        if len(words) < 5:
            continue

        this_gal = words[0]
        this_ra = words[1]
        this_dec = words[2]
        this_vsys = words[3]
        this_vwidth = words[4]
        
        mosaic_key[this_gal] = {}
        mosaic_key[this_gal]['rastring'] = this_ra
        mosaic_key[this_gal]['decstring'] = this_dec
        mosaic_key[this_gal]['vsys'] = float(this_vsys)
        mosaic_key[this_gal]['vwidth'] = float(this_vwidth)

    infile.close()
    
    return mosaic_key

def read_override_mosaic_params(
    fname='../scripts/override_mosaic_params.txt'
    ):
    """
    Read hand set overrides for cell and image sizes.
    """

    infile = open(fname, 'r')

    override_dict = {}
    while True:
        line = infile.readline()    
        if len(line) == 0:
            break
        if line[0] == '#':
            continue
        words = line.split()
        if len(words) < 3:
            continue
        vis_override = words[0]
        param_override = words[1]
        value_override = words[2]
        if override_dict.has_key(vis_override) == False:
            override_dict[vis_override] = {}
        override_dict[vis_override][param_override] = value_override
            
    infile.close()

    return override_dict

def read_override_imaging_params(
    fname='../scripts/override_imaging_params.txt'
    ):
    """
    Read hand set overrides for imaging parameters.
    """

    infile = open(fname, 'r')

    override_dict = {}
    while True:
        line = infile.readline()    
        if len(line) == 0:
            break
        if line[0] == '#':
            continue
        words = line.split()
        if len(words) < 3:
            continue
        vis_override = words[0]
        param_override = words[1]
        value_override = words[2]
        if override_dict.has_key(vis_override) == False:
            override_dict[vis_override] = {}
        override_dict[vis_override][param_override] = value_override
            
    infile.close()

    return override_dict

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to move data around.
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

# All of these know about the PHANGS keys. They're called as part of
# the pipeline to set up the imaging.

def copy_data(gal=None,
              just_proj=None,
              just_ms=None,
              just_array=None,
              do_split=True,
              do_statwt=True,
              quiet=False):
    """
    Copies data from its original location, which is specified in a
    text file ms_key.txt. Then splits out only the science target.
    """

    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    ms_key = read_ms_key()

    if ms_key.has_key(gal) == False:
        if quiet == False:
            print "Galaxy "+gal+" not found in the measurement set key."
        return
    gal_specific_key = ms_key[gal]

    # Change to the right directory

    this_dir = dir_for_gal(gal)
    os.chdir(this_dir)

    if quiet == False:
        print "--------------------------------------------------------"
        print "START: Copying data from original location."
        print "--------------------------------------------------------"

        print "Galaxy: ", gal
        if just_array != None: print "Project: ", just_proj
        if just_array != None: print "Measurements Set: ", just_ms
        if just_array != None: print "Array: ", just_array

    # Loop over files in the measurement set key

    for this_proj in gal_specific_key.keys():
        if just_proj != None:
            if type(just_proj) == type([]):
                if just_proj.count(this_proj) == 0:
                    continue
            else:
                if this_proj != just_proj:
                    continue

        proj_specific_key = gal_specific_key[this_proj]
        for this_ms in proj_specific_key.keys():
            if just_ms != None:
                if type(just_ms) == type([]):
                    if just_ms.count(this_ms) == 0:
                        continue
                    else:
                        if this_ms != just_ms:
                            continue
 
            if just_array != None:
                if this_ms.count(just_array) == 0:
                    continue
           
            # Set up a copy command, overwriting previous versions

            in_file = proj_specific_key[this_ms]            

            if do_split:
                copied_file = gal+'_'+this_proj+'_'+this_ms+'_copied.ms'
            else:
                copied_file = gal+'_'+this_proj+'_'+this_ms+'.ms'

            os.system('rm -rf '+copied_file)
            os.system('rm -rf '+copied_file+'.flagversions')

            command = 'cp -r -H '+in_file+' '+copied_file
            print command
            var = os.system(command)    
            print var

            # Call split and statwt if desired (default is yes)

            if do_split:

                if quiet == False:
                    print "Splitting out science target data."

                out_file = gal+'_'+this_proj+'_'+this_ms+'.ms'

                os.system('rm -rf '+out_file)
                os.system('rm -rf '+out_file+'.flagversions')
                
                # If present, use the corrected column. If not, then
                # use the data column.
                mytb = au.createCasaTool(tbtool)
                mytb.open(copied_file)
                colnames = mytb.colnames()
                if colnames.count('CORRECTED_DATA') == 1:
                    print "Data has a CORRECTED column. Will use that."
                    use_column = 'CORRECTED'
                else:
                    print "Data lacks a CORRECTED column. Will use DATA column."
                    use_column = 'DATA'
                mytb.close()

                split(vis=copied_file
                      , intent ='OBSERVE_TARGET#ON_SOURCE'
                      , datacolumn=use_column
                      , outputvis=out_file)        

                os.system('rm -rf '+copied_file)
                os.system('rm -rf '+copied_file+'.flagversions')

            if do_statwt:

                if quiet == False:
                    print "Using statwt to re-weight the data."

                statwt(vis=out_file,
                       datacolumn='DATA')

    if quiet ==False:
        print "--------------------------------------------------------"
        print "END: Copying data from original location."
        print "--------------------------------------------------------"

def concat_line_for_gal(
    gal=None,
    just_proj=None,
    just_ms=None,
    just_array=None,
    line='co21',
    tag='',
    do_statwt=True,
    do_chan0=True,
    quiet=False):
    """
    Combine all measurement sets for one line and one galaxy.
    """

    # Identify the data sets to combine

    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    ms_key = read_ms_key()

    if ms_key.has_key(gal) == False:
        if quiet == False:
            print "Galaxy "+gal+" not found in the measurement set key."
        return
    gal_specific_key = ms_key[gal]

    files_to_concat = []

    for this_proj in gal_specific_key.keys():
        if just_proj != None:
            if type(just_proj) == type([]):
                if just_proj.count(this_proj) == 0:
                    continue
            else:
                if this_proj != just_proj:
                    continue

        proj_specific_key = gal_specific_key[this_proj]
        for this_ms in proj_specific_key.keys():
            if just_ms != None:
                if type(just_ms) == type([]):
                    if just_ms.count(this_ms) == 0:
                        continue
                    else:
                        if this_ms != just_ms:
                            continue
            
            if just_array != None:
                if this_ms.count(just_array) == 0:
                    continue

            this_in_file = gal+'_'+this_proj+'_'+this_ms+'_'+line+'.ms'    
            if os.path.isdir(this_in_file) == False:
                continue
            files_to_concat.append(this_in_file)

    if len(files_to_concat) == 0:
        print "No files to concatenate found. Returning."
        return

    # Concatenate all of the relevant files

    if tag != '':
        out_file =  gal+'_'+tag+'_'+line+'.ms'
    else:
        out_file =  gal+'_'+line+'.ms'

    os.system('rm -rf '+out_file)
    os.system('rm -rf '+out_file+'.flagversions')

    concat(vis=files_to_concat,
           concatvis=out_file)

    # Re-weight the data empirically

    if do_statwt:
        statwt(vis=out_file,
               datacolumn='DATA')

    # Collapse to form a "channel 0" measurement set

    if do_chan0 == False:
        return
    
    if tag != '':
        chan0_vis = gal+'_'+tag+'_'+line+'_chan0.ms'
    else:
        chan0_vis = gal+'_'+line+'_chan0.ms'

    os.system('rm -rf '+chan0_vis)
    os.system('rm -rf '+chan0_vis+'.flagversions')
    split(vis=out_file
          , datacolumn='DATA'
          , spw=''
          , outputvis=chan0_vis
          , width=10000)

def concat_cont_for_gal(
    gal=None,
    just_proj=None,
    just_ms=None,
    just_array=None,
    tag='',
    ):
    """
    Concatenate continuum data sets.
    """
    pass

    # Identify the data sets to combine

    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    ms_key = read_ms_key()

    if ms_key.has_key(gal) == False:
        if quiet == False:
            print "Galaxy "+gal+" not found in the measurement set key."
        return
    gal_specific_key = ms_key[gal]

    files_to_concat = []

    for this_proj in gal_specific_key.keys():
        if just_proj != None:
            if type(just_proj) == type([]):
                if just_proj.count(this_proj) == 0:
                    continue
            else:
                if this_proj != just_proj:
                    continue

        proj_specific_key = gal_specific_key[this_proj]
        for this_ms in proj_specific_key.keys():
            if just_ms != None:
                if type(just_ms) == type([]):
                    if just_ms.count(this_ms) == 0:
                        continue
                    else:
                        if this_ms != just_ms:
                            continue
            
            if just_array != None:
                if this_ms.count(just_array) == 0:
                    continue

            this_in_file = gal+'_'+this_proj+'_'+this_ms+'_cont.ms'
            if os.path.isdir(this_in_file) == False:
                continue
            files_to_concat.append(this_in_file)

    if len(files_to_concat) == 0:
        print "No files to concatenate found. Returning."
        return

    # Concatenate all of the relevant files

    if tag != '':
        out_file =  gal+'_'+tag+'_cont.ms'
    else:
        out_file =  gal+'_cont.ms'

    os.system('rm -rf '+out_file)
    os.system('rm -rf '+out_file+'.flagversions')

    concat(vis=files_to_concat,
           concatvis=out_file)

def extract_phangs_lines(   
    gal=None,
    just_array=None,
    ext='',
    quiet=False
    ):
    """
    Extract all phangs lines and continuum for a galaxy.
    """

    # Could add sio54, which is generally covered in PHANGS but almost
    # always likely to be a nondetection.

    if quiet == False:
        print "--------------------------------------------------------"
        print "START: Extracting spectral lines from data set."
        print "--------------------------------------------------------"

    chan_width = {}
    chan_width['co21'] = 2.5
    chan_width['c18o21'] = 6.0

    for line in ['co21', 'c18o21']:

        extract_line_for_galaxy(   
            gal=gal,
            just_array=just_array,
            line=line,
            ext=ext,
            chan_width=chan_width[line],    
            quiet=quiet
            )

        if just_array != '12m':
            concat_line_for_gal(
                gal=gal,
                just_array='7m',
                tag='7m',
                line=line,
                do_statwt=True,
                do_chan0=True)

        if just_array != '7m':
            concat_line_for_gal(
                gal=gal,
                just_array='12m',
                tag='12m',
                line=line,
                do_statwt=True,
                do_chan0=True)

        has_7m = len(glob.glob(gal+'*7m*'+line+'*')) > 0
        has_12m = len(glob.glob(gal+'*12m*'+line+'*')) > 0
        if has_12m == False or has_7m == False:
            continue

        if just_array == None:

            concat_line_for_gal(
                gal=gal,
                just_array = None,
                tag='12m+7m',
                line=line,
                do_statwt=True,
                do_chan0=True)
            

    if quiet == False:
        print "--------------------------------------------------------"
        print "END: Extracting spectral lines from data set."
        print "--------------------------------------------------------"

def extract_phangs_continuum(   
    gal=None,
    just_array=None,
    ext='',
    quiet=False
    ):
    """
    Extract all phangs lines and continuum for a galaxy.
    """

    if quiet == False:
        print "--------------------------------------------------------"
        print "START: Extracting continuum from data set."
        print "--------------------------------------------------------"

    lines_to_flag = line_list.lines_co+line_list.lines_13co+line_list.lines_c18o

    extract_continuum_for_galaxy(   
        gal=gal,
        just_array=just_array,
        lines_to_flag=lines_to_flag,
        ext=ext,
        do_statwt=True,
        do_collapse=True,
        quiet=quiet
        )

    if just_array != '12m':
        concat_cont_for_gal(
            gal=gal,
            just_array = '7m',
            tag = '7m')

    if just_array != '7m':
        concat_cont_for_gal(
            gal=gal,
            just_array = '12m',
            tag = '12m')

    has_7m = len(glob.glob(gal+'*7m*cont*')) > 0
    has_12m = len(glob.glob(gal+'*12m*cont*')) > 0

    if just_array == None and has_7m and has_12m:
        concat_cont_for_gal(
            gal=gal,
            just_array = None,
            tag = '12m+7m')

    if quiet == False:
        print "--------------------------------------------------------"
        print "END: Extracting continuum from data set."
        print "--------------------------------------------------------"

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to extract lines from a measurement set
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

def list_lines_in_ms(
    in_file= None,
    vsys=0.0,
    gal=None,
    ):    
    """
    List the lines likely to be present in a measurement set. This can
    be a general purpose utility.
    """

    sol_kms = 2.99e5

    # pull the parameters from the galaxy in the mosaic file
    if gal != None:
        mosaic_parms = read_mosaic_key()
        if mosaic_parms.has_key(gal):
            vsys = mosaic_parms[gal]['vsys']
            vwidth = mosaic_parms[gal]['vwidth']

    # Set up the input file

    if os.path.isdir(in_file) == False:
        if quiet == False:
            print "Input file not found."
        return

    lines_in_ms = []
    for line in line_list.line_list.keys():
        restfreq_ghz = line_list.line_list[line]

        # work out the frequency of the line and the line wings

        target_freq_ghz = restfreq_ghz*(1.-vsys/sol_kms)

        this_spw_list = au.getScienceSpwsForFrequency(in_file, target_freq_ghz*1e9)    
        if len(this_spw_list) == 0:
            continue
        
        lines_in_ms.append(line)

    return lines_in_ms

def chanwidth_for_line(
    in_file=None,
    line='co21',
    gal=None,
    vsys=0.0,
    vwidth=500.,
    quiet=False):
    """
    Return the coarsest channel width among spectral windows that
    overlap a line. This can be a general purpose utility.
    """

    # pull the parameters from the galaxy in the mosaic file
    if gal != None:
        mosaic_parms = read_mosaic_key()
        if mosaic_parms.has_key(gal):
            vsys = mosaic_parms[gal]['vsys']
            vwidth = mosaic_parms[gal]['vwidth']

    sol_kms = 2.99e5

    # Set up the input file

    if os.path.isdir(in_file) == False:
        if quiet == False:
            print "Input file not found."
        return

    # Look up the line

    if line_list.line_list.has_key(line) == False:
        if quiet == False:
            print "Line not found. Give lower case abbreviate found in line_list.py"
        return
    restfreq_ghz = line_list.line_list[line]

    # Work out which spectral windows contain the line contain

    target_freq_ghz = restfreq_ghz*(1.-vsys/sol_kms)
    target_freq_high = restfreq_ghz*(1.-(vsys-0.5*vwidth)/sol_kms)
    target_freq_low = restfreq_ghz*(1.-(vsys+0.5*vwidth)/sol_kms)

    spw_list_string = ''    
    first = True
    spw_list = []

    for target_freq in [target_freq_high, target_freq_ghz, target_freq_low]:
        this_spw_list = au.getScienceSpwsForFrequency(in_file, target_freq*1e9)    
        for spw in this_spw_list:
            if spw_list.count(spw) != 0:
                continue
            spw_list.append(spw)
            if not first:
                spw_list_string += ','
            else:
                first = False
            spw_list_string += str(spw)

    if len(spw_list) == 0:
        if quiet == False:
            print "No spectral windows contain this line at this redshift."
        return

    # Figure out how much averaging is needed to reach the target resolution
    chan_width_hz = au.getChanWidths(in_file, spw_list_string)

    # Convert to km/s and return
    chan_width_kms = abs(chan_width_hz / (restfreq_ghz*1e9)*sol_kms)

    return chan_width_kms

def extract_line(in_file=None,
                 out_file=None,
                 line='co21',
                 gal=None,
                 vsys=0.0,
                 vwidth=500.,
                 chan_width=2.5,
                 quiet=False):
    """
    Extract a spectral line from a measurement set and regrid onto a
    new velocity grid with the desired spacing. This doesn't
    necessarily need the PHANGS keys in place and may be a general
    purpose utility.
    """

    sol_kms = 2.99e5

    # pull the parameters from the galaxy in the mosaic file
    if gal != None:
        mosaic_parms = read_mosaic_key()
        if mosaic_parms.has_key(gal):
            vsys = mosaic_parms[gal]['vsys']
            vwidth = mosaic_parms[gal]['vwidth']

    # Set up the input file

    if os.path.isdir(in_file) == False:
        if quiet == False:
            print "Input file not found."
        return

    # Look up the line

    if line_list.line_list.has_key(line) == False:
        if quiet == False:
            print "Line not found. Give lower case abbreviate found in line_list.py"
        return
    restfreq_ghz = line_list.line_list[line]

    # Work out which spectral windows contain the line contain

    target_freq_ghz = restfreq_ghz*(1.-vsys/sol_kms)
    target_freq_high = restfreq_ghz*(1.-(vsys-0.5*vwidth)/sol_kms)
    target_freq_low = restfreq_ghz*(1.-(vsys+0.5*vwidth)/sol_kms)

    spw_list_string = ''    
    first = True
    spw_list = []

    for target_freq in [target_freq_high, target_freq_ghz, target_freq_low]:
        this_spw_list = au.getScienceSpwsForFrequency(in_file, target_freq*1e9)    
        for spw in this_spw_list:
            if spw_list.count(spw) != 0:
                continue
            spw_list.append(spw)
            if not first:
                spw_list_string += ','
            else:
                first = False
            spw_list_string += str(spw)

    if len(spw_list) == 0:
        if quiet == False:
            print "No spectral windows contain this line at this redshift."
        return

    # Figure out the starting velocity and number of channels.

    start_vel_kms = (vsys - vwidth/2.0)
    nchan = int(np.floor(vwidth / chan_width)+1)

    # Convert to strings. The precision is hardcoded with
    # extragalactic ALMA work in mind.

    restfreq_string = "{:10.6f}".format(restfreq_ghz)+'GHz'
    chan_dv_string =  "{:5.2f}".format(chan_width)+'km/s'
    start_vel_string =  "{:6.1f}".format(start_vel_kms)+'km/s'

    # Figure out how much averaging is needed to reach the target resolution

    chan_width_hz = au.getChanWidths(in_file, spw_list_string)
    current_chan_width_kms = abs(chan_width_hz / (restfreq_ghz*1e9)*sol_kms)    
    target_width_hz = chan_width/sol_kms*restfreq_ghz*1e9
    rebin_factor = min(target_width_hz / chan_width_hz)

    if max(current_chan_width_kms) > chan_width:
        print "Requested channel width is smaller than the starting width. Returning."
        return
    
    if rebin_factor < 2:
        chanbin = 1
    else:
        chanbin = int(np.floor(rebin_factor/2.))

    if chanbin > 1:
        chanaverage = True
    else:
        chanaverage = False

    # Report the call

    if quiet == False:        
        print "FILE:", in_file
        print "LINE TAG: ", line
        print "REST FREQUENCY: ", restfreq_string
        print "SPECTRAL WINDOWS: ", spw_list
        print "STARTING CHANNEL WIDTH: ", current_chan_width_kms
        print "TARGET CHANNEL WIDTH: ", chan_dv_string
        print "SUPPLIED SOURCE VELOCITY: ", str(vsys)
        print "DESIRED VELOCITY WIDTH: ", str(vwidth)
        print "START VELOCITY: ", start_vel_string
        print "NUMBER OF CHANNELS: ", str(nchan)
        print "CHANNELS TO BIN TOGETHER FIRST: ", chanbin

    # Call mstransform
    
    os.system('rm -rf '+out_file+'.temp')
    os.system('rm -rf '+out_file+'.temp.flagversions')

    mstransform(vis=in_file,
                outputvis=out_file+'.temp',
                spw=spw_list_string,
                datacolumn='DATA',
                chanaverage=chanaverage,
                chanbin=chanbin,
                hanning=False,
                interpolation='cubic',
                )

    os.system('rm -rf '+out_file)
    os.system('rm -rf '+out_file+'.flagversions')

    mstransform(vis=out_file+'.temp',
                outputvis=out_file,
                datacolumn='DATA',
                regridms=True,
                mode='velocity',
                interpolation='cubic',
                start=start_vel_string,
                nchan=nchan,
                width=chan_dv_string,
                restfreq=restfreq_string,
                outframe='lsrk',
                veltype='radio',
                )

    os.system('rm -rf '+out_file+'.temp')
    os.system('rm -rf '+out_file+'.temp.flagversions')

    return

def extract_line_for_galaxy(   
    gal=None,
    just_proj=None,
    just_ms=None,
    just_array=None,
    line='co21',
    vsys=0.0,
    vwidth=500.,
    chan_width=2.5,    
    ext='',
    quiet=False
    ):
    """
    Extract a given line for all data sets for a galaxy. This knows
    about the PHANGS measurement set keys and is specific to our
    projects.
    """
    
    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    ms_key = read_ms_key()

    if ms_key.has_key(gal) == False:
        if quiet == False:
            print "Galaxy "+gal+" not found in the measurement set key."
        return
    gal_specific_key = ms_key[gal]

    # Look up the galaxy specific parameters

    mosaic_parms = read_mosaic_key()
    if mosaic_parms.has_key(gal):
        vsys = mosaic_parms[gal]['vsys']
        vwidth = mosaic_parms[gal]['vwidth']

    # Change to the right directory

    this_dir = dir_for_gal(gal)
    os.chdir(this_dir)

    # Loop over all projects and measurement sets

    for this_proj in gal_specific_key.keys():

        if just_proj != None:
            if type(just_proj) == type([]):
                if just_proj.count(this_proj) == 0:
                    continue
            else:
                if this_proj != just_proj:
                    continue

        proj_specific_key = gal_specific_key[this_proj]
        for this_ms in proj_specific_key.keys():
            if just_ms != None:
                if type(just_ms) == type([]):
                    if just_ms.count(this_ms) == 0:
                        continue
                    else:
                        if this_ms != just_ms:
                            continue
            
            if just_array != None:
                if this_ms.count(just_array) == 0:
                    continue
            
            in_file = gal+'_'+this_proj+'_'+this_ms+ext+'.ms'
            out_file = gal+'_'+this_proj+'_'+this_ms+'_'+line+'.ms'    

            lines_in_ms = list_lines_in_ms(in_file, gal=gal)
            if lines_in_ms.count(line) == 0:
                print "Line not found in measurement set."
                return

            extract_line(in_file=in_file,
                         out_file=out_file,
                         line=line,
                         gal=gal,
                         chan_width=chan_width,
                         quiet=quiet)            

    return
    
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to extract continuum from a measurement set
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

def contsub(
    in_file=None,
    lines_to_flag=None,
    gal=None,
    vsys=0.0,
    vwidth=500.,
    quiet=False    
    ):
    """
    Carry out uv continuum subtraction on a measurement set. First
    figures out channels corresponding to spectral lines for a suite
    of bright lines.
    """

    sol_kms = 2.99e5

    # Set up the input file

    if os.path.isdir(in_file) == False:
        if quiet == False:
            print "Input file not found."
        return

    # pull the parameters from the galaxy in the mosaic file

    if gal != None:
        mosaic_parms = read_mosaic_key()
        if mosaic_parms.has_key(gal):
            vsys = mosaic_parms[gal]['vsys']
            vwidth = mosaic_parms[gal]['vwidth']

    # set the list of lines to flag

    if lines_to_flag == None:
        lines_to_flag = line_list.lines_co + line_list.lines_13co + line_list.lines_c18o

    vm = au.ValueMapping(in_file)

    spw_flagging_string = ''
    first = True
    for spw in vm.spwInfo.keys():
        this_spw_string = str(spw)+':0'
        if first:
            spw_flagging_string += this_spw_string
            first = False
        else:
            spw_flagging_string += ','+this_spw_string            

    for line in lines_to_flag:
        rest_linefreq_ghz = line_list.line_list[line]

        shifted_linefreq_hz = rest_linefreq_ghz*(1.-vsys/sol_kms)*1e9
        hi_linefreq_hz = rest_linefreq_ghz*(1.-(vsys-vwidth/2.0)/sol_kms)*1e9
        lo_linefreq_hz = rest_linefreq_ghz*(1.-(vsys+vwidth/2.0)/sol_kms)*1e9

        spw_list = au.getScienceSpwsForFrequency(this_infile,
                                                 shifted_linefreq_hz)
        if spw_list == []:
            continue

        print "Found overlap for "+line
        for this_spw in spw_list:
            freq_ra = vm.spwInfo[this_spw]['chanFreqs']
            chan_ra = np.arange(len(freq_ra))
            to_flag = (freq_ra >= lo_linefreq_hz)*(freq_ra <= hi_linefreq_hz)
            to_flag[np.argmin(np.abs(freq_ra - shifted_linefreq_hz))]
            low_chan = np.min(chan_ra[to_flag])
            hi_chan = np.max(chan_ra[to_flag])                
            this_spw_string = str(this_spw)+':'+str(low_chan)+'~'+str(hi_chan)
            if first:
                spw_flagging_string += this_spw_string
                first = False
            else:
                spw_flagging_string += ','+this_spw_string

    print "... proposed channels to avoid "+spw_flagging_string

    os.system('rm -rf '+in_file+'.contsub')
    uvcontsub(vis=in_file,
              fitspw=spw_flagging_string,
              excludechans=True)

    return

def extract_continuum(
    in_file=None,
    out_file=None,
    lines_to_flag=None,
    gal=None,
    vsys=0.0,
    vwidth=500.,
    do_statwt=True,
    do_collapse=True,
    quiet=False):
    """
    Extract a continuum measurement set, flagging any specified lines,
    reweighting using statwt, and then collapsing to a single "channel
    0" measurement.
    """

    sol_kms = 2.99e5

    # Set up the input file

    if os.path.isdir(in_file) == False:
        if quiet == False:
            print "Input file not found."
        return

    # pull the parameters from the galaxy in the mosaic file

    if gal != None:
        mosaic_parms = read_mosaic_key()
        if mosaic_parms.has_key(gal):
            vsys = mosaic_parms[gal]['vsys']
            vwidth = mosaic_parms[gal]['vwidth']

    # set the list of lines to flag

    if lines_to_flag == None:
        lines_to_flag = line_list.lines_co + line_list.lines_13co + line_list.lines_c18o

    # Make a continuum copy of the data

    os.system('rm -rf '+out_file)
    os.system('rm -rf '+out_file+'.flagversions')

    command = 'cp -r -H '+in_file+' '+out_file
    print command
    var = os.system(command)
    print var
    
    # Figure out the line channels and flag them

    vm = au.ValueMapping(out_file)

    spw_flagging_string = ''
    first = True
    for spw in vm.spwInfo.keys():
        this_spw_string = str(spw)+':0'
        if first:
            spw_flagging_string += this_spw_string
            first = False
        else:
            spw_flagging_string += ','+this_spw_string            

    for line in lines_to_flag:
        rest_linefreq_ghz = line_list.line_list[line]

        shifted_linefreq_hz = rest_linefreq_ghz*(1.-vsys/sol_kms)*1e9
        hi_linefreq_hz = rest_linefreq_ghz*(1.-(vsys-vwidth/2.0)/sol_kms)*1e9
        lo_linefreq_hz = rest_linefreq_ghz*(1.-(vsys+vwidth/2.0)/sol_kms)*1e9

        spw_list = au.getScienceSpwsForFrequency(out_file,
                                                 shifted_linefreq_hz)
        if spw_list == []:
            continue

        print "Found overlap for "+line
        for this_spw in spw_list:
            freq_ra = vm.spwInfo[this_spw]['chanFreqs']
            chan_ra = np.arange(len(freq_ra))
            to_flag = (freq_ra >= lo_linefreq_hz)*(freq_ra <= hi_linefreq_hz)
            to_flag[np.argmin(np.abs(freq_ra - shifted_linefreq_hz))]
            low_chan = np.min(chan_ra[to_flag])
            hi_chan = np.max(chan_ra[to_flag])                
            this_spw_string = str(this_spw)+':'+str(low_chan)+'~'+str(hi_chan)
            if first:
                spw_flagging_string += this_spw_string
                first = False
            else:
                spw_flagging_string += ','+this_spw_string
        
    print "... proposed flagging "+spw_flagging_string

    if spw_flagging_string != '':
        flagdata(vis=out_file,
                 spw=spw_flagging_string,
                 )
        
    if do_statwt:
        print "... deriving emprical weights using STATWT."
        statwt(vis=out_file,
               datacolumn='DATA')

    if do_collapse:
        print "... Collapsing the continuum to a single channel."

        os.system('rm -rf '+out_file+'.temp_copy')
        os.system('rm -rf '+out_file+'.temp_copy.flagversions')

        command = 'mv '+out_file+' '+out_file+'.temp_copy'
        print command
        var = os.system(command)
        print var

        command = 'mv '+out_file+'.flagversions '+out_file+'.temp_copy.flagversions'
        print command
        var = os.system(command)
        print var

        split(vis=out_file+'.temp_copy',
              outputvis=out_file,
              width=10000,
              datacolumn='DATA',
              keepflags=False)        

        os.system('rm -rf '+out_file+'.temp_copy')
        os.system('rm -rf '+out_file+'.temp_copy.flagversions')
        
    return    

def extract_continuum_for_galaxy(   
    gal=None,
    just_proj=None,
    just_ms=None,
    just_array=None,
    lines_to_flag=None,
    ext='',
    do_statwt=True,
    do_collapse=True,
    quiet=False
    ):
    """
    Extract continuum for all data sets for a galaxy. This knows about
    the PHANGS measurement set keys and is specific to our projects.
    """
    
    if gal == None:
        if quiet == False:
            print "Please specify a galaxy."
        return

    ms_key = read_ms_key()

    if ms_key.has_key(gal) == False:
        if quiet == False:
            print "Galaxy "+gal+" not found in the measurement set key."
        return
    gal_specific_key = ms_key[gal]

    # Look up the galaxy specific parameters

    mosaic_parms = read_mosaic_key()
    if mosaic_parms.has_key(gal):
        vsys = mosaic_parms[gal]['vsys']
        vwidth = mosaic_parms[gal]['vwidth']

    # Change to the right directory

    this_dir = dir_for_gal(gal)
    os.chdir(this_dir)

    # Loop over all projects and measurement sets

    for this_proj in gal_specific_key.keys():

        if just_proj != None:
            if type(just_proj) == type([]):
                if just_proj.count(this_proj) == 0:
                    continue
            else:
                if this_proj != just_proj:
                    continue

        proj_specific_key = gal_specific_key[this_proj]
        for this_ms in proj_specific_key.keys():
            if just_ms != None:
                if type(just_ms) == type([]):
                    if just_ms.count(this_ms) == 0:
                        continue
                    else:
                        if this_ms != just_ms:
                            continue
            
            if just_array != None:
                if this_ms.count(just_array) == 0:
                    continue
            
            in_file = gal+'_'+this_proj+'_'+this_ms+ext+'.ms'
            out_file = gal+'_'+this_proj+'_'+this_ms+'_cont.ms'

            extract_continuum(
                in_file=in_file,
                out_file=out_file,
                lines_to_flag=lines_to_flag,
                gal=gal,
                do_statwt=do_statwt,
                do_collapse=do_collapse)

    return

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to characterize measurement sets
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

def pick_phangs_cell_and_imsize(
    in_file=None,
    oversamp=5
    ):
    """
    Wraps estimate_cell_and_imsize and also allows our custom
    overrides.
    """

    cell_size_string, x_size_string, y_size_string = \
        estimate_cell_and_imsize(in_file, oversamp)

    override_dict = read_override_mosaic_params()

    # Check for overrides
    if override_dict.has_key(in_file):
        if override_dict.has_key('cell_size'):
            cell_size_string = override_dict[this_vis]['cell_size']
        if override_dict.has_key('x_size'):
            x_size_string = override_dict[this_vis]['x_size']
        if override_dict.has_key('y_size'):
            y_size_string = override_dict[this_vis]['y_size']    

    return cell_size_string, x_size_string, y_size_string

def estimate_cell_and_imsize(
    in_file=None,    
    oversamp=5
    ):
    """
    Pick a cell and image size for a measurement set. Requests an
    oversampling factor, which is by default 5. Will pick a good size
    for the FFT and will try to pick a round number for the cell size.
    """

    if os.path.isdir(in_file) == False:
        print "File not found."
        return
    
    valid_sizes = []
    for ii in range(10):
        for kk in range(3):
            for jj in range(3):
                valid_sizes.append(2**(ii+1)*5**(jj)*3**(kk))
    valid_sizes.sort()
    valid_sizes = np.array(valid_sizes)

    # Cell size implied by baseline distribution from analysis
    # utilities.

    au_cellsize, au_imsize, au_centralField = \
        au.pickCellSize(in_file, imsize=True, npix=oversamp)
    xextent = au_cellsize*au_imsize[0]*1.2
    yextent = au_cellsize*au_imsize[1]*1.2

    # Make the cell size a nice round number

    if au_cellsize < 0.1:
        cell_size = au_cellsize
    if au_cellsize >= 0.1 and au_cellsize < 0.5:
        cell_size = np.floor(au_cellsize/0.05)*0.05
    if au_cellsize >= 0.5 and au_cellsize < 1.0:
        cell_size = np.floor(au_cellsize/0.1)*0.1
    if au_cellsize >= 1.0 and au_cellsize < 2.0:
        cell_size = np.floor(au_cellsize/0.25)*0.25
    if au_cellsize >= 2.0 and au_cellsize < 5.0:
        cell_size = np.floor(au_cellsize/0.5)*0.5
    if au_cellsize >= 5.0:
        cell_size = np.floor(au_cellsize/1.0)*0.5

    # Now make the image size a good number for the FFT

    need_cells_x = xextent / cell_size
    need_cells_y = yextent / cell_size

    cells_x = np.min(valid_sizes[valid_sizes > need_cells_x])
    cells_y = np.min(valid_sizes[valid_sizes > need_cells_y])

    image_size = [int(cells_x), int(cells_y)]
    cell_size_string = str(cell_size)+'arcsec'

    x_size_string = str(image_size[0])
    y_size_string = str(image_size[1])

    return cell_size_string, x_size_string, y_size_string

# TBD: Add the baseline data extractor to make plots (extract_uv_plots.py)

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to characterize and manipulate cubes
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

def stat_clean_cube(cube_file=None):
    """
    Calculate statistics for an image cube.
    """
    if cube_file == None:
        print "No cube file specified. Returning"
        return
    imstat_dict = imstat(cube_file)
    
    return imstat_dict

def save_copy_of_cube(
    input_root=None,
    output_root=None):
    """
    Copy a cube to a new name. Used to make a backup copy. Overwrites
    the previous cube of that name.
    """

    wipe_cube(output_root)
    
    os.system('cp -r '+input_root+'.image '+output_root+'.image')
    os.system('cp -r '+input_root+'.model '+output_root+'.model')
    os.system('cp -r '+input_root+'.mask '+output_root+'.mask')
    os.system('cp -r '+input_root+'.pb '+output_root+'.pb')
    os.system('cp -r '+input_root+'.psf '+output_root+'.psf')
    os.system('cp -r '+input_root+'.residual '+output_root+'.residual')
    os.system('cp -r '+input_root+'.psf '+output_root+'.weight')
    os.system('cp -r '+input_root+'.residual '+output_root+'.sumwt')

def wipe_cube(
    cube_root=None):
    """
    Wipe files associated with a cube.
    """
    if cube_root == None:
        return
    os.system('rm -rf '+cube_root+'.image')
    os.system('rm -rf '+cube_root+'.model')
    os.system('rm -rf '+cube_root+'.mask')
    os.system('rm -rf '+cube_root+'.pb')
    os.system('rm -rf '+cube_root+'.psf')
    os.system('rm -rf '+cube_root+'.residual')
    os.system('rm -rf '+cube_root+'.weight')
    os.system('rm -rf '+cube_root+'.sumwt')

def replace_cube_with_copy(
    to_root=None,
    from_root=None):
    """
    Replace a cube with a copy.
    """

    wipe_cube(to_root)

    os.system('cp -r '+from_root+'.image '+to_root+'.image')
    os.system('cp -r '+from_root+'.model '+to_root+'.model')
    os.system('cp -r '+from_root+'.mask '+to_root+'.mask')
    os.system('cp -r '+from_root+'.pb '+to_root+'.pb')
    os.system('cp -r '+from_root+'.psf '+to_root+'.psf')
    os.system('cp -r '+from_root+'.residual '+to_root+'.residual')
    os.system('cp -r '+from_root+'.psf '+to_root+'.weight')
    os.system('cp -r '+from_root+'.residual '+to_root+'.sumwt')

def import_and_align_mask(  
    in_file=None,
    out_file=None,
    template=None,
    ):
    """
    Align a mask to a target astrometry. Some klugy steps to make
    things work most of the time.
    """

    # Import from FITS (could make optional)
    os.system('rm -rf '+out_file+'.temp_copy')
    importfits(fitsimage=in_file, 
               imagename=out_file+'.temp_copy'
               , overwrite=True)

    # Align to the template grid
    os.system('rm -rf '+out_file+'.temp_aligned')
    imregrid(imagename=out_file+'.temp_copy', 
             template=template, 
             output=out_file+'.temp_aligned', 
             asvelocity=True,
             interpolation='nearest',         
             replicate=False,
             overwrite=True)

    # Make an EXACT copy of the template, avoids various annoying edge cases
    os.system('rm -rf '+out_file)
    os.system('cp -r '+template+' '+out_file)
    
    hdr = imhead(template)

    # Pull the data out of the aligned mask and place it in the output file
    myia = au.createCasaTool(iatool)
    myia.open(out_file+'.temp_aligned')
    mask = myia.getchunk(dropdeg=True)
    myia.close()

    # Need to make sure this works for two dimensional cases, too.
    if (hdr['axisnames'][3] == 'Frequency') and \
            (hdr['ndim'] == 4):    
        myia.open(out_file)
        data = myia.getchunk(dropdeg=False)
        data[:,:,0,:] = mask
        myia.putchunk(data)
        myia.close()
    elif (hdr['axisnames'][2] == 'Frequency') and \
            (hdr['ndim'] == 4):    
        myia.open(mask_root+'.mask')
        data = myia.getchunk(dropdeg=False)
        data[:,:,:,0] = mask
        myia.putchunk(data)
        myia.close()
    else:
        print "ALERT! Did not find a case."

    os.system('rm -rf '+out_file+'.temp_copy')
    os.system('rm -rf '+out_file+'.temp_aligned')
    return

def apply_additional_mask(
    old_mask_file=None,
    new_mask_file=None,
    new_thresh=0.0,
    operation='AND'
    ):
    """
    Combine a mask with another mask on the same grid and some
    threshold. Can run AND/OR operations. Can be used to apply primary
    beam based masks by setting the PB file to new_mask_file and the
    pb_limit as new_thresh.
    """
    if root_mask == None:
        print "Specify a cube root file name."
        return

    myia = au.createCasaTool(iatool)    
    myia.open(new_mask_file)
    new_mask = myia.getchunk()
    myia.close()

    myia.open(old_mask_file)
    mask = myia.getchunk()
    if operation == "AND":
        mask *= (new_mask > new_thresh)
    else:
        mask = (mask + (new_mask > new_thresh)) >= 1.0
    myia.putchunk(mask)
    myia.close()

    return

def signal_mask(
    cube_root=None,
    out_file=None,
    operation='AND',
    high_snr = 4.0,
    low_snr = 2.0,
    ):
    """
    A simple signal mask creation routine used to make masks on the
    fly during imaging. Leverages CASA statistics and scipy.
    """
    
    if os.path.isdir(cube_root+'.image') == False:
        print 'Need CUBE_ROOT.image to be an image file.'
        print 'Returning. Generalize the code if you want different syntax.'
        return

    myia = au.createCasaTool(iatool)
    if operation == 'AND' or operation == 'OR':
        if os.path.isdir(cube_root+'.mask') == True:
            myia.open(cube_root+'.mask')
            old_mask = myia.getchunk()
            myia.close()
        else:
            print "Operation AND/OR requested but no previous mask found."
            print "... will set operation=NEW."
            operation = 'NEW'    

    if os.path.isdir(cube_root+'.residual') == True:
        stats = stat_clean_cube(cube_root+'.residual')
    else:
        stats = stat_clean_cube(cube_root+'.image')
    rms = stats['medabsdevmed'][0]/0.6745
    hi_thresh = high_snr*rms
    low_thresh = low_snr*rms

    header = imhead(cube_root+'.image')
    if header['axisnames'][2] == 'Frequency':
        spec_axis = 2
    else:
        spec_axis = 3

    myia.open(cube_root+'.image')
    cube = myia.getchunk()
    myia.close()

    hi_mask = (cube > hi_thresh)
    mask = \
        (hi_mask + np.roll(hi_mask,1,axis=spec_axis) + \
             np.roll(hi_mask,-1,axis=spec_axis)) >= 1

    if high_snr > low_snr:
        low_mask = (cube > low_thresh)
        rolled_low_mask = \
            (low_mask + np.roll(low_mask,1,axis=spec_axis) + \
                 np.roll(low_mask,-1,axis=spec_axis)) >= 1
        mask = ndimage.binary_dilation(hi_mask, 
                                       mask=rolled_low_mask, 
                                       iterations=-1)

    if operation == 'AND':
        mask = mask*old_mask
    if operation == 'OR':
        mask = (mask + old_mask) > 0
    if operation == 'NEW':
        mask = mask

    os.system('rm -rf '+cube_root+'.mask')
    os.system('cp -r '+cube_root+'.image '+cube_root+'.mask')
    myia.open(cube_root+'.mask')
    myia.putchunk(mask)
    myia.close()

def export_to_fits(
    cube_root=None,
    bitpix=-32):
    """
    Export the various products associated with a CASA cube to FITS.
    """

    exportfits(imagename=cube_root+'.image',
               fitsimage=cube_root+'.fits',
               velocity=True, overwrite=True, dropstokes=True, 
               dropdeg=True, bitpix=bitpix)

    exportfits(imagename=cube_root+'.model',
               fitsimage=cube_root+'_model.fits',
               velocity=True, overwrite=True, dropstokes=True, 
               dropdeg=True, bitpix=bitpix)

    exportfits(imagename=cube_root+'.residual',
               fitsimage=cube_root+'_residual.fits',
               velocity=True, overwrite=True, dropstokes=True, 
               dropdeg=True, bitpix=bitpix)

    exportfits(imagename=cube_root+'.mask',
               fitsimage=cube_root+'_mask.fits',
               velocity=True, overwrite=True, dropstokes=True, 
               dropdeg=True, bitpix=bitpix)
    
    exportfits(imagename=cube_root+'.pb',
               fitsimage=cube_root+'_pb.fits',
               velocity=True, overwrite=True, dropstokes=True, 
               dropdeg=True, bitpix=bitpix)

    return

# TBD: Add a routine to actually write the feathering scripts? (feather_script_12m and feather_script_7m)

# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%
# Routines to image the data
# &%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%&%

class cleanCall:
    
    def __init__(self):
        self.vis = None
        self.image_root = None
        self.phase_center = ""
        self.image_size = None
        self.cell_size = None
        self.restfreq_ghz = -1.0
        self.calcres = True
        self.calcpsf = True
        self.specmode = 'cube'
        self.deconvolver = 'hogbom'
        self.threshold = '0.0mJy/beam'
        self.scales_as_pix = [0]
        self.scales_as_angle = None
        self.smallscalebias = 0.9
        self.briggs_weight = 0.5
        self.niter = 0
        self.cycle_niter = 200
        self.minpsffraction = 0.5
        self.pblimit = 0.25
        self.uvtaper = None
        self.restoringbeam = ''
        self.usemask = 'user'
        self.mask = ''
        self.interactive = False
        self.rest = False
        self.logfile = None
        self.clean_mask_file = None

    def execute(self):
        """
        Execute the clean call.
        """
    
        if self.vis == None:
            print "No visibility. Returning."
            return    

        if os.path.isdir(self.vis) == False:
            print "Visibility file not found. Returning."
            return
        
        if self.cell_size == None or self.image_size == None:
            print "Estimating cell and image size."
            estimate_cell_and_imsize(self.vis, oversamp=5)

        if self.restfreq_ghz < 0:
            restfreq_str = ''
        else:
            restfreq_str = str(self.restfreq_ghz)+'GHz'

        if self.logfile != None:
            oldlogfile = casalog.logfile()
            casalog.setlogfile(self.logfile)

        if self.uvtaper == None:
            uv_taper_string = ''
        else:
            uv_taper_string = [str(uvtaper)+'arcsec',str(uvtaper)+'arcsec','0deg']

        if self.reset:
            print "Wiping previous versions of the cube."
            wipe_cube(self.image_root)

        tclean(vis=self.vis,
               imagename=self.image_root,
               phasecenter=self.phase_center,
               cell=self.cell_size,
               imsize=self.image_size,
               gridder='mosaic',
               # Spectral axis
               specmode=self.specmode,
               restfreq=restfreq_str,
               outframe='lsrk',
               veltype='radio',
               # Workflow
               calcres=self.calcres,
               calcpsf=self.calcpsf,
               # Deconvolver
               deconvolver=self.deconvolver,
               scales=self.scales_as_pix,
               smallscalebias=self.smallscalebias,
               pblimit=self.pblimit,
               normtype='flatnoise',
               # Restoring beam
               restoringbeam=self.restoringbeam,
               # U-V plane gridding
               weighting='briggs',
               robust=self.briggs_weight,
               uvtaper=uv_taper_string,
               # Stopping criterion
               niter=self.niter,
               threshold=self.threshold,
               cycleniter=self.cycle_niter,
               cyclefactor=3.0,
               minpsffraction=self.minpsffraction,
               # Mask
               usemask=self.usemask,
               mask=self.mask,
               pbmask=self.pblimit,
               # UI
               interactive=self.interactive,
               )

        if self.logfile != None:
            casalog.setlogfile(oldlogfile)

def make_dirty_map(
    clean_call = None,    
    ):
    """
    Create a dirty map from a visibility set.
    """

    if type(clean_call) != type(cleanCall()):
        print "Supply a valid clean call."

    clean_call.niter = 0
    clean_call.reset = True
    clean_call.usemask = 'pb'
    clean_call.logfile = clean_call.image_root+'_dirty.log'
    
    clean_call.execute()
    
    clean_call.reset = False
    clean_call.usemask = 'user'
    clean_call.logfile = None

    save_copy_of_cube(
        input_root=clean_call.image_root,
        output_root=clean_call.image_root+'_dirty')

def multiscale_loop(
    clean_call = None,
    record_file=None,
    delta_flux_threshold=0.02,
    absolute_threshold=None,
    snr_threshold=4.0,
    stop_at_negative=True,
    max_loop = 20
    ):
    """
    Carry out an iterative multiscale clean loop.
    """
    
    # Check that we have a vile clean call

    if type(clean_call) != type(cleanCall()):
        print "Supply a valid clean call."
    
    # Figure out the scales to use in pixel units

    cell_as_num = float((clean_call.cell_size.split('arcsec'))[0])
    scales_as_pix = []
    for scale in clean_call.scales_as_angle:
        scales_as_pix.append(int(scale/cell_as_num))
        
    clean_call.deconvolver = 'multiscale'
    clean_call.scales_as_pix = scales_as_pix

    print "I will use the following scales: "
    print "... as pixels: ", str(clean_call.scales_as_pix)
    print "... as arcseconds: ", str(clean_call.scales_as_angle)

    # Call the loop

    clean_loop(
        clean_call=clean_call,
        record_file=record_file,
        delta_flux_threshold=0.02,
        absolute_threshold=None,
        snr_threshold=4.0,
        stop_at_negative=True,
        max_loop = 20        
        )

    # Save a copy

    save_copy_of_cube(
        input_root=clean_call.image_root,
        output_root=clean_call.image_root+'_multiscale')

def singlescale_loop(
    clean_call = None,
    scales_as_angle=[],
    record_file=None,
    delta_flux_threshold=0.02,
    absolute_threshold=None,
    snr_threshold=4.0,
    stop_at_negative=True,
    max_loop = 20
    ):
    """
    Carry out an iterative multiscale clean loop.
    """
    
    # Check that we have a vile clean call

    if type(clean_call) != type(cleanCall()):
        print "Supply a valid clean call."
        
    clean_call.deconvolver = 'hogbom'

    # Call the loop

    clean_loop(
        clean_call=clean_call,
        record_file=record_file,
        delta_flux_threshold=delta_flux_threshold,
        absolute_threshold=absolute_threshold,
        snr_threshold=snr_threshold,
        stop_at_negative=stop_at_negative,
        max_loop = 20        
        )

    # Save a copy

    save_copy_of_cube(
        input_root=clean_call.image_root,
        output_root=clean_call.image_root+'_singlescale')

def clean_loop(
    clean_call = None,
    record_file=None,
    log_ext=None,
    delta_flux_threshold=0.02,
    absolute_threshold=None,
    snr_threshold=4.0,
    stop_at_negative=True,
    max_loop = 20
    ):
    """
    Carry out an iterative clean until a convergence criteria is met.
    """

   # Note the number of channels, which is used in setting the number
   # of iterations that we give to an individual clean call.

    vm = au.ValueMapping(clean_call.vis)
    nchan = vm.spwInfo[0]['numChannels']

    # Figure out the number of iterations we will use. Note that this
    # step is highly tunable, and can still be improved as we go
    # forward.

    base_niter = 10*nchan
    base_cycle_niter = 100
    loop = 1

    # Initialize our tracking of the flux in the model

    model_flux = 0.0

    # Open the text record if desired

    if record_file != None:
        f = open(record_file,'w')
        f.write("# column 1: loop type\n")
        f.write("# column 2: loop number\n")
        f.write("# column 3: supplied threshold\n")
        f.write("# column 4: model flux at end of this clean\n")
        f.write("# column 5: fractional change in flux (current-previous)/current\n")
        f.write("# column 6: number of iterations allocated (not necessarily used)\n")
        f.close()

    # Run the main loop

    proceed = True
    while proceed == True and loop <= max_loop:

        # Figure out how many iterations to give clean.

        if loop > 5:
            factor = 5
        else:
            factor = (loop-1)
        
        clean_call.niter = base_niter*(2**factor)
        clean_call.cycle_niter = base_cycle_niter*factor
        
        # Set the threshold for the clean call.

        if snr_threshold != None:
            resid_stats = stat_clean_cube(clean_call.image_root+'.residual')        
            current_noise = resid_stats['medabsdevmed'][0]/0.6745
            clean_call.threshold = str(current_noise*snr_threshold)+'Jy/beam'
        elif absolute_threshold != None:
            clean_call.threshold = absolute_threshold

        # Set the log file

        if log_ext != None:
            clean_call.logfile = cube_root+"_loop_"+str(loop)+"_"+log_ext+".log"
        else:
            clean_call.logfile = None

        # Save the previous version of the file
        save_copy_of_cube(
            input_root=clean_call.image_root,
            output_root=clean_call.image_root+'_prev')

        # Execute the clean call.

        clean_call.reset = False
        clean_call.execute()

        # Record the new model flux and check for convergence. A nice
        # way to improve this would be to calculate the flux per
        # iteration.

        model_stats = stat_clean_cube(clean_call.image_root+'.model')

        prev_flux = model_flux
        model_flux = model_stats['sum'][0]

        delta_flux = (model_flux-prev_flux)/model_flux

        if delta_flux_threshold > 0.0:
            proceed = \
                (delta_flux > delta_flux_threshold)

        if stop_at_negative:
            if model_flux < 0.0:
                proceed = False
            
        # Print output
                
        print ""
        print "******************************"
        print "CLEAN LOOP "+str(loop)
        print "... threshold "+clean_call.threshold
        print "... old flux "+str(prev_flux)
        print "... new flux "+str(model_flux)
        print "... fractional change "+str(delta_flux)+ \
            " compare to stopping criterion of "+str(delta_flux_threshold)
        print "... proceed? "+str(proceed)
        print "******************************"
        print ""

        # Record to log

        if record_file != None:
            line = 'LOOP '+str(loop)+ \
                ' '+clean_call.threshold+' '+str(model_flux)+ \
                ' '+str(delta_flux) + ' ' + str(clean_call.niter)+ '\n' 
            f = open(record_file,'a')
            f.write(line)
            f.close()

        if proceed == False:
            break
        loop += 1

    return

def buildPhangsCleanCall(
    gal=None,
    array='7m',
    product='co21',    
    tag='',
    ):
    """
    Build a clean call.
    """

    # Change to the relevant directory

    this_dir = dir_for_gal(gal)
    os.chdir(this_dir)

    # Initialize the call

    clean_call = cleanCall()

    # Set the files needed

    clean_call.vis = gal+'_'+array+'_'+product+'.ms'
    if os.path.isdir(clean_call.vis) == False:
        print "Visibility data not found. Returning empty."
        return

    if tag == '':
        clean_call.image_root = gal+'_'+array+'_'+product
    else:
        clean_call.image_root = gal+'_'+array+'_'+product+'_'+tag

    # Look up the center and shape of the mosaic

    mosaic_key = read_mosaic_key()
    this_ra = mosaic_key[gal]['rastring']
    this_dec = mosaic_key[gal]['decstring']
    clean_call.phase_center = 'J2000 '+this_ra+' '+this_dec

    cell_size, x_size, y_size = \
        pick_phangs_cell_and_imsize(clean_call.vis)
    image_size = [int(x_size), int(y_size)]

    clean_call.cell_size = cell_size
    clean_call.image_size = image_size

    # Look up the line and data product

    if product == 'co21':
        clean_call.specmode = 'cube'
        clean_call.restfreq_ghz = line_list.line_list['co21']

    if product == 'co21_chan0':
        clean_call.specmode = 'mfs'
        clean_call.restfreq_ghz = line_list.line_list['co21']

    if product == 'c18o21':
        clean_call.specmode = 'cube'
        clean_call.restfreq_ghz = line_list.line_list['c18o21']

    if product == 'c18o21_chan0':
        clean_call.specmode = 'mfs'
        clean_call.restfreq_ghz = line_list.line_list['c18o21']

    if product == 'cont':
        clean_call.specmode = 'mfs'
        clean_call.restfreq_ghz = -1.0

    # Set angular scales to be used in multiscale clean

    if array == '7m':
        clean_call.pblimit = 0.25
        clean_call.smallscalebias = 0.6
        clean_call.scales_as_angle = [0, 5, 10]
    elif array == '12m':
        clean_call.smallscalebias = 0.6
        clean_call.scales_as_angle = [0, 1, 2.5, 5]
    elif array == '12m+7m':
        clean_call.smallscalebias = 0.8
        clean_call.scales_as_angle = [0, 1, 2.5, 5, 10]

    # Look up overrides in the imaging parameters
    override_dict = read_override_imaging_params()

    if override_dict.has_key(clean_call.image_root):
        this_override_dict = override_dic[clean_call.image_root]

        if this_override_dict.has_key('smallscalebias'):
            clean_call.smallscale_bias = this_override_dict['smallscalebias']
        if override_dict.has_key('x_size'):
            x_size_string = override_dict[this_vis]['x_size']
        if override_dict.has_key('y_size'):
            y_size_string = override_dict[this_vis]['y_size']    

    # Define the clean mask
    clean_file_name = '../clean_masks/'+gal+'_co21_clean_mask.fits'
    if os.path.isfile(clean_file_name):
        clean_call.clean_mask_file = clean_file_name

    # Return

    return clean_call

def phangsImagingRecipe(
    clean_call = None,
    gal=None,
    array='7m',
    product='co21',    
    make_dirty_image=False,
    revert_to_dirty=False,
    read_in_clean_mask=False,
    run_multiscale_clean=False,
    revert_to_multiscale=False,
    make_singlescale_mask=False,
    run_singlescale_clean=False,
    do_export_to_fits=False
    ):
    """
    The end-to-end PHANGS imaging recipe. Dirty image -> mask
    alignment -> lightly masked multiscale clean -> heavily masked
    single scale clean -> export.
    """

    if clean_call == None:
        clean_call = buildPhangsCleanCall(
            gal=gal,
            array=array,
            product=product,
            )
    
    if make_dirty_image:
        print ""
        print "MAKING THE DIRTY IMAGE."
        print ""

        make_dirty_map(clean_call)

    if revert_to_dirty:
        print ""
        print "RESETING THE IMAGING TO THE DIRTY IMAGE."
        print ""

        replace_cube_with_copy(
            to_root=clea_call.image_root,
            from_root=clean_call.image_root+'_dirty')

    if read_in_clean_mask:
        print ""
        print "READING IN THE CLEAN MASK."
        print ""
        
        if clean_call.clean_mask_file != None:
            import_and_align_mask(
                in_file=clean_call.clean_mask_file,
                out_file=clean_call.image_root+'.mask',
                template=clean_call.image_root+'.image',
                )
        else:
            print "No clean mask defined."

    if run_multiscale_clean:
        print ""
        print "RUNNING THE MULTISCALE CLEAN."
        print ""

        multiscale_loop(
            clean_call = clean_call,
            record_file = clean_call.image_root+'_multiscale_record.txt',
            delta_flux_threshold=0.02,
            absolute_threshold=None,
            snr_threshold=4.0,
            stop_at_negative=True,
            max_loop = 20
            )

    if revert_to_multiscale:
        print ""
        print "RESETING THE IMAGING TO THE OUTPUT OF MULTISCALE CLEAN."
        print ""

        replace_cube_with_copy(
            to_root=clean_call.image_root,
            from_root=clean_call.image_root+'_multiscale')

    if make_singlescale_mask:
        print ""
        print "MAKING THE MASK FOR SINGLE SCALE CLEAN."
        print ""

        signal_mask(
            cube_root=clean_call.image_root,
            out_file=clean_call.image_root+'.mask',
            operation='AND',
            high_snr=4.0,
            low_snr=2.0)
        
    if run_singlescale_clean:
        print ""
        print "RUNNING THE SINGLE SCALE CLEAN."
        print ""

        singlescale_loop(
            clean_call = clean_call,
            record_file = clean_call.image_root+'_singlescale_record.txt',
            delta_flux_threshold=0.02,
            absolute_threshold=None,
            snr_threshold=1.0,
            stop_at_negative=True,
            max_loop = 20
            )

    if do_export_to_fits:
        print ""
        print "EXPORTING PRODUCTS TO FITS."
        print ""
        export_to_fits(clean_call.image_root)
        export_to_fits(clean_call.image_root+'_dirty')
        export_to_fits(clean_call.image_root+'_multiscale')

    return

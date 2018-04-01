
############################# BEGIN FRONTMATTER ################################
#                                                                              #
#   TEA - calculates Thermochemical Equilibrium Abundances of chemical species #
#                                                                              #
#   TEA is part of the PhD dissertation work of Dr. Jasmina                    #
#   Blecic, who developed it with coding assistance from                       #
#   undergraduate M. Oliver Bowman and under the advice of                     #
#   Prof. Joseph Harrington at the University of Central Florida,              #
#   Orlando, Florida, USA.                                                     #
#                                                                              #
#   Copyright (C) 2014-2016 University of Central Florida                      #
#                                                                              #
#   This program is reproducible-research software: you can                    #
#   redistribute it and/or modify it under the terms of the                    #
#   Reproducible Research Software License as published by                     #
#   Prof. Joseph Harrington at the University of Central Florida,              #
#   either version 0.3 of the License, or (at your option) any later           #
#   version.                                                                   #
#                                                                              #
#   This program is distributed in the hope that it will be useful,            #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of             #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the              #
#   Reproducible Research Software License for more details.                   #
#                                                                              #
#   You should have received a copy of the Reproducible Research               #
#   Software License along with this program.  If not, see                     #
#   <http://planets.ucf.edu/resources/reproducible/>.  The license's           #
#   preamble explains the situation, concepts, and reasons surrounding         #
#   reproducible research, and answers some common questions.                  #
#                                                                              #
#   This project was started with the support of the NASA Earth and            #
#   Space Science Fellowship Program, grant NNX12AL83H, held by                #
#   Jasmina Blecic, Principal Investigator Joseph Harrington, and the          #
#   NASA Science Mission Directorate Planetary Atmospheres Program,            #
#   grant NNX12AI69G.                                                          #
#                                                                              #
#   See the file ACKNOWLEDGING in the top-level TEA directory for              #
#   instructions on how to acknowledge TEA in publications.                    #
#                                                                              #
#   We welcome your feedback, but do not guarantee support.                    #
#   Many questions are answered in the TEA forums:                             #
#                                                                              #
#   https://physics.ucf.edu/mailman/listinfo/tea-user                          #
#   https://physics.ucf.edu/mailman/listinfo/tea-devel                         #
#                                                                              #
#   Visit our Github site:                                                     #
#                                                                              #
#   https://github.com/dzesmin/TEA/                                            #
#                                                                              #
#   Reach us directly at:                                                      #
#                                                                              #
#   Jasmina Blecic <jasmina@physics.ucf.edu>                                   #
#   Joseph Harrington <jh@physics.ucf.edu>                                     #
#                                                                              #
############################## END FRONTMATTER #################################

import numpy as np
import re
import os

from scipy.interpolate import UnivariateSpline
import scipy.constants as sc

import readconf as rc

location_TEA = os.path.realpath(os.path.dirname(__file__) + "/..") + "/"

# =============================================================================
# This module contains functions to write headers containing all necessary
# chemical information for a single T-P and multiple
# T-P runs. It consists of two main functions, make_singleheader() and
# make_atmheader() called by the runsingle.py and runatm.py modules
# respectively. The header_setup(), atm_headarr(), single_headarr(), and
# write_header() are the supporting functions for the main functions.
# Imported by runatm.py and runsingle.py to create the header files.
# =============================================================================


def read_stoich(spec_list, stoich_file='lib/stoich.txt'):
    """
    This function reads and returns stoichiometric values for the
    list of input species.
    This function is a common setup for both single T-P and multiple
    T-P runs.  It is executed by the runatm() and make_singleheader()
    functions.

    Parameters
    ----------
    spec_list: string array
       Array containing names of molecular species.
    stoich_file = 'lib/stoich.txt': string
       Name of file containing stoichiometric data.

    Returns
    -------
    spec_stoich: 2D float ndarray
       Array containing values from stoich_file that correspond to the
       species used.
    atom_stoich: 1D String ndarray
       Array of elements with non-zero stoichiometric values from
       spec_stoich species.
    """
    # Get number of elements that occur in species of interest
    nspec = len(spec_list)
    # Trim suffix from species list:
    nostate = np.copy(spec_list)
    for i in np.arange(nspec):
        nostate[i] = re.search('(.*?)_', spec_list[i]).group(1)

    # Location of the stoich_file
    stoich_file = location_TEA + stoich_file

    # Get stoichiometric information for species of interest
    with open(stoich_file, 'r') as f:
      stoich_data = []
      for line in f.readlines():
          l = [value for value in line.split()]
          stoich_data.append(l)
      # Store information in stoich_data array
      stoich_data = np.asarray(stoich_data)

    # All species names:
    allspec = stoich_data[2:,0]
    # Elemental abundances:
    dex      = stoich_data[0, 1:]
    elements = stoich_data[1, 1:]
    # Trim species names and cast to float:
    stoich_data = np.asarray(stoich_data[2:,1:], np.double)

    # Select species:
    # Has to be in a for-loop to keep order:
    idx = np.zeros(nspec, int)
    for i in np.arange(nspec):
      idx[i] = np.where(allspec == nostate[i])[0][0]
    spec_stoich = stoich_data[idx]

    # Now select elements:
    ielem = np.sum(spec_stoich, axis=0) > 0
    b = np.array(dex[ielem], np.double)
    spec_stoich = spec_stoich[:,ielem]
    atom_stoich = elements[ielem]

    return spec_stoich, atom_stoich


def read_gdata(spec_list, thermo_dir):
    """
    This function reads the free-energy data (gdata) from JANAF
    tables, and returns a list of spline functions and formation heat
    values for each input species (such that they can be later
    evaluated by the calc_gRT() function).
    It is executed by the runatm() and make_singleheader() functions.

    Parameters
    ----------
    spec_list: List of strings
       Array containing names of molecular species.
    thermo_dir: String
       Name of directory containing thermodynamic data.

    Returns
    -------
    free_energy: 1D list of scipy splines
       Splines (as function of temperature) of the free energies of
       the species.
    heat: 1D float ndarray
       Formation heat of the species.
    """
    # Obtain thermo_dir files, and count both files and species
    gdata_files = os.listdir(thermo_dir)
    nspec       = np.size(spec_list)

    free_energy, heat = [], []
    # Create index of where species listed in the input file are in thermo_dir
    for i in np.arange(nspec):
        spec_file = '{:s}/{:s}.txt'.format(thermo_dir, spec_list[i])
        with open(spec_file, 'r') as f:
          lines = f.readlines()[1:]  # Skip first line (header)

        nlines = len(lines)
        T = np.zeros(nlines)
        term1 = np.zeros(nlines)
        for j in np.arange(nlines):
            T[j], term1[j], t2 = lines[j].split()
            if T[j] == 298.15:
              heat.append(t2)
        # Convert data to an array
        free_energy.append(UnivariateSpline(T, term1, s=1))
    return free_energy, np.array(heat, np.double)


def calc_gRT(free_energy, heat, temp):
    """
    This function evaluates the chemical potentials for the species
    of interest at the specified temperature.  It is executed by the
    runatm() and make_singleheader() functions.  The inputs for this
    function must be generated by the read_gdata() function.

    Parameters
    ----------
    free_energy: 1D list of scipy splines
       Splines (as function of temperature) of the free energies of
       the species.
    heat: 1D float ndarray
       Formation heat of the species.
    temp: float
         Current temperature value.

    Returns
    -------
    g_RT: float array
         Array containing species' chemical potentials.
    """
    nspec = len(free_energy)
    g_RT = np.zeros(nspec)
    # Equation for g_RT term equation (10) in TEA theory document
    #  G        G-H(298)      delta-f H(298)
    # ---  =    -------  +    -------------
    # R*T         R*T              R*T

    # First term is divided by T in JANAF, Eq. (11) in TEA theory document
    # Second term needs to be converted to Joules (JANAF gives kJ)
    #  G   G-H(298)             1                                 1000
    # -- = ------- [J/K/mol] * ---      + delta-f H(298) [kJ/mol] ------
    # RT    T                 R[J/K/mol]                         RT [J/K/mol][K]
    for i in np.arange(nspec):
        # Evaluate free-energy spline at given temperature:
        free_en = free_energy[i](temp)
        # Calculate the above equation
        g_RT[i] = -(free_en/sc.R) + (heat[i]*1000 / (temp*sc.R))
    return g_RT


def write_header(hfolder, desc, temp, pressure, speclist, atomlist,
                 stoich_arr, b, g_RT):
    """
    This function writes a header file that contains all necessary data
    for TEA to run. It is run by make_atmheader() and make_singleheader().

    Parameters
    ----------
    hfolder: String
       Folder where to store the header file.
    desc: string
       Name of output file.
    temp: float
       Temperature value (in Kelvin degrees).
    pressure: float
       Pressure value (in bars).
    speclist: 1D list of strings
       Names of the species.
    atomlist:L 1D list of strings
       Names of the elements.
    stoich_arr: array
       Array containing the stoichiometric values of the species.
    b: 1D float ndarray
       Elemental mixing fractions.
    g_RT: float array
       Chemical potentials of the species.
    """
    nspec, natom = np.shape(stoich_arr)
    # Make header directory if it does not exist to store header files
    if not os.path.exists(hfolder):
        os.makedirs(hfolder)
    # Create header file to be used by the main pipeline
    outfile = "{:s}/header_{:s}_{:.0f}K_{:.2e}bar.txt".format(
                    hfolder, desc, temp, pressure)

    # Open file to write
    f = open(outfile, 'w+')

    # Comment at top of header file
    f.write(
    "# This is a header file for one T-P. It contains the following data:\n"
    "# pressure (bar), temperature (K), elemental abundances (b, unitless),\n"
    "# species names, stoichiometric values of each element in the species (a),\n"
    "# and chemical potentials.\n\n")
    f.write("{:.5e}\n".format(pressure))
    f.write("{:.3f}\n".format(temp))

    # Elemental abundances:
    bstr = " ".join(["{:.6e}".format(x) for x in b])
    f.write("b {:s}\n".format(bstr))

    # Title for species names
    f.write("# Species")
    for j in np.arange(natom):
      f.write("{:>3s}".format(atomlist[j]))
    f.write("  Chemical potential\n")

    # Loop over all species and titles
    for i in np.arange(nspec):
        # Loop over species and number of elements
        f.write("{:>9s}".format(speclist[i]))
        for j in np.arange(natom):
            # Write elemental number density
            f.write("{:>3.0f}".format(stoich_arr[i,j]))
        # Write chemical potentials, adjust spacing for minus sign
        f.write("  {:-14.10f}\n".format(g_RT[i]))

    f.close()


def make_singleheader(infile, desc, thermo_dir, location_out):
    '''
    This is the main function that creates single-run TEA header.
    It reads the input T-P file and retrieves necessary data.  It
    calls the read_gdata(), calc_gRT(), read_stoich(),
    header_setup(), and write_header() functions to create a
    header for the single T-P point.  This function is called by the
    runsingle.py module.

    Parameters
    ----------
    infile: string
         Name of the input file (single T-P file).
    desc: string
         Name of output directory given by user.
    thermo_dir = 'lib/gdata':  string
         Name of directory containing thermodynamic data.

    Returns
    -------
    desc: string
         Name of output directory given by user.
    pressure: float
         Current pressure value.
    temp: float
         Current temperature value.
    stoich_arr: array
         Array containing elemental abundances, species names, and their
         stoichiometric values.
    nspec: integer
         Number of species.
    g_RT: float array
         Array containing chemical potentials for each species at the
         current T-P.
    '''
    # Read single input file
    f = open(infile, 'r')

    # Allocate species list
    speclist = []

    # Begin by reading first line of file (l = 0)
    l = 0

    # Loop over all lines in input file to retrieve appropriate data
    for line in f.readlines():
        # Retrieve temperature
        if l == 0:
            temp     = float([value for value in line.split()][0])
        # Retrieve pressure
        if l == 1:
            pressure = float([value for value in line.split()][0])
        # Retrieve list of species
        if l > 1:
            val = [value for value in line.split()][0]
            speclist = np.append(speclist, val)
        l += 1

    f.close()

    # Retrieve number of species used
    nspec = np.size(speclist)

    # Load and evaluate gdata:
    free_energy, heat = mh.read_gdata(speclist, thermo_dir)
    g_RT = mh.calc_gRT(free_energy, heat, temp)
    stoich_arr = mh.read_stoich(speclist)

    # FINDME: get b values for write_header()
    #         get atomlist
    # Write header array to file
    hfolder = location_out + desc + "/headers/"
    write_header(hfolder, desc, temp, pressure, speclist, atomlist,
                 stoich_arr, b, g_RT)

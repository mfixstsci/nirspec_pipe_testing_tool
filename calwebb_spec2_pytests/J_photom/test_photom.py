
"""
py.test module for unit testing the photom step.
"""

import os
import time
import pytest
import logging
from glob import glob
from astropy.io import fits
from jwst.photom.photom_step import PhotomStep

from . import photom_utils
from .. import core_utils
from .. auxiliary_code import change_filter_opaque2science



# HEADER
__author__ = "M. A. Pena-Guerrero & Gray Kanarek"
__version__ = "2.2"

# HISTORY
# Nov 2017 - Version 1.0: initial version completed
# May 2018 - Version 2.0: Gray added routine to generalize reference file check
# May 2018 - Version 2.1: Maria separated completion from other tests
# Apr 2019 - Version 2.2: implemented logging capability


# Set up the fixtures needed for all of the tests, i.e. open up all of the FITS files

# Default names of pipeline input and output files
@pytest.fixture(scope="module")
def set_inandout_filenames(request, config):
    step = "photom"
    step_info = core_utils.set_inandout_filenames(step, config)
    step_input_filename, step_output_filename, in_file_suffix, out_file_suffix, True_steps_suffix_map = step_info
    return step, step_input_filename, step_output_filename, in_file_suffix, out_file_suffix, True_steps_suffix_map


# fixture to read the output file header
@pytest.fixture(scope="module")
def output_hdul(set_inandout_filenames, config):
    set_inandout_filenames_info = core_utils.read_info4outputhdul(config, set_inandout_filenames)
    step, txt_name, step_input_file, step_output_file, run_calwebb_spec2, outstep_file_suffix = set_inandout_filenames_info
    run_pipe_step = config.getboolean("run_pipe_steps", step)
    # determine which tests are to be run
    photom_completion_tests = config.getboolean("run_pytest", "_".join((step, "completion", "tests")))
    #photom_reffile_tests = config.getboolean("run_pytest", "_".join((step, "reffile", "tests")))
    #photom_validation_tests = config.getboolean("run_pytest", "_".join((step, "validation", "tests")))
    run_pytests = [photom_completion_tests]#, photom_reffile_tests, photom_validation_tests]

    # if run_calwebb_spec2 is True calwebb_spec2 will be called, else individual steps will be ran
    step_completed = False
    end_time = '0.0'

    working_directory = config.get("calwebb_spec2_input_file", "working_directory")
    initial_input_file = config.get("calwebb_spec2_input_file", "input_file")
    initial_input_file = os.path.join(working_directory, initial_input_file)
    detector = fits.getval(initial_input_file, "DETECTOR", 0)
    if not os.path.isfile(initial_input_file):
        pytest.skip("Skipping "+step+" because the initial input file given in PTT_config.cfg does not exist.")

    # check if the filter is to be changed
    change_filter_opaque = config.getboolean("calwebb_spec2_input_file", "change_filter_opaque")
    if change_filter_opaque:
        is_filter_opaque, step_input_filename = change_filter_opaque2science.change_filter_opaque(step_input_file, step=step)
        if is_filter_opaque:
            filter_opaque_msg = "With FILTER=OPAQUE, the calwebb_spec2 will run up to the extract_2d step. Photometry pytest now set to Skip."
            print(filter_opaque_msg)
            core_utils.add_completed_steps(txt_name, step, outstep_file_suffix, step_completed, end_time)
            pytest.skip("Skipping "+step+" because FILTER=OPAQUE.")

    if run_calwebb_spec2:
        hdul = core_utils.read_hdrfits(step_output_file, info=False, show_hdr=False)
        return hdul, step_output_file, run_pytests
    else:

        if run_pipe_step:

            # Create the logfile for PTT, but erase the previous one if it exists
            PTTcalspec2_log = os.path.join(working_directory, 'PTT_calspec2_'+detector+'_'+step+'.log')
            if os.path.isfile(PTTcalspec2_log):
                os.remove(PTTcalspec2_log)
            print("Information outputed to screen from PTT will be logged in file: ", PTTcalspec2_log)
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            logging.basicConfig(filename=PTTcalspec2_log, level=logging.INFO)
            # print pipeline version
            import jwst
            pipeline_version = "\n *** Using jwst pipeline version: "+jwst.__version__+" *** \n"
            print(pipeline_version)
            logging.info(pipeline_version)
            if change_filter_opaque:
                logging.info(filter_opaque_msg)

            if os.path.isfile(step_input_file):

                msg = " *** Step "+step+" set to True"
                print(msg)
                logging.info(msg)
                stp = PhotomStep()

                # check that previous pipeline steps were run up to this point
                core_utils.check_completed_steps(step, step_input_file)

                # get the right configuration files to run the step
                local_pipe_cfg_path = config.get("calwebb_spec2_input_file", "local_pipe_cfg_path")
                # start the timer to compute the step running time
                start_time = time.time()
                if local_pipe_cfg_path == "pipe_source_tree_code":
                    result = stp.call(step_input_file)
                else:
                    result = stp.call(step_input_file, config_file=local_pipe_cfg_path+'/photom.cfg')
                result.save(step_output_file)
                # end the timer to compute the step running time
                end_time = repr(time.time() - start_time)   # this is in seconds
                msg = "Step "+step+" took "+end_time+" seconds to finish"
                print(msg)
                logging.info(msg)
                step_completed = True
                hdul = core_utils.read_hdrfits(step_output_file, info=False, show_hdr=False)

                # rename and move the pipeline log file
                calspec2_pilelog = "calspec2_pipeline_"+step+"_"+detector+".log"
                pytest_workdir = os.getcwd()
                logfile = glob(pytest_workdir+"/pipeline.log")[0]
                os.rename(logfile, os.path.join(working_directory, calspec2_pilelog))

                # add the running time for this step
                core_utils.add_completed_steps(txt_name, step, outstep_file_suffix, step_completed, end_time)
                return hdul, step_output_file, run_pytests


            else:
                msg = "Skipping running pipeline step "+step
                print(msg)
                logging.info(msg)
                end_time = core_utils.get_stp_run_time_from_screenfile(step, detector, working_directory)
                if os.path.isfile(step_output_file):
                    hdul = core_utils.read_hdrfits(step_output_file, info=False, show_hdr=False)
                    step_completed = True
                    # add the running time for this step
                    core_utils.add_completed_steps(txt_name, step, outstep_file_suffix, step_completed, end_time)
                    return hdul, step_output_file, run_pytests
                else:
                    step_completed = False
                    # add the running time for this step
                    core_utils.add_completed_steps(txt_name, step, outstep_file_suffix, step_completed, end_time)
                    pytest.skip()

        else:
            msg =" The input file does not exist. Skipping step."
            print(msg)
            logging.info(msg)
            core_utils.add_completed_steps(txt_name, step, outstep_file_suffix, step_completed, end_time)
            pytest.skip("Skipping "+step+" because the input file does not exist.")



# Unit tests

def test_s_photom_exists(output_hdul):
    # want to run this pytest?
    # output_hdul[2] = photom_completion_tests, photom_reffile_tests, photom_validation_tests
    run_pytests = output_hdul[2][0]
    if not run_pytests:
        msg = "Skipping completion pytest: option to run Pytest is set to False in PTT_config.cfg file.\n"
        print(msg)
        logging.info(msg)
        pytest.skip(msg)
    else:
        msg = "\n * Running completion pytest...\n"
        print(msg)
        logging.info(msg)
        assert photom_utils.s_photom_exists(output_hdul[0]), "The keyword S_PHOTOM was not added to the header --> Photom step was not completed."


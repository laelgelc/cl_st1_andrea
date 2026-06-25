#!/usr/bin/env bash

# Run the CCA results extraction programme on the SAS HTML output.
#
# The Python script reads the Canonical Structure section of the SAS CANCORR
# results file and writes two JSON files:
#
#   - cca_var.json
#       Correlations between the VAR variables and their canonical variables.
#
#   - cca_with.json
#       Correlations between the WITH variables and their canonical variables.
#
# Because no --output-dir argument is supplied here, both JSON files are written
# to the directory from which this shell script is executed.

python cca_results_extract.py \
    output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html

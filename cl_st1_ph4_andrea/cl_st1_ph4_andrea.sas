/* CCA - CL_St1_Ph4_andrea_CCA */

/* Match this to the actual folder in SAS OnDemand */
%let project = cl_st1_ph4_andrea_cca;
%let myfolder = &project;

/* Replace with your SAS user ID */
%let sasusername = u63529080;

/* Importing the data set */
proc import datafile="/home/&sasusername/&myfolder/tv_commercials_cca.tsv"
            out=cl_st1_ph4_andrea_cca
            dbms=tab
            replace;
   getnames=yes;
   guessingrows=max;
run;

/* CCA */
title "CCA for &project";
ods noproctitle;
ods graphics / imagemap=on;

proc cancorr data=work.cl_st1_ph4_andrea_cca
             out=cca_scores;
    var ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8;
    with vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
run;
quit;
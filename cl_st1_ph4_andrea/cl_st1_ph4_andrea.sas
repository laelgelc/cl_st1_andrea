/* CCA - CL_St1_Ph4_andrea_CCA */
/* Replace all occurrences of this project ID with yours and create a folder named after it */
%let project = cl_st1_ph4_andrea_CCA;

%let myfolder = &project;

/* Replace all occurrences of this user ID with yours */
%let sasusername = u63529080;

/* Importing the data set */
proc import datafile="/home/&sasusername/&myfolder/tv_commercials_cca.tsv"
            out=cl_st1_ph4_andrea_CCA
            dbms=tab
            replace;
   getnames=yes;
run;

/* CCA */

title "CCA for &project";
ods noproctitle;
ods graphics / imagemap=on;

proc cancorr data=WORK.CL_ST1_PH4_ANDREA_CCA out=cca_scores;
    var ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8;
    with vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
run;
quit;
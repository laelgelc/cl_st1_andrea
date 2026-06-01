/* CCA - CL_St1_Ph4_andrea_CCA */

/* Match this to the actual folder in SAS OnDemand */
%LET project = cl_st1_ph4_andrea_CCA;
%LET myfolder = &project;

/* Replace with your SAS user ID */
%LET sasusername = u63529080;

/* Importing the data set */
PROC IMPORT DATAFILE="/home/&sasusername/&myfolder/tv_commercials_cca.tsv"
            OUT=tv_commercials_cca
            DBMS=TAB
            REPLACE;
   GETNAMES=YES;
   GUESSINGROWS=MAX;
RUN;

PROC CONTENTS DATA=work.tv_commercials_cca;
RUN;

PROC MEANS DATA=work.tv_commercials_cca N NMISS MEAN STD MIN MAX;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
RUN;

/* CCA */
TITLE "CCA for &project";
ODS NOPROCTITLE;
ODS GRAPHICS / IMAGEMAP=ON;

PROC CANCORR DATA=work.tv_commercials_cca
             OUT=tv_commercials_cca_scores;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8;
    WITH vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8;
RUN;
QUIT;